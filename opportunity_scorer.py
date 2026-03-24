#!/usr/bin/env python3
"""
opportunity_scorer.py
Calculates a composite opportunity score for each BRVM company and saves to Supabase.
"""

import os
import sys
from datetime import datetime, timedelta
import logging

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

# ============================================
# CONFIGURATION - MATCHES YOUR SCHEMA
# ============================================
COMPANIES_TABLE = 'companies'
HISTORICAL_TABLE = 'historical_data'
TECHNICAL_TABLE = 'technical_analysis'
FUNDAMENTAL_TABLE = 'fundamental_analysis'
OPPORTUNITIES_TABLE = 'opportunities'
MONTHLY_VOLUME_TABLE = 'monthly_volume_avg'

# Column mappings based on your schema
SYMBOL_COLUMN = 'symbol'
COMPANY_ID_COLUMN = 'company_id'
DATE_COLUMN = 'trade_date'
CLOSE_COLUMN = 'price'
VOLUME_COLUMN = 'volume'

# ============================================
# WEIGHTS
# ============================================
WEIGHT_TECH = 0.40
WEIGHT_FUND = 0.30
WEIGHT_LIQ = 0.20
WEIGHT_TREND = 0.10


def get_company_mapping():
    """Get mapping from symbol to company_id."""
    try:
        res = supabase.table(COMPANIES_TABLE).select('id, symbol').execute()
        if not res.data:
            logger.error(f"No data found in {COMPANIES_TABLE}")
            return {}
        mapping = {row['symbol']: row['id'] for row in res.data}
        logger.info(f"Found {len(mapping)} companies")
        return mapping
    except Exception as e:
        logger.error(f"Error fetching companies: {e}")
        return {}


def get_latest_technical(company_id):
    """Fetch the latest technical analysis for a company."""
    try:
        res = supabase.table(TECHNICAL_TABLE) \
            .select('*') \
            .eq('company_id', company_id) \
            .order('date', desc=True) \
            .limit(1) \
            .execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.debug(f"Technical data not available for company_id {company_id}: {e}")
        return None


def get_latest_fundamental(company_id):
    """Fetch the latest fundamental analysis for a company."""
    try:
        res = supabase.table(FUNDAMENTAL_TABLE) \
            .select('*') \
            .eq('company_id', company_id) \
            .order('analysis_timestamp', desc=True) \
            .limit(1) \
            .execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.debug(f"Fundamental data not available for company_id {company_id}: {e}")
        return None


def get_liquidity_score(company_id):
    """Calculate liquidity score based on recent volume vs historical monthly average."""
    try:
        current_month = datetime.now().month
        
        # Get historical monthly average for this month
        res = supabase.table(MONTHLY_VOLUME_TABLE) \
            .select('hist_avg_volume') \
            .eq('company_id', company_id) \
            .eq('month', current_month) \
            .execute()
        
        if not res.data or res.data[0]['hist_avg_volume'] == 0:
            return 50.0
        
        hist_avg = res.data[0]['hist_avg_volume']
        
        # Get volume for last 10 days
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=10)
        
        res_vol = supabase.table(HISTORICAL_TABLE) \
            .select(VOLUME_COLUMN) \
            .eq(COMPANY_ID_COLUMN, company_id) \
            .gte(DATE_COLUMN, start_date.isoformat()) \
            .lte(DATE_COLUMN, end_date.isoformat()) \
            .execute()
        
        if not res_vol.data:
            return 50.0
        
        # Take last 5 non-zero volumes
        volumes = [row[VOLUME_COLUMN] for row in res_vol.data if row.get(VOLUME_COLUMN, 0) > 0]
        if not volumes:
            return 50.0
        
        recent_volumes = volumes[:5]
        recent_avg = sum(recent_volumes) / len(recent_volumes)
        
        # Calculate ratio and convert to score
        ratio = recent_avg / hist_avg if hist_avg > 0 else 1.0
        # Score: 100 at ratio >= 2.0, 0 at ratio <= 0.5, linear in between
        score = min(100, max(0, (ratio - 0.5) * (100 / 1.5)))
        
        return round(score, 2)
        
    except Exception as e:
        logger.error(f"Error calculating liquidity score for company_id {company_id}: {e}")
        return 50.0


def get_trend_score(company_id):
    """Calculate long-term trend score based on 3 years of historical prices."""
    try:
        # Get last 3 years of data
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=3*365)
        
        res = supabase.table(HISTORICAL_TABLE) \
            .select(f'{DATE_COLUMN}, {CLOSE_COLUMN}') \
            .eq(COMPANY_ID_COLUMN, company_id) \
            .gte(DATE_COLUMN, start_date.isoformat()) \
            .lte(DATE_COLUMN, end_date.isoformat()) \
            .order(DATE_COLUMN, asc=True) \
            .execute()
        
        if len(res.data) < 20:
            return 50.0
        
        # Aggregate to monthly data
        monthly_prices = {}
        for row in res.data:
            month_key = row[DATE_COLUMN][:7]
            monthly_prices[month_key] = row[CLOSE_COLUMN]
        
        prices = list(monthly_prices.values())
        
        if len(prices) < 12:
            return 50.0
        
        # Simple linear regression
        n = len(prices)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(prices) / n
        
        numerator = sum((x[i] - x_mean) * (prices[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 50.0
        
        slope = numerator / denominator
        
        # Annualize slope and normalize by average price
        price_avg = y_mean
        if price_avg == 0:
            return 50.0
        
        annual_slope = slope * 12
        relative_slope = annual_slope / price_avg
        
        # Convert to score: 0 for -50% annual decline, 100 for +50% annual growth
        clamped_slope = max(-0.5, min(0.5, relative_slope))
        score = (clamped_slope + 0.5) * 100
        
        return round(score, 2)
        
    except Exception as e:
        logger.error(f"Error calculating trend score for company_id {company_id}: {e}")
        return 50.0


def compute_technical_score(tech_data):
    """Convert technical indicators into a score out of 100."""
    if not tech_data:
        return 0.0
    
    score = 0.0
    
    # RSI
    rsi = tech_data.get('rsi')
    if rsi is not None:
        rsi_score = min(100, max(0, (rsi - 30) * (100 / 40)))
        score += 0.4 * rsi_score
    else:
        score += 0.4 * 50
    
    # MACD
    macd = tech_data.get('macd')
    signal = tech_data.get('macd_signal')
    if macd is not None and signal is not None:
        macd_score = 100 if macd > signal else 0
        score += 0.3 * macd_score
    else:
        score += 0.3 * 50
    
    # Moving averages
    close = tech_data.get('close')
    ma20 = tech_data.get('ma20')
    ma50 = tech_data.get('ma50')
    if close and ma20 and ma50:
        ma_score = 0.0
        if close > ma20:
            ma_score += 50
        if close > ma50:
            ma_score += 50
        score += 0.3 * ma_score
    else:
        score += 0.3 * 50
    
    return round(score, 2)


def compute_fundamental_score(fund_data):
    """Convert fundamental analysis into a score out of 100."""
    if not fund_data:
        return 50.0
    return 70.0


def main():
    """Main execution function."""
    
    # Get company mapping
    company_mapping = get_company_mapping()
    if not company_mapping:
        logger.error("No companies found. Check your companies table.")
        sys.exit(1)
    
    logger.info(f"Processing {len(company_mapping)} companies")
    
    opportunities = []
    
    for symbol, company_id in company_mapping.items():
        tech = get_latest_technical(company_id)
        fund = get_latest_fundamental(company_id)
        
        tech_score = compute_technical_score(tech)
        fund_score = compute_fundamental_score(fund)
        liq_score = get_liquidity_score(company_id)
        trend_score = get_trend_score(company_id)
        
        total_score = round(
            WEIGHT_TECH * tech_score +
            WEIGHT_FUND * fund_score +
            WEIGHT_LIQ * liq_score +
            WEIGHT_TREND * trend_score,
            2
        )
        
        opp = {
            'symbol': symbol,
            'score': total_score,
            'technical_score': tech_score,
            'fundamental_score': fund_score,
            'liquidity_score': liq_score,
            'trend_score': trend_score,
            'sentiment_score': None,
            'signal': None,
            'components': {
                'technical': tech_score,
                'fundamental': fund_score,
                'liquidity': liq_score,
                'trend': trend_score,
                'weights': {
                    'technical': WEIGHT_TECH,
                    'fundamental': WEIGHT_FUND,
                    'liquidity': WEIGHT_LIQ,
                    'trend': WEIGHT_TREND
                }
            },
            'last_updated': datetime.utcnow().isoformat()
        }
        opportunities.append(opp)
        
        logger.info(f"{symbol}: tech={tech_score}, fund={fund_score}, liq={liq_score}, trend={trend_score} -> total={total_score}")
    
    # Insert into opportunities table
    try:
        # Clear old records
        supabase.table(OPPORTUNITIES_TABLE).delete().neq('id', 0).execute()
        # Insert new records
        supabase.table(OPPORTUNITIES_TABLE).insert(opportunities).execute()
        logger.info(f"Successfully inserted {len(opportunities)} opportunity records")
    except Exception as e:
        logger.error(f"Error inserting opportunities: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()