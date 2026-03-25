#!/usr/bin/env python3
"""
data_collector_fixed.py
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
    """Scrape all stock data from the full table (Table 3)"""
    logger.info(f"Fetching data from {BULLETIN_URL}")
    
    response = requests.get(BULLETIN_URL, timeout=30)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all tables and target the one with 48 rows (full data)
    tables = soup.find_all('table')
    target_table = None
    for table in tables:
        rows = table.find_all('tr')
        if len(rows) > 40:  # The full table has 48 rows
            target_table = table
            break
    
    if not target_table:
        logger.error("Could not find the full data table")
        return None, None
    
    # Get session date from page
    session_date = datetime.now().date().isoformat()
    date_match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', response.text)
    if date_match:
        day, month, year = date_match.groups()
        try:
            # Simple month mapping
            months = {
                'January': '01', 'February': '02', 'March': '03', 'April': '04',
                'May': '05', 'June': '06', 'July': '07', 'August': '08',
                'September': '09', 'October': '10', 'November': '11', 'December': '12'
            }
            month_num = months.get(month, '03')
            session_date = f"{year}-{month_num}-{int(day):02d}"
        except:
            pass
    
    # Parse table rows
    rows = target_table.find_all('tr')
    data = []
    
    for row in rows[1:]:  # Skip header row
        cells = row.find_all('td')
        if len(cells) >= 7:
            symbol = cells[0].get_text(strip=True)
            volume_text = cells[2].get_text(strip=True) if len(cells) > 2 else None
            prev_price_text = cells[3].get_text(strip=True) if len(cells) > 3 else None
            open_price_text = cells[4].get_text(strip=True) if len(cells) > 4 else None
            close_price_text = cells[5].get_text(strip=True) if len(cells) > 5 else None
            
            volume = parse_number(volume_text)
            open_price = parse_number(open_price_text)
            close_price = parse_number(close_price_text)
            
            if symbol and close_price:
                data.append({
                    'symbol': symbol,
                    'price': close_price,
                    'open_price': open_price or close_price,
                    'high_price': close_price,  # We don't have high/low from this table
                    'low_price': close_price,
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
    logger.info("BRVM Data Collector - Full Table (Fixed)")
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
