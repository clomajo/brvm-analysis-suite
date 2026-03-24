#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timedelta

import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Starting technical analyzer...")

def get_historical_data(company_id, days=200):
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    try:
        # Remove order first to test
        res = supabase.table('historical_data') \
            .select('trade_date, open_price, high_price, low_price, price, volume') \
            .eq('company_id', company_id) \
            .gte('trade_date', start_date.isoformat()) \
            .lte('trade_date', end_date.isoformat()) \
            .execute()
        
        if not res.data:
            return None
        
        df = pd.DataFrame(res.data)
        df = df.sort_values('trade_date')  # Sort in pandas instead
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

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    
    deltas = prices.diff()
    gain = deltas.where(deltas > 0, 0)
    loss = -deltas.where(deltas < 0, 0)
    
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def get_latest_historical_id(company_id):
    try:
        res = supabase.table('historical_data') \
            .select('id') \
            .eq('company_id', company_id) \
            .order('trade_date') \
            .limit(1) \
            .execute()
        
        if res.data:
            return res.data[0]['id']
        return None
    except Exception as e:
        print(f"Error getting historical_id: {e}")
        return None

# Get all companies
res = supabase.table('companies').select('id, symbol').execute()
companies = res.data
print(f"Found {len(companies)} companies")

success_count = 0
for company in companies[:5]:
    print(f"\nProcessing {company['symbol']}...")
    
    df = get_historical_data(company['id'], days=200)
    if df is None:
        print(f"  No data returned")
        continue
    
    print(f"  Got {len(df)} rows")
    print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
    
    if len(df) < 50:
        print(f"  Not enough data (need 50, got {len(df)})")
        continue
    
    historical_id = get_latest_historical_id(company['id'])
    if not historical_id:
        print(f"  No historical_id found")
        continue
    
    print(f"  Historical ID: {historical_id}")
    
    # Calculate RSI
    rsi = calculate_rsi(df['close'])
    print(f"  RSI: {rsi}")
    
    if rsi:
        # Save RSI only for testing
        try:
            data = {
                'historical_data_id': historical_id,
                'rsi': float(rsi)
            }
            supabase.table('technical_analysis').insert(data).execute()
            print(f"  Saved successfully")
            success_count += 1
        except Exception as e:
            print(f"  Save failed: {e}")

print(f"\nCompleted: {success_count}/5 companies")
