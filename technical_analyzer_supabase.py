#!/usr/bin/env python3
"""
technical_analyzer_supabase.py
Calculates technical indicators for all BRVM companies using Supabase.
"""

import os
import sys
import logging
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase connection
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables missing")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def calculate_rsi(prices, period=14):
    """Calculate Relative Strength Index."""
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
    """Calculate MACD, Signal Line, and Histogram."""
    if len(prices) < slow + signal:
        return None, None, None
    
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]


def calculate_moving_averages(prices, periods=[5, 10, 20, 50]):
    """Calculate multiple moving averages."""
    mas = {}
    for period in periods:
        if len(prices) >= period:
            mas[f'ma{period}'] = prices.tail(period).mean()
        else:
            mas[f'ma{period}'] = None
    return mas


def calculate_bollinger_bands(prices, period=20, num_std=2):
    """Calculate Bollinger Bands."""
    if len(prices) < period:
        return None, None, None
    
    ma = prices.tail(period).mean()
    std = prices.tail(period).std()
    
    upper = ma + (std * num_std)
    lower = ma - (std * num_std)
    
    return ma, upper, lower


def calculate_stochastic(df, k_period=14, d_period=3):
    """Calculate Stochastic Oscillator."""
    if len(df) < k_period:
        return None, None
    
    low_min = df['low'].rolling(window=k_period).min()
    high_max = df['high'].rolling(window=k_period).max()
    
    k = 100 * ((df['close'] - low_min) / (high_max - low_min))
    d = k.rolling(window=d_period).mean()
    
    return k.iloc[-1], d.iloc[-1]


def get_historical_data(company_id, days=200):
    """Fetch historical OHLCV data for a company."""
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
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        return df
        
    except Exception as e:
        logger.error(f"Error fetching data for company_id {company_id}: {e}")
        return None


def get_latest_historical_id(company_id):
    """Get the latest historical_data ID for a company."""
    try:
        res = supabase.table('historical_data') \
            .select('id') \
            .eq('company_id', company_id) \
            .order('trade_date', ascending=False) \
            .limit(1) \
            .execute()
        
        if res.data:
            return res.data[0]['id']
        return None
    except Exception as e:
        logger.error(f"Error getting latest historical_id for {company_id}: {e}")
        return None


def save_technical_analysis(historical_data_id, indicators):
    """Save technical analysis results to database."""
    try:
        existing = supabase.table('technical_analysis') \
            .select('id') \
            .eq('historical_data_id', historical_data_id) \
            .execute()
        
        data = {
            'historical_data_id': historical_data_id,
            'rsi': indicators.get('rsi'),
            'macd_line': indicators.get('macd_line'),
            'signal_line': indicators.get('signal_line'),
            'histogram': indicators.get('histogram'),
            'macd_decision': indicators.get('macd_decision'),
            'mm5': indicators.get('ma5'),
            'mm10': indicators.get('ma10'),
            'mm20': indicators.get('ma20'),
            'mm50': indicators.get('ma50'),
            'bollinger_central': indicators.get('bollinger_mid'),
            'bollinger_superior': indicators.get('bollinger_upper'),
            'bollinger_inferior': indicators.get('bollinger_lower'),
            'stochastic_k': indicators.get('stoch_k'),
            'stochastic_d': indicators.get('stoch_d')
        }
        
        if existing.data:
            supabase.table('technical_analysis') \
                .update(data) \
                .eq('id', existing.data[0]['id']) \
                .execute()
        else:
            supabase.table('technical_analysis').insert(data).execute()
            
        return True
        
    except Exception as e:
        logger.error(f"Error saving technical analysis: {e}")
        return False


def process_company(company_id, symbol):
    """Process a single company: calculate and save technical indicators."""
    logger.info(f"Processing {symbol} (ID: {company_id})...")
    
    df = get_historical_data(company_id, days=200)
    if df is None or len(df) < 50:
        logger.warning(f"Not enough data for {symbol}")
        return False
    
    historical_id = get_latest_historical_id(company_id)
    if not historical_id:
        logger.warning(f"Cannot find historical_data_id for {symbol}")
        return False
    
    indicators = {}
    
    rsi = calculate_rsi(df['close'], period=14)
    indicators['rsi'] = round(rsi, 2) if rsi else None
    
    macd, signal, hist = calculate_macd(df['close'])
    indicators['macd_line'] = round(macd, 2) if macd else None
    indicators['signal_line'] = round(signal, 2) if signal else None
    indicators['histogram'] = round(hist, 2) if hist else None
    
    if macd and signal:
        indicators['macd_decision'] = 'BUY' if macd > signal else 'SELL'
    else:
        indicators['macd_decision'] = None
    
    mas = calculate_moving_averages(df['close'], periods=[5, 10, 20, 50])
    for period, value in mas.items():
        indicators[period] = round(value, 2) if value else None
    
    mid, upper, lower = calculate_bollinger_bands(df['close'])
    indicators['bollinger_mid'] = round(mid, 2) if mid else None
    indicators['bollinger_upper'] = round(upper, 2) if upper else None
    indicators['bollinger_lower'] = round(lower, 2) if lower else None
    
    stoch_k, stoch_d = calculate_stochastic(df)
    indicators['stoch_k'] = round(stoch_k, 2) if stoch_k else None
    indicators['stoch_d']
