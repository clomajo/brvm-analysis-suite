#!/usr/bin/env python3
"""
data_collector_v2.py - Improved parser that captures all symbols
"""

import os
import sys
import re
import logging
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BULLETIN_URL = "https://www.brvm.org/en/volumes/0"

def parse_number(value):
    """Convert string like '35 000' to float"""
    if not value:
        return None
    cleaned = str(value).strip()
    cleaned = cleaned.replace(' ', '').replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return None

def get_company_mapping():
    res = supabase.table('companies').select('id, symbol').execute()
    return {row['symbol']: row['id'] for row in res.data}

def scrape_all_data():
    """Scrape all symbols from the bulletin table"""
    logger.info(f"Fetching bulletin from {BULLETIN_URL}")
    
    response = requests.get(BULLETIN_URL, timeout=30)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find the table
    table = soup.find('table')
    if not table:
        logger.error("No table found")
        return None, None
    
    # Get session date from page
    session_date = datetime.now().date().isoformat()
    
    # Find the header to identify columns
    headers = []
    header_row = table.find('tr')
    if header_row:
        for th in header_row.find_all('th'):
            headers.append(th.get_text(strip=True))
    
    logger.info(f"Table headers: {headers}")
    
    # Parse all rows
    data = []
    rows = table.find_all('tr')[1:]  # Skip header
    
    for row in rows:
        cells = row.find_all('td')
        if len(cells) >= 2:
            # First cell is symbol (e.g., "ABJC")
            symbol_cell = cells[0].get_text(strip=True)
            # Extract just the symbol (first word)
            symbol = symbol_cell.split()[0] if symbol_cell else None
            
            # Look for price - usually the second column
            price = None
            if len(cells) >= 2:
                price_text = cells[1].get_text(strip=True)
                # Clean up price text (remove non-numeric)
                price_match = re.search(r'[\d\s,]+', price_text)
                if price_match:
                    price = parse_number(price_match.group())
            
            if symbol and price:
                data.append({
                    'symbol': symbol,
                    'price': price,
                    'trade_date': session_date
                })
    
    logger.info(f"Scraped {len(data)} symbols")
    return data, session_date

def insert_data(data, session_date, company_map):
    if not data:
        return 0
    
    # Check if date already exists
    existing = supabase.table('historical_data').select('trade_date').eq('trade_date', session_date).execute()
    if existing.data:
        logger.info(f"Data for {session_date} already exists ({len(existing.data)} records)")
        return 0
    
    records = []
    for item in data:
        symbol = item['symbol']
        if symbol not in company_map:
            logger.warning(f"Symbol {symbol} not in database")
            continue
        
        records.append({
            'company_id': company_map[symbol],
            'trade_date': session_date,
            'price': item['price'],
            'open_price': item['price'],
            'high_price': item['price'],
            'low_price': item['price'],
            'volume': 0,
        })
    
    if records:
        supabase.table('historical_data').insert(records).execute()
        logger.info(f"Inserted {len(records)} records for {session_date}")
    
    return len(records)

def main():
    logger.info("=" * 60)
    logger.info("BRVM Data Collector - All Symbols")
    logger.info("=" * 60)
    
    company_map = get_company_mapping()
    logger.info(f"Found {len(company_map)} companies")
    
    data, session_date = scrape_all_data()
    if not data:
        logger.error("No data scraped")
        sys.exit(1)
    
    inserted = insert_data(data, session_date, company_map)
    logger.info(f"Completed: {inserted} records inserted")

if __name__ == "__main__":
    main()
