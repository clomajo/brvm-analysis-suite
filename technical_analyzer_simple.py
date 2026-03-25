#!/usr/bin/env python3
"""
technical_analyzer_simple.py - Simplified technical analyzer using direct HTTP
"""

import os
import sys
import logging
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

def supabase_request(method, endpoint, data=None):
    """Make direct HTTP request to Supabase"""
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    if method == "GET":
        response = requests.get(url, headers=headers)
    elif method == "POST":
        response = requests.post(url, headers=headers, json=data)
    elif method == "DELETE":
        response = requests.delete(url, headers=headers)
    else:
        return None
    
    if response.status_code in [200, 201]:
        return response.json() if response.content else []
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

def calculate_macd(prices, fast=12, slow=26, signal=9):
    if len(prices) < slow + signal:
        return None, None, None
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]

def get_historical_data(company_id, days=200):
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    data = supabase_request("GET", f"historical_data?company_id=eq.{company_id}&select=trade_date,price&trade_date=gte.{start_date}&trade_date=lte.{end_date}")
    if not data:
        return None
    
    df = pd.DataFrame(data)
    if df.empty:
        return None
    df = df.sort_values('trade_date')
    df = df.rename(columns={'price': 'close'})
    df['close'] = pd.to_numeric(df['close'])
    return df

def get_latest_historical_id(company_id):
    data = supabase_request("GET", f"historical_data?company_id=eq.{company_id}&select=id,trade_date&order=trade_date.desc&limit=1")
    if data:
        return data[0]['id']
    return None

def process_company(company_id, symbol):
    logger.info(f"Processing {symbol}...")
    
    df = get_historical_data(company_id, days=200)
    if df is None or len(df) < 50:
        logger.warning(f"Not enough data for {symbol}")
        return False
    
    historical_id = get_latest_historical_id(company_id)
    if not historical_id:
        logger.warning(f"No historical_id for {symbol}")
        return False
    
    # Calculate indicators
    rsi = calculate_rsi(df['close'])
    macd, signal, hist = calculate_macd(df['close'])
    
    data = {
        'historical_data_id': historical_id,
        'rsi': round(rsi, 2) if rsi else None,
        'macd_line': round(macd, 2) if macd else None,
        'signal_line': round(signal, 2) if signal else None,
        'histogram': round(hist, 2) if hist else None,
    }
    
    # Check if exists
    existing = supabase_request("GET", f"technical_analysis?historical_data_id=eq.{historical_id}&select=id")
    
    if existing:
        supabase_request("PATCH", f"technical_analysis?id=eq.{existing[0]['id']}", data)
    else:
        supabase_request("POST", "technical_analysis", data)
    
    logger.info(f"✅ {symbol}: RSI={rsi:.2f}" if rsi else f"✅ {symbol}")
    return True

def main():
    logger.info("=" * 60)
    logger.info("Technical Analyzer - Simple HTTP Version")
    logger.info("=" * 60)
    
    # Get all companies
    companies = supabase_request("GET", "companies?select=id,symbol")
    if not companies:
        logger.error("No companies found")
        sys.exit(1)
    
    logger.info(f"Found {len(companies)} companies")
    
    success = 0
    for company in companies:
        if process_company(company['id'], company['symbol']):
            success += 1
    
    logger.info(f"✅ Completed: {success}/{len(companies)} companies processed")

if __name__ == "__main__":
    main()
