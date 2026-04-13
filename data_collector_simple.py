#!/usr/bin/env python3
"""
data_collector_simple.py - Simplified data collector using direct HTTP requests
"""

import os
import sys
import re
import logging
import requests
import urllib3
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv

# Disable SSL warnings for BRVM (they have certificate issues)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

BULLETIN_URLS = [f"https://www.brvm.org/en/cours-actions/{i}" for i in range(7)]

def parse_number(value):
    if not value:
        return None
    cleaned = str(value).strip()
    cleaned = cleaned.replace(' ', '').replace(',', '.')
    if '%' in cleaned:
        cleaned = cleaned.replace('%', '')
    try:
        return float(cleaned)
    except ValueError:
        return None

def get_company_mapping():
    """Get mapping from symbol to company_id using direct HTTP"""
    url = f"{SUPABASE_URL}/rest/v1/companies?select=id,symbol"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        companies = response.json()
        return {row['symbol']: row['id'] for row in companies}
    return {}

def scrape_all_data():
    all_data = []
    from datetime import datetime as _dt
    session_date = _dt.now().date().isoformat()
    
    for url in BULLETIN_URLS:
        logger.info(f"Fetching data from {url}")
        try:
            response = requests.get(url, timeout=30, verify=False)
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            continue
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get session date from first successful fetch
        if not session_date:
            date_match_url = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', response.text)
            if date_match_url:
                day, month, year = date_match_url.groups()
                months = {'January': '01', 'February': '02', 'March': '03', 'April': '04',
                          'May': '05', 'June': '06', 'July': '07', 'August': '08',
                          'September': '09', 'October': '10', 'November': '11', 'December': '12'}
                month_num = months.get(month, '03')
                session_date = f"{year}-{month_num}-{int(day):02d}"
        
        # Find the largest table (main data table)
        tables = soup.find_all('table')
        target_table = max(tables, key=lambda t: len(t.find_all('tr'))) if tables else None
        
        if not target_table:
            logger.warning(f"No table found at {url}")
            continue
    
        # Parse rows for this sector
        rows = target_table.find_all('tr')
        
        for row in rows[1:]:
            cells = row.find_all('td')
            if len(cells) >= 7:
                symbol = cells[0].get_text(strip=True)
                volume_text = cells[2].get_text(strip=True) if len(cells) > 2 else None
                close_price_text = cells[5].get_text(strip=True) if len(cells) > 5 else None
                
                volume = parse_number(volume_text)
                close_price = parse_number(close_price_text)
                if symbol and close_price:
                    all_data.append({
                        'symbol': symbol,
                        'price': close_price,
                        'volume': int(volume) if volume else 0,
                        'trade_date': session_date
                    })
    
    if not session_date:
        session_date = __import__('datetime').datetime.now().date().isoformat()
    
    logger.info(f"Scraped {len(all_data)} symbols across all sectors")
    return all_data, session_date

def insert_data(data, session_date, company_map):
    if not data:
        return 0
    
    # Delete existing records for this date
    logger.info(f"Deleting existing records for {session_date}...")
    url = f"{SUPABASE_URL}/rest/v1/historical_data?trade_date=eq.{session_date}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    requests.delete(url, headers=headers)
    
    # Insert new records
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
            'open_price': item['price'],
            'high_price': item['price'],
            'low_price': item['price'],
            'volume': item['volume'],
        })
    
    if records:
        url = f"{SUPABASE_URL}/rest/v1/historical_data"
        response = requests.post(url, headers=headers, json=records)
        if response.status_code == 201:
            logger.info(f"Inserted {len(records)} records for {session_date}")
            return len(records)
        else:
            logger.error(f"Failed to insert: {response.status_code}")
            return 0
    
    return 0

def main():
    logger.info("=" * 60)
    logger.info("BRVM Data Collector - Simple HTTP Version (SSL disabled)")
    logger.info("=" * 60)
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("SUPABASE_URL or SUPABASE_KEY not set in environment")
        sys.exit(1)
    
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
