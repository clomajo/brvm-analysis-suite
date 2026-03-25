#!/usr/bin/env python3
"""
data_collector_supabase.py
Scrapes BRVM daily bulletin and inserts data into Supabase.
Replaces the old PostgreSQL-based data collector.
"""

import os
import sys
import re
import logging
from datetime import datetime, date
import requests
from bs4 import BeautifulSoup
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
    logger.error("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# BRVM bulletin URL
BULLETIN_URL = "https://www.brvm.org/en/volumes/0"

def parse_number(value):
    """Convert string like '35 000' or '35,000' to float"""
    if not value:
        return None
    # Remove spaces, replace comma with dot, handle negative numbers
    cleaned = str(value).strip()
    cleaned = cleaned.replace(' ', '').replace(',', '.')
    # Handle negative numbers like '-1,64%' -> -1.64
    if '%' in cleaned:
        cleaned = cleaned.replace('%', '')
    try:
        return float(cleaned)
    except ValueError:
        return None

def get_company_mapping():
    """Get mapping from symbol to company_id"""
    try:
        res = supabase.table('companies').select('id, symbol').execute()
        return {row['symbol']: row['id'] for row in res.data}
    except Exception as e:
        logger.error(f"Error fetching companies: {e}")
        return {}

def get_existing_dates():
    """Get set of existing trade dates to avoid duplicates"""
    try:
        res = supabase.table('historical_data').select('trade_date').execute()
        return {row['trade_date'] for row in res.data}
    except Exception as e:
        logger.error(f"Error fetching existing dates: {e}")
        return set()

def scrape_bulletin():
    """Scrape the BRVM daily bulletin"""
    logger.info(f"Fetching bulletin from {BULLETIN_URL}")
    
    try:
        response = requests.get(BULLETIN_URL, timeout=30)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Error fetching bulletin: {e}")
        return None, None
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find the table with volumes/values
    table = soup.find('table')
    if not table:
        logger.error("No table found on page")
        return None, None
    
    # Parse session date from page
    session_info = soup.find(string=re.compile(r'Session closed|Session ouverte'))
    session_date = None
    if session_info:
        date_match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', session_info)
        if date_match:
            # Simple date parsing - you may need to handle month names
            session_date = datetime.now().date().isoformat()
        else:
            session_date = datetime.now().date().isoformat()
    else:
        session_date = datetime.now().date().isoformat()
    
    # Parse table rows
    rows = table.find_all('tr')
    data = []
    
    for row in rows[1:]:  # Skip header row
        cells = row.find_all('td')
        if len(cells) >= 2:
            symbol_cell = cells[0].get_text(strip=True)
            # Symbol is usually the first column, sometimes with spaces
            symbol = symbol_cell.split()[0] if symbol_cell else None
            
            # Look for price in other cells (usually the second or third column)
            price = None
            for cell in cells[1:]:
                cell_text = cell.get_text(strip=True)
                # Check if it looks like a price (numbers with spaces)
                if re.match(r'^[\d\s]+$', cell_text.replace(' ', '')):
                    price = parse_number(cell_text)
                    break
            
            if symbol and price:
                data.append({
                    'symbol': symbol,
                    'price': price,
                    'trade_date': session_date
                })
    
    return data, session_date

def get_previous_close(symbol, trade_date):
    """Get the previous closing price for a symbol"""
    try:
        res = supabase.table('historical_data') \
            .select('price') \
            .eq('symbol', symbol) \
            .lt('trade_date', trade_date) \
            .order('trade_date', desc=True) \
            .limit(1) \
            .execute()
        
        if res.data:
            return res.data[0]['price']
        return None
    except Exception as e:
        logger.debug(f"Error getting previous close for {symbol}: {e}")
        return None

def insert_data(data, session_date, company_map):
    """Insert scraped data into Supabase"""
    if not data:
        logger.warning("No data to insert")
        return 0
    
    existing_dates = get_existing_dates()
    
    # Check if this date already exists
    if session_date in existing_dates:
        logger.info(f"Data for {session_date} already exists, skipping")
        return 0
    
    records = []
    for item in data:
        symbol = item['symbol']
        if symbol not in company_map:
            logger.warning(f"Symbol {symbol} not found in database, skipping")
            continue
        
        company_id = company_map[symbol]
        price = item['price']
        
        # Get previous close for change calculation (optional)
        prev_close = get_previous_close(symbol, session_date)
        
        record = {
            'company_id': company_id,
            'trade_date': session_date,
            'price': price,
            'open_price': price,  # Fallback if not available
            'high_price': price,   # Fallback
            'low_price': price,    # Fallback
            'volume': 0,           # Default if not available
        }
        records.append(record)
    
    if not records:
        logger.warning("No valid records to insert")
        return 0
    
    # Insert in batches
    batch_size = 100
    inserted = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        try:
            supabase.table('historical_data').insert(batch).execute()
            inserted += len(batch)
            logger.info(f"Inserted {inserted}/{len(records)} records")
        except Exception as e:
            logger.error(f"Error inserting batch: {e}")
            # Try one by one
            for record in batch:
                try:
                    supabase.table('historical_data').insert(record).execute()
                    inserted += 1
                except Exception as e2:
                    logger.error(f"Failed to insert {record['symbol']} for {record['trade_date']}: {e2}")
    
    return inserted

def main():
    logger.info("=" * 60)
    logger.info("BRVM Data Collector (Supabase Version)")
    logger.info("=" * 60)
    
    # Get company mapping
    company_map = get_company_mapping()
    logger.info(f"Found {len(company_map)} companies in database")
    
    # Scrape bulletin
    data, session_date = scrape_bulletin()
    
    if not data:
        logger.error("No data scraped. Check the bulletin URL.")
        sys.exit(1)
    
    logger.info(f"Scraped {len(data)} symbols for date {session_date}")
    
    # Insert data
    inserted = insert_data(data, session_date, company_map)
    
    logger.info(f"Completed: {inserted} records inserted for {session_date}")

if __name__ == "__main__":
    main()
