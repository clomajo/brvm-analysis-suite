from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))

res = supabase.table('opportunities').select('symbol, score, technical_score, fundamental_score, liquidity_score, trend_score').order('score', desc=True).limit(10).execute()

print('Top 10 Opportunities:')
print('=' * 70)
for row in res.data:
    print(f"{row['symbol']:8} | Score: {row['score']:5.2f} | Tech: {row['technical_score']:5.2f} | Fund: {row['fundamental_score']:5.2f} | Liq: {row['liquidity_score']:5.2f} | Trend: {row['trend_score']:5.2f}")
