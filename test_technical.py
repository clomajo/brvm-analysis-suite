import os
import sys
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

print("Connecting to Supabase...")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Fetching companies...")
res = supabase.table('companies').select('id, symbol').execute()
print(f"Found {len(res.data)} companies")

if len(res.data) > 0:
    print(f"First company: {res.data[0]}")

print("Checking historical_data...")
res2 = supabase.table('historical_data').select('id, company_id').limit(5).execute()
print(f"Found {len(res2.data)} historical records")

print("Done!")
