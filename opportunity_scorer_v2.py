#!/usr/bin/env python3
"""
opportunity_scorer_v2.py
Calculates opportunity scores using actual technical data from technical_analysis table.
"""

import os
import sys
from datetime import datetime, timedelta
import logging

from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

WEIGHT_TECH = 0.40
WEIGHT_FUND = 0.30
WEIGHT_LIQ = 0.20
WEIGHT_TREND = 0.10

def get_technical_score(company_id):
    """Get the latest technical analysis for a company"""
    try:
        # First get the latest historical_data_id for this company
        hist_res = supabase.table('historical_data') \
            .select('id') \
            .eq('company_id', company_id) \
            .order('trade_date', desc=True) \
            .limit(1) \
            .execute()
        
        if not hist_res.data:
            return 0.0
        
        historical_id = hist_res.data[0]['id']
        
        # Get technical analysis for that historical_id
        tech_res = supabase.table('technical_analysis') \
            .select('rsi, macd_line, signal_line, mm20, mm50') \
            .eq('historical_data_id', historical_id) \
            .execute()
        
        if not tech_res.data:
            return 0.0
        
        tech = tech_res.data[0]
        
        # Calculate score from technical indicators
        score = 0.0
        weight_sum = 0
        
        # RSI: 0-100, higher is better up to 70
        if tech.get('rsi'):
            rsi = tech['rsi']
            if rsi < 30:
                rsi_score = 0
            elif rsi > 80:
                rsi_score = 0
            elif rsi > 70:
                rsi_score = 50
            else:
                rsi_score = (rsi - 30) * (100 / 40)
            score += rsi_score * 0.4
            weight_sum += 0.4
        
        # MACD: bullish if macd > signal
        if tech.get('macd_line') and tech.get('signal_line'):
            macd_score = 100 if tech['macd_line'] > tech['signal_line'] else 0
            score += macd_score * 0.3
            weight_sum += 0.3
        
        # Moving averages: price above MA is good
        price_res = supabase.table('historical_data') \
            .select('price') \
            .eq('id', historical_id) \
            .execute()
        
        if price_res.data:
            price = price_res.data[0]['price']
            ma_score = 0
            ma_count = 0
            for ma in ['mm20', 'mm50']:
                if tech.get(ma) and tech[ma]:
                    if price > tech[ma]:
                        ma_score += 100
                    else:
                        ma_score += 0
                    ma_count += 1
            
            if ma_count > 0:
                score += (ma_score / ma_count) * 0.3
                weight_sum += 0.3
        
        if weight_sum > 0:
            return round(score / weight_sum, 2)
        return 0.0
        
    except Exception as e:
        logger.error(f"Error getting technical score for company {company_id}: {e}")
        return 0.0

def get_fundamental_score(company_id):
    """Get fundamental score from analysis_text"""
    try:
        res = supabase.table('fundamental_analysis') \
            .select('analysis_text') \
            .eq('company_id', company_id) \
            .order('analysis_timestamp', desc=True) \
            .limit(1) \
            .execute()
        
        if res.data:
            text = res.data[0].get('analysis_text', '')
            if 'ACHAT' in text or 'BUY' in text:
                return 80.0
            elif 'CONSERVER' in text or 'HOLD' in text:
                return 60.0
            elif 'VENDRE' in text or 'SELL' in text:
                return 30.0
            return 50.0
        return 50.0
    except Exception as e:
        return 50.0

def get_liquidity_score(company_id):
    """Calculate liquidity based on recent volume"""
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        
        res = supabase.table('historical_data') \
            .select('volume') \
            .eq('company_id', company_id) \
            .gte('trade_date', start_date.isoformat()) \
            .execute()
        
        volumes = [r['volume'] for r in res.data if r.get('volume')]
        if volumes:
            avg_volume = sum(volumes) / len(volumes)
            if avg_volume > 10000:
                return 100.0
            elif avg_volume > 5000:
                return 75.0
            elif avg_volume > 1000:
                return 50.0
            elif avg_volume > 500:
                return 25.0
            else:
                return 10.0
        return 50.0
    except Exception as e:
        return 50.0

def get_trend_score(company_id):
    """Calculate trend based on 90-day price movement"""
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=90)
        
        res = supabase.table('historical_data') \
            .select('price') \
            .eq('company_id', company_id) \
            .gte('trade_date', start_date.isoformat()) \
            .order('trade_date', asc=True) \
            .execute()
        
        if len(res.data) >= 2:
            first_price = res.data[0]['price']
            last_price = res.data[-1]['price']
            if first_price and last_price and first_price > 0:
                change = (last_price - first_price) / first_price
                score = min(100, max(0, (change + 0.2) * 250))
                return round(score, 2)
        return 50.0
    except Exception as e:
        return 50.0

def main():
    logger.info("=" * 60)
    logger.info("Opportunity Scorer V2 - Using Real Technical Data")
    logger.info("=" * 60)
    
    # Get all companies
    res = supabase.table('companies').select('id, symbol').execute()
    companies = res.data
    logger.info(f"Found {len(companies)} companies")
    
    opportunities = []
    for company in companies:
        company_id = company['id']
        symbol = company['symbol']
        
        tech_score = get_technical_score(company_id)
        fund_score = get_fundamental_score(company_id)
        liq_score = get_liquidity_score(company_id)
        trend_score = get_trend_score(company_id)
        
        total_score = round(
            WEIGHT_TECH * tech_score +
            WEIGHT_FUND * fund_score +
            WEIGHT_LIQ * liq_score +
            WEIGHT_TREND * trend_score,
            2
        )
        
        logger.info(f"{symbol}: tech={tech_score}, fund={fund_score}, liq={liq_score}, trend={trend_score} -> total={total_score}")
        
        opportunities.append({
            'symbol': symbol,
            'score': total_score,
            'technical_score': tech_score,
            'fundamental_score': fund_score,
            'liquidity_score': liq_score,
            'trend_score': trend_score,
            'sentiment_score': None,
            'components': {
                'technical': tech_score,
                'fundamental': fund_score,
                'liquidity': liq_score,
                'trend': trend_score
            },
            'last_updated': datetime.utcnow().isoformat()
        })
    
    # Clear and insert
    supabase.table('opportunities').delete().neq('id', 0).execute()
    supabase.table('opportunities').insert(opportunities).execute()
    logger.info(f"✅ Inserted {len(opportunities)} opportunity records")

if __name__ == "__main__":
    main()
