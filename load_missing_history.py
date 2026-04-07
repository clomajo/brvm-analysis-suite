import pandas as pd
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])

BASE = '/Users/kaylam/Downloads/Historical Data BRVM 10Y/'

files = {
    'ORAC': BASE + '27_market-data_ORANGE CI.xlsx',
    'ETIT': BASE + '16_market-data_ECOBANK.xlsx',
    'ABJC': BASE + '30_market-data_SERVAIR ABIDJAN.xlsx',
    'SDCC': BASE + '38_market-data_SODECI.xlsx',
    'SICC': BASE + '10_market-data_BICICI.xlsx',
}

res = supabase.table('companies').select('id,symbol').execute()
sym_to_id = {r['symbol']: r['id'] for r in res.data}

for symbol, filepath in files.items():
    if not os.path.exists(filepath):
        print(f"❌ {symbol}: file not found")
        continue

    company_id = sym_to_id.get(symbol)
    if not company_id:
        print(f"❌ {symbol}: not in companies table")
        continue

    df = pd.read_excel(filepath)
    df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
    df = df.sort_values('Date').reset_index(drop=True)

    rows = []
    for _, row in df.iterrows():
        try:
            price = float(row['Close'])
            if price <= 0:
                continue
            rows.append({
                'company_id': company_id,
                'trade_date': row['Date'],
                'price': price,
                'volume': int(float(row['Volume'])) if float(row['Volume']) > 0 else 0,
                'value': price * int(float(row['Volume'])),
            })
        except:
            continue

    supabase.table('historical_data').delete().eq('company_id', company_id).execute()

    for i in range(0, len(rows), 200):
        batch = rows[i:i+200]
        supabase.table('historical_data').upsert(batch, on_conflict='company_id,trade_date').execute()

    print(f"✅ {symbol}: {len(rows)} rows | {rows[0]['trade_date']} to {rows[-1]['trade_date']}")

print("\nDone")
