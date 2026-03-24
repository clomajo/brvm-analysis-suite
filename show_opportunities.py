from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))

res = supabase.table('opportunities').select('symbol, score, technical_score, signal').order('score', desc=True).execute()

print('=' * 85)
print(f"{'Rank':<4} | {'Symbol':<10} | {'Score':<6} | {'Tech':<8} | {'Signal':<12}")
print('=' * 85)

for i, row in enumerate(res.data, 1):
    print(f"{i:<4} | {row['symbol']:<10} | {row['score']:>6.1f} | {row['technical_score']:>8.1f} | {row['signal']:<12}")

print('=' * 85)
print(f'Total: {len(res.data)} companies')

# Summary
scores = [row['score'] for row in res.data]
print(f'\nScore Summary:')
print(f'  Top: {max(scores):.1f}')
print(f'  Average: {sum(scores)/len(scores):.1f}')
print(f'  Bottom: {min(scores):.1f}')

# Signal distribution
signals = {}
for row in res.data:
    signal = row['signal']
    signals[signal] = signals.get(signal, 0) + 1
print(f'\nSignal Distribution:')
for signal, count in sorted(signals.items(), key=lambda x: x[1], reverse=True):
    print(f'  {signal}: {count} companies')
