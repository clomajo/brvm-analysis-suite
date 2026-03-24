#!/usr/bin/env python3
"""
technical_analyzer_all.py
Calculates technical indicators for ALL 47 BRVM companies.
Handles companies with limited historical data.
"""

import os
import sys
import pandas as pd
import numpy as np
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def calculate_rsi(prices, period=14):
    """Calculate RSI with fallback for short data"""
    if len(prices) < period + 1:
        # Use shorter period if data is limited
        period = max(5, len(prices) // 3)
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

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD with fallback for short data"""
    # Adjust periods based on available data
    if len(prices) < slow + signal:
        if len(prices) < 20:
            return None, None, None
        slow = max(10, len(prices) // 2)
        fast = max(5, slow // 2)
        signal = max(5, slow // 3)
    
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]

def calculate_moving_averages(prices, periods=[5, 10, 20, 50]):
    """Calculate moving averages with fallback for short data"""
    mas = {}
    for period in periods:
        if len(prices) >= period:
            mas[f'ma{period}'] = prices.tail(period).mean()
        elif len(prices) >= 3:
            # Use available data
            mas[f'ma{period}'] = prices.mean()
        else:
            mas[f'ma{period}'] = None
    return mas

def get_historical_data(company_id, days=200):
    """Fetch historical OHLCV data for a company"""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    res = supabase.table('historical_data') \
        .select('trade_date, open_price, high_price, low_price, price, volume') \
        .eq('company_id', company_id) \
        .execute()
    
    if not res.data:
        return None
    
    df = pd.DataFrame(res.data)
    df = df.sort_values('trade_date')
    df = df.rename(columns={
        'trade_date': 'date',
        'open_price': 'open',
        'high_price': 'high',
        'low_price': 'low',
        'price': 'close',
        'volume': 'volume'
    })
    df['close'] = pd.to_numeric(df['close'])
    return df

def get_latest_historical_id(company_id):
    """Get the latest historical_data ID for a company"""
    res = supabase.table('historical_data') \
        .select('id, trade_date') \
        .eq('company_id', company_id) \
        .execute()
    
    if res.data:
        latest = max(res.data, key=lambda x: x['trade_date'])
        return latest['id']
    return None

def process_company(company_id, symbol):
    """Process a single company with fallback for limited data"""
    print(f"Processing {symbol}...", end=" ")
    
    df = get_historical_data(company_id, days=200)
    if df is None or len(df) < 5:
        print(f"❌ No data")
        return False
    
    rows = len(df)
    print(f"({rows} rows)", end=" ")
    
    historical_id = get_latest_historical_id(company_id)
    if not historical_id:
        print(f"❌ No historical_id")
        return False
    
    # Calculate indicators with fallbacks
    rsi = calculate_rsi(df['close'])
    macd, signal, hist = calculate_macd(df['close'])
    mas = calculate_moving_averages(df['close'])
    
    # Prepare data
    data = {
        'historical_data_id': historical_id,
        'rsi': float(rsi) if rsi else None,
        'macd_line': float(macd) if macd else None,
        'signal_line': float(signal) if signal else None,
        'histogram': float(hist) if hist else None,
        'mm5': float(mas['ma5']) if mas['ma5'] else None,
        'mm10': float(mas['ma10']) if mas['ma10'] else None,
        'mm20': float(mas['ma20']) if mas['ma20'] else None,
        'mm50': float(mas['ma50']) if mas['ma50'] else None,
    }
    
    # Check if record exists
    existing = supabase.table('technical_analysis') \
        .select('id') \
        .eq('historical_data_id', historical_id) \
        .execute()
    
    try:
        if existing.data:
            supabase.table('technical_analysis') \
                .update(data) \
                .eq('id', existing.data[0]['id']) \
                .execute()
        else:
            supabase.table('technical_analysis').insert(data).execute()
        
        print(f"✅ RSI={rsi:.1f}" if rsi else f"✅ (no RSI)")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("=" * 60)
    print("Technical Analyzer - ALL 47 Companies")
    print("=" * 60)
    
    # Get all companies
    res = supabase.table('companies').select('id, symbol').execute()
    companies = res.data
    print(f"Found {len(companies)} companies\n")
    
    success = 0
    for company in companies:
        if process_company(company['id'], company['symbol']):
            success += 1
    
    print(f"\n✅ Completed: {success}/{len(companies)} companies processed")

if __name__ == "__main__":
    main()
