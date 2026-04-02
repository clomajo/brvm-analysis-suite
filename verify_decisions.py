import os
import requests
import json
from supabase import create_client
from dotenv import load_dotenv
from datetime import date, timedelta

load_dotenv()
supabase = create_client(
    os.environ['SUPABASE_URL'],
    os.environ['SUPABASE_SERVICE_ROLE_KEY']
)
MISTRAL_KEY = os.environ.get('MISTRAL_API_KEY')

today      = date.today()
check_date = today - timedelta(days=90)  # signals from 90 days ago

print(f"Verifying signals from {check_date} (90 days ago)...")

# ── 1. Fetch signals from 90 days ago ────────────────────────────────────────
res = supabase.table('brvm_decisions') \
    .select('*') \
    .eq('date', check_date.isoformat()) \
    .execute()

signals = res.data
if not signals:
    print(f"  No signals found for {check_date} — nothing to verify today")
    exit(0)

print(f"  Found {len(signals)} signals to verify")

# ── 2. Fetch actual prices for those tickers ──────────────────────────────────
# Get company_id map
comp_res = supabase.table('companies').select('id, symbol').execute()
symbol_to_id = {r['symbol']: r['id'] for r in comp_res.data}

results = []
for signal in signals:
    ticker     = signal['ticker']
    company_id = symbol_to_id.get(ticker)
    if not company_id:
        print(f"  Skipping {ticker} — no company_id found")
        continue

    # Get closest price to today
    price_res = supabase.table('historical_data') \
        .select('trade_date, price') \
        .eq('company_id', company_id) \
        .gte('trade_date', (today - timedelta(days=7)).isoformat()) \
        .lte('trade_date', today.isoformat()) \
        .order('trade_date', desc=True) \
        .limit(1) \
        .execute()

    if not price_res.data:
        print(f"  Skipping {ticker} — no recent price found")
        continue

    actual_price  = float(price_res.data[0]['price'])
    signal_price  = None

    # Get signal-date price
    signal_price_res = supabase.table('historical_data') \
        .select('price') \
        .eq('company_id', company_id) \
        .gte('trade_date', (check_date - timedelta(days=5)).isoformat()) \
        .lte('trade_date', (check_date + timedelta(days=5)).isoformat()) \
        .order('trade_date', desc=True) \
        .limit(1) \
        .execute()

    if signal_price_res.data:
        signal_price = float(signal_price_res.data[0]['price'])

    actual_return = None
    hit_target    = None
    if signal_price and signal_price > 0:
        actual_return = round((actual_price - signal_price) / signal_price * 100, 2)
        if signal['signal'] == 'ACHAT':
            hit_target = actual_price >= float(signal['upside_target'])
        elif signal['signal'] == 'EVITER':
            hit_target = actual_price <= float(signal['downside_target'])

    results.append({
        'ticker':    ticker,
        'signal':    signal['signal'],
        'hit_target': hit_target,
        'actual_return': actual_return,
        'signal_price': signal_price,
        'actual_price': actual_price,
        'actual_return_str': f"{actual_return:+.2f}%" if actual_return else "N/A"
    })

print(f"\n── Price verification complete ──────────────────────────")
for r in sorted(results, key=lambda x: x['actual_return'] or 0, reverse=True):
    hit = "✅" if r['hit_target'] else "❌" if r['hit_target'] is not None else "—"
    print(f"  {r['ticker']:6} | {r['signal']:10} | {r['actual_return_str']:8} | {hit}")

# ── 3. AI sentiment analysis for each ticker ──────────────────────────────────
print(f"\n── Running AI sentiment analysis ────────────────────────")

def get_sentiment(ticker, signal):
    if not MISTRAL_KEY:
        return None, None, None
    try:
        prompt = f"""You are a financial analyst specializing in West African markets (BRVM).
Analyze the recent news sentiment for {ticker} stock listed on the BRVM exchange.
Based on your knowledge of this company and recent market conditions in the UEMOA region:

1. What is the overall news sentiment for {ticker} in the last 30 days? 
2. Does this sentiment CONFIRM or CONTRADICT a {signal} signal?

Respond in JSON only, no other text:
{{"sentiment_score": <number from -100 to 100>, "sentiment_direction": "<Positive|Neutral|Negative>", "confirmed": <true|false>, "reasoning": "<one sentence>"}}"""

        response = requests.post(
            'https://api.mistral.ai/v1/chat/completions',
            headers={'Authorization': f'Bearer {MISTRAL_KEY}', 'Content-Type': 'application/json'},
            json={'model': 'mistral-small-latest', 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 200},
            timeout=15
        )
        content = response.json()['choices'][0]['message']['content']
        content = content.replace('```json', '').replace('```', '').strip()
        data = json.loads(content)
        return (
            float(data.get('sentiment_score', 0)),
            data.get('sentiment_direction', 'Neutral'),
            bool(data.get('confirmed', False))
        )
    except Exception as e:
        print(f"    Sentiment error for {ticker}: {e}")
        return None, None, None

# Run sentiment for ACHAT and EVITER signals only
sentiment_map = {}
for r in results:
    if r['signal'] in ['ACHAT', 'EVITER']:
        score, direction, confirmed = get_sentiment(r['ticker'], r['signal'])
        sentiment_map[r['ticker']] = (score, direction, confirmed)
        if direction:
            conf_str = "✅ confirmed" if confirmed else "❌ contradicts"
            print(f"  {r['ticker']:6} | {direction:8} ({score:+.0f}) | {conf_str}")

# ── 4. Upsert results into brvm_decisions_results ────────────────────────────
print(f"\n── Upserting to Supabase ─────────────────────────────────")
upsert_rows = []
for r in results:
    sent = sentiment_map.get(r['ticker'], (None, None, None))
    
    # Find decision_id
    dec = next((s for s in signals if s['ticker'] == r['ticker']), None)
    
    upsert_rows.append({
        'decision_id':          dec['id'] if dec else None,
        'ticker':               r['ticker'],
        'signal_date':          check_date.isoformat(),
        'signal':               r['signal'],
        'signal_price':         r['signal_price'],
        'actual_price':         r['actual_price'],
        'actual_return':        r['actual_return'],
        'upside_target':        dec['upside_target'] if dec else None,
        'hit_target':           r['hit_target'],
        'sentiment_30d':        sent[0],
        'sentiment_direction':  sent[1],
        'sentiment_confirmed':  sent[2],
        'verified_at':          today.isoformat(),
    })

supabase.table('brvm_decisions_results') \
    .upsert(upsert_rows, on_conflict='ticker,signal_date') \
    .execute()

print(f"✅ {len(upsert_rows)} results verified and stored for {check_date}")

# ── 5. Summary stats ──────────────────────────────────────────────────────────
achat = [r for r in results if r['signal'] == 'ACHAT' and r['hit_target'] is not None]
eviter = [r for r in results if r['signal'] == 'EVITER' and r['hit_target'] is not None]

if achat:
    hit_rate = sum(1 for r in achat if r['hit_target']) / len(achat) * 100
    avg_ret  = sum(r['actual_return'] for r in achat if r['actual_return']) / len(achat)
    print(f"\n── Today's verification summary ─────────────────────────")
    print(f"  ACHAT:  {len(achat)} signals | hit rate: {hit_rate:.1f}% | avg return: {avg_ret:+.2f}%")
if eviter:
    hit_rate = sum(1 for r in eviter if r['hit_target']) / len(eviter) * 100
    print(f"  EVITER: {len(eviter)} signals | hit rate: {hit_rate:.1f}%")
