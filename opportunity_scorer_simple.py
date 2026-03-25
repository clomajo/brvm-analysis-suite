#!/usr/bin/env python3
"""
opportunity_scorer_simple.py - Simplified opportunity scorer using direct HTTP
"""

import os
import sys
import logging
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

def supabase_request(method, endpoint, data=None):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.request(method, url, headers=headers, json=data)
    if response.status_code in [200, 201]:
        return response.json() if response.content else []
    return None

def get_technical_score(company_id):
    hist = supabase_request("GET", f"historical_data?company_id=eq.{company_id}&select=id&order=trade_date.desc&limit=1")
    if not hist:
        return 50.0
    tech = supabase_request("GET", f"technical_analysis?historical_data_id=eq.{hist[0]['id']}&select=rsi,macd_line,signal_line")
    if not tech:
        return 50.0
    # Simple scoring based on RSI
    rsi = tech[0].get('rsi')
    if rsi:
        if rsi > 70:
            return 80.0
        elif rsi > 50:
            return 60.0
        elif rsi > 30:
            return 40.0
        else:
            return 20.0
    return 50.0

def get_fundamental_score(company_id):
    fund = supabase_request("GET", f"fundamental_analysis?company_id=eq.{company_id}&select=analysis_summary&order=analysis_timestamp.desc&limit=1")
    if fund:
        text = fund[0].get('analysis_summary', '')
        if 'ACHAT' in text:
            return 80.0
        elif 'CONSERVER' in text:
            return 60.0
        elif 'VENDRE' in text:
            return 30.0
    return 50.0

def get_liquidity_score(company_id):
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    data = supabase_request("GET", f"historical_data?company_id=eq.{company_id}&select=volume&trade_date=gte.{start_date}")
    if data:
        volumes = [d['volume'] for d in data if d.get('volume')]
        if volumes:
            avg_vol = sum(volumes) / len(volumes)
            if avg_vol > 10000:
                return 100.0
            elif avg_vol > 5000:
                return 75.0
            elif avg_vol > 1000:
                return 50.0
            elif avg_vol > 500:
                return 25.0
    return 50.0

def get_trend_score(company_id):
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=90)
    data = supabase_request("GET", f"historical_data?company_id=eq.{company_id}&select=price&trade_date=gte.{start_date}&order=trade_date.asc")
    if data and len(data) >= 2:
        first = data[0]['price']
        last = data[-1]['price']
        if first and last and first > 0:
            change = (last - first) / first
            score = min(100, max(0, (change + 0.2) * 250))
            return round(score, 2)
    return 50.0

def get_signal(score):
    if score >= 70:
        return "BUY"
    elif score >= 60:
        return "ACCUMULATE"
    elif score >= 50:
        return "NEUTRAL"
    elif score >= 40:
        return "REDUCE"
    else:
        return "SELL"

def main():
    logger.info("=" * 60)
    logger.info("Opportunity Scorer - Simple HTTP Version")
    logger.info("=" * 60)
    
    companies = supabase_request("GET", "companies?select=id,symbol")
    if not companies:
        logger.error("No companies found")
        sys.exit(1)
    
    logger.info(f"Found {len(companies)} companies")
    
    opportunities = []
    for company in companies:
        company_id = company['id']
        symbol = company['symbol']
        
        tech = get_technical_score(company_id)
        fund = get_fundamental_score(company_id)
        liq = get_liquidity_score(company_id)
        trend = get_trend_score(company_id)
        
        total = round(tech * 0.4 + fund * 0.3 + liq * 0.2 + trend * 0.1, 2)
        signal = get_signal(total)
        
        logger.info(f"{symbol}: tech={tech:.1f}, fund={fund:.1f}, liq={liq:.1f}, trend={trend:.1f} -> total={total:.1f} ({signal})")
        
        opportunities.append({
            'symbol': symbol,
            'score': total,
            'technical_score': tech,
            'fundamental_score': fund,
            'liquidity_score': liq,
            'trend_score': trend,
            'signal': signal,
            'last_updated': datetime.utcnow().isoformat()
        })
    
    # Delete old and insert new
    supabase_request("DELETE", "opportunities?id=neq.0")
    supabase_request("POST", "opportunities", opportunities)
    logger.info(f"✅ Inserted {len(opportunities)} opportunity records")

if __name__ == "__main__":
    main()
