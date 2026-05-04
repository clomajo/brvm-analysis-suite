import pandas as pd
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])

# Trouver le company_id de ORAC
res = supabase.table('companies').select('id,symbol').eq('symbol', 'ORAC').execute()
company_id = res.data[0]['id']
print(f"ORAC company_id: {company_id}")

# Charger le fichier Excel
df = pd.read_excel('/Users/kaylam/Downloads/27_market-data_ORANGE_CI.xlsx')
df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
df = df.sort_values('Date').reset_index(drop=True)
print(f"Rows to load: {len(df)} | {df['Date'].iloc[0]} to {df['Date'].iloc[-1]}")

# Préparer les données
rows = []
for _, row in df.iterrows():
    price = float(row['Close']) if row['Close'] > 0 else None
    if price is None:
        continue
    rows.append({
        'company_id': company_id,
        'trade_date': row['Date'],
        'price': price,
        'volume': int(row['Volume']) if row['Volume'] > 0 else 0,
        'value': float(row['Close'] * row['Volume']) if row['Close'] > 0 else 0,
    })

print(f"Valid rows: {len(rows)}")

# Supprimer les anciennes données et recharger
res = supabase.table('historical_data').delete().eq('company_id', company_id).execute()
print(f"Deleted existing rows")

# Insérer par batch de 200
batch_size = 200
for i in range(0, len(rows), batch_size):
    batch = rows[i:i+batch_size]
    supabase.table('historical_data').upsert(batch, on_conflict='company_id,trade_date').execute()
    print(f"  Batch {i//batch_size + 1}: {len(batch)} rows")

print(f"✅ ORAC history loaded: {len(rows)} rows")
