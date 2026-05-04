import requests
ANON_KEY='sb_publishable_IMWcNKWBdOnIYEQ6dvSztw_54iohHy-'
SUPABASE_URL='https://lynevvhmstpcffobwudr.supabase.co'

r5 = requests.get(f'{SUPABASE_URL}/rest/v1/companies?select=id,symbol',
    headers={'apikey': ANON_KEY, 'Authorization': f'Bearer {ANON_KEY}'})
id_to_sym = {c['id']: c['symbol'] for c in r5.json()}

changes = []
for cid, sym in id_to_sym.items():
    if sym in ['BRVMC','BRVM30']: continue
    r = requests.get(
        f'{SUPABASE_URL}/rest/v1/historical_data?company_id=eq.{cid}&select=trade_date,price&order=trade_date.desc&limit=20',
        headers={'apikey': ANON_KEY, 'Authorization': f'Bearer {ANON_KEY}'}
    )
    prices = r.json()
    if len(prices) < 2: continue
    latest_price = prices[0]['price']
    latest_date  = prices[0]['trade_date']
    prev_price = None
    prev_date  = None
    for p in prices[1:]:
        if p['price'] != latest_price:
            prev_price = p['price']
            prev_date  = p['trade_date']
            break
    if prev_price:
        chg = (latest_price - prev_price) / prev_price * 100
        changes.append((sym, latest_price, prev_price, prev_date, round(chg,2)))
    else:
        changes.append((sym, latest_price, latest_price, latest_date, 0.0))

changes.sort(key=lambda x: x[4], reverse=True)
print(f"{'Sym':<8} {'Prix':>10} {'Prev':>10} {'Prev date':<14} {'Chg':>8}")
print('-'*54)
for sym, lp, pp, pd, chg in changes:
    marker = '🟢' if chg > 0 else ('🔴' if chg < 0 else '⚪')
    print(f"{sym:<8} {lp:>10.0f} {pp:>10.0f} {pd:<14} {chg:>+7.2f}% {marker}")
