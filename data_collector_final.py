#!/usr/bin/env python3
"""
data_collector_final.py
Scrapes full BRVM stock data from the official course page.
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

# URL with full table of all stocks
BULLETIN_URL = "https://www.brvm.org/en/cours-actions/0"

def parse_number(value):
    """Convert string like '35 000' or '35,000' to float"""
    if not value:
        return None
    cleaned = str(value).strip()
    cleaned = cleaned.replace(' ', '').replace(',', '.')
    # Handle negative numbers like '-1,64%'
    if '%' in cleaned:
        cleaned = cleaned.replace('%', '')
    try:
        return float(cleaned)
    except ValueError:
        return None

def get_company_mapping():
    """Get mapping from symbol to company_id"""
    res = supabase.table('companies').select('id, symbol').execute()
    return {row['symbol']: row['id'] for row in res.data}

def scrape_all_data():
    """Scrape all stock data from the full table"""
    logger.info(f"Fetching data from {BULLETIN_URL}")
    
    response = requests.get(BULLETIN_URL, timeout=30)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find the main table
    table = soup.find('table')
    if not table:
        logger.error("No table found on page")
        return None, None
    
    # Get session date from the page
    session_date = datetime.now().date().isoformat()
    # Look for date in page text
    date_match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', response.text)
    if date_match:
        # Parse date from text like "Wednesday, 25 March, 2026"
        day, month, year = date_match.groups()
        try:
            from dateutil import parser
            session_date = parser.parse(f"{day} {month} {year}").date().isoformat()
        except:
            pass
    
    # Parse table rows
    rows = table.find_all('tr')
    data = []
    
    for row in rows[1:]:  # Skip header row
        cells = row.find_all('td')
        if len(cells) >= 6:
            symbol_cell = cells[0].get_text(strip=True)
            symbol = symbol_cell.split()[0] if symbol_cell else None
            
            # Get volume
            volume_text = cells[2].get_text(strip=True) if len(cells) > 2 else None
            volume = parse_number(volume_text) if volume_text else None
            
            # Get previous price
            prev_price_text = cells[3].get_text(strip=True) if len(cells) > 3 else None
            prev_price = parse_number(prev_price_text) if prev_price_text else None
            
            # Get opening price
            open_price_text = cells[4].get_text(strip=True) if len(cells) > 4 else None
            open_price = parse_number(open_price_text) if open_price_text else None
            
            # Get closing price
            close_price_text = cells[5].get_text(strip=True) if len(cells) > 5 else None
            close_price = parse_number(close_price_text) if close_price_text else None
            
            # Get change
            change_text = cells[6].get_text(strip=True) if len(cells) > 6 else None
            change = parse_number(change_text) if change_text else None
            
            if symbol and close_price:
                data.append({
                    'symbol': symbol,
                    'price': close_price,
                    'open_price': open_price or close_price,
                    'high_price': max(open_price or close_price, close_price) if open_price else close_price,
                    'low_price': min(open_price or close_price, close_price) if open_price else close_price,
                    'volume': int(volume) if volume else 0,
                    'trade_date': session_date
                })
    
    logger.info(f"Scraped {len(data)} symbols")
    return data, session_date

def insert_data(data, session_date, company_map):
    """Insert scraped data into Supabase"""
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
            logger.warning(f"Symbol {symbol} not in database, skipping")
            continue
        
        records.append({
            'company_id': company_map[symbol],
            'trade_date': item['trade_date'],
            'price': item['price'],
            'open_price': item['open_price'],
            'high_price': item['high_price'],
            'low_price': item['low_price'],
            'volume': item['volume'],
        })
    
    if records:
        # Insert in batches
        batch_size = 100
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            supabase.table('historical_data').insert(batch).execute()
            logger.info(f"Inserted {min(i+batch_size, len(records))}/{len(records)} records")
        logger.info(f"Inserted {len(records)} records for {session_date}")
    
    return len(records)

def main():
    logger.info("=" * 60)
    logger.info("BRVM Data Collector - Full Table")
    logger.info("=" * 60)
    
    company_map = get_company_mapping()
    logger.info(f"Found {len(company_map)} companies")
    
    data, session_date = scrape_all_data()
    if not data:
        logger.error("No data scraped")
        sys.exit(1)
    
    logger.info(f"Scraped {len(data)} symbols for {session_date}")
    
    inserted = insert_data(data, session_date, company_map)
    logger.info(f"Completed: {inserted} records inserted")

if __name__ == "__main__":
    main()
