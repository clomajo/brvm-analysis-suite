from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))

# Get top opportunities
res = supabase.table('opportunities').select('symbol, score, technical_score, fundamental_score, liquidity_score, trend_score, signal, last_updated').order('score', desc=True).limit(10).execute()

print('=' * 80)
print('TOP 10 OPPORTUNITIES (Updated)')
print('=' * 80)
print(f"{'Symbol':<10} | {'Score':<6} | {'Tech':<6} | {'Fund':<6} | {'Liq':<6} | {'Trend':<6} | {'Signal':<12}")
print('-' * 80)

for row in res.data:
    print(f"{row['symbol']:<10} | {row['score']:>6.1f} | {row['technical_score']:>6.1f} | {row['fundamental_score']:>6.1f} | {row['liquidity_score']:>6.1f} | {row['trend_score']:>6.1f} | {row['signal']:<12}")

print('=' * 80)
if res.data:
    print(f"Last updated: {res.data[0]['last_updated']}")
