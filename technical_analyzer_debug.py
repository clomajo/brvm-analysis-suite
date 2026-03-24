#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Starting technical analyzer...")

def get_historical_data(company_id, days=200):
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    try:
        res = supabase.table('historical_data') \
            .select('trade_date, open_price, high_price, low_price, price, volume') \
            .eq('company_id', company_id) \
            .gte('trade_date', start_date.isoformat()) \
            .lte('trade_date', end_date.isoformat()) \
            .order('trade_date', ascending=True) \
            .execute()
        
        if not res.data:
            return None
        
        df = pd.DataFrame(res.data)
        df = df.rename(columns={
            'trade_date': 'date',
            'open_price': 'open',
            'high_price': 'high',
            'low_price': 'low',
            'price': 'close',
            'volume': 'volume'
        })
        return df
        
    except Exception as e:
        print(f"Error: {e}")
        return None

# Get all companies
res = supabase.table('companies').select('id, symbol').execute()
companies = res.data
print(f"Found {len(companies)} companies")

success_count = 0
for company in companies[:5]:  # Test first 5 companies
    print(f"Processing {company['symbol']}...")
    df = get_historical_data(company['id'], days=200)
    if df is None:
        print(f"  No data for {company['symbol']}")
        continue
    print(f"  Got {len(df)} rows of data")
    print(f"  Latest close price: {df['close'].iloc[-1] if len(df) > 0 else 'N/A'}")
    success_count += 1

print(f"Completed: {success_count}/5 companies")
