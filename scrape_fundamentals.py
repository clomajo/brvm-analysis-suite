"""
scrape_fundamentals.py
Scrape financial data from stockanalysis.com for all BRVM tickers
Stores results in Supabase company_fundamentals table
"""

import os
import re
import json
import time
import requests
import urllib3
from bs4 import BeautifulSoup
from datetime import date
from dotenv import load_dotenv

urllib3.disable_warnings()
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
}

# All 47 BRVM tickers
TICKERS = [
    'ABJC','BICC','BNBC','BOAB','BOABF','BOAC','BOAM','BOAN','BOAS',
    'CABC','CBIBF','CFAC','CIEC','ECOC','ETIT','FTSC','LNBB','NEIC',
    'NSBC','NTLC','ONTBF','ORAC','ORGT','PALC','PRSC','SAFC','SCRC',
    'SDCC','SDSC','SEMC','SGBC','SHEC','SIBC','SICC','SIVC','SLBC',
    'SMBC','SNTS','SOGC','SPHC','STAC','STBC','TTLC','TTLS','UNLC','UNXC'
]

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
})

def parse_number(text):
    """Convert text like '1,923,122' or '35.41%' to float."""
    if not text or text.strip() in ['-', 'N/A', '']:
        return None
    text = text.strip().replace('%', '').replace(',', '')
    try:
        return float(text)
    except:
        return None

def scrape_income_statement(ticker):
    """Scrape income statement from stockanalysis.com."""
    url = f"https://stockanalysis.com/quote/brvm/{ticker}/financials/"
    try:
        r = SESSION.get(url, timeout=20, verify=False)
        if r.status_code != 200:
            print(f"  {ticker}: HTTP {r.status_code}")
            return None

        soup = BeautifulSoup(r.text, 'html.parser')

        # Find the main financial table
        table = soup.find('table')
        if not table:
            print(f"  {ticker}: No table found")
            return None

        # Get headers (fiscal years)
        headers = []
        header_row = table.find('thead')
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all('th')]

        # Get data rows
        data = {}
        tbody = table.find('tbody')
        if not tbody:
            return None

        for row in tbody.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) < 2:
                continue
            metric = cells[0].get_text(strip=True)
            values = [parse_number(c.get_text(strip=True)) for c in cells[1:]]
            data[metric] = values

        # Extract most recent year (index 0 = most recent)
        def get_val(key, idx=0):
            for k, v in data.items():
                if key.lower() in k.lower():
                    if idx < len(v):
                        return v[idx]
            return None

        result = {
            'ticker': ticker,
            'fiscal_year': 'FY2025',
            'revenue': get_val('Revenue', 0),
            'revenue_growth': get_val('Revenue Growth', 0),
            'gross_profit': get_val('Gross Profit', 0),
            'operating_income': get_val('Operating Income', 0),
            'net_income': get_val('Net Income', 0),
            'net_income_growth': get_val('Net Income Growth', 0),
            'eps': get_val('EPS (Basic)', 0),
            'eps_growth': get_val('EPS Growth', 0),
            'dividend_per_share': get_val('Dividend Per Share', 0),
            'gross_margin': get_val('Gross Margin', 0),
            'operating_margin': get_val('Operating Margin', 0),
            'profit_margin': get_val('Profit Margin', 0),
            'ebitda': get_val('EBITDA', 0),
            'ebitda_margin': get_val('EBITDA Margin', 0),
            'free_cash_flow': get_val('Free Cash Flow', 0),
        }

        return result

    except Exception as e:
        print(f"  {ticker}: Exception — {e}")
        return None

def scrape_ratios(ticker):
    """Scrape P/E, ROE, P/B from ratios page."""
    url = f"https://stockanalysis.com/quote/brvm/{ticker}/financials/ratios/"
    try:
        r = SESSION.get(url, timeout=20, verify=False)
        if r.status_code != 200:
            return {}

        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table')
        if not table:
            return {}

        data = {}
        tbody = table.find('tbody')
        if tbody:
            for row in tbody.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    metric = cells[0].get_text(strip=True)
                    value = parse_number(cells[1].get_text(strip=True))
                    data[metric] = value

        result = {}
        for k, v in data.items():
            kl = k.lower()
            if 'p/e' in kl or 'price/earn' in kl:
                result['pe_ratio'] = v
            elif 'p/b' in kl or 'price/book' in kl:
                result['pb_ratio'] = v
            elif 'roe' in kl or 'return on equity' in kl:
                result['roe'] = v
            elif 'roa' in kl or 'return on asset' in kl:
                result['roa'] = v
            elif 'debt/equity' in kl:
                result['debt_to_equity'] = v
            elif 'dividend yield' in kl:
                result['dividend_yield'] = v

        return result

    except Exception as e:
        return {}

def upsert_to_supabase(record):
    """Upsert record to company_fundamentals table."""
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/company_fundamentals",
        headers={**HEADERS, 'Prefer': 'resolution=merge-duplicates'},
        json=record
    )
    return r.status_code

def get_company_ids():
    """Get mapping symbol -> company_id from Supabase."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/companies?select=id,symbol",
        headers=HEADERS
    )
    if r.status_code == 200:
        return {c['symbol']: c['id'] for c in r.json()}
    return {}

def create_table_if_needed():
    """Print SQL to create the table if it doesn't exist."""
    sql = """
-- Run this in Supabase SQL editor if table doesn't exist:
CREATE TABLE IF NOT EXISTS company_fundamentals (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    ticker TEXT,
    fiscal_year TEXT,
    revenue NUMERIC,
    revenue_growth NUMERIC,
    gross_profit NUMERIC,
    operating_income NUMERIC,
    net_income NUMERIC,
    net_income_growth NUMERIC,
    eps NUMERIC,
    eps_growth NUMERIC,
    dividend_per_share NUMERIC,
    gross_margin NUMERIC,
    operating_margin NUMERIC,
    profit_margin NUMERIC,
    ebitda NUMERIC,
    ebitda_margin NUMERIC,
    free_cash_flow NUMERIC,
    pe_ratio NUMERIC,
    pb_ratio NUMERIC,
    roe NUMERIC,
    roa NUMERIC,
    debt_to_equity NUMERIC,
    dividend_yield NUMERIC,
    scraped_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(company_id, fiscal_year)
);
"""
    print(sql)

if __name__ == '__main__':
    print("="*60)
    print("BRVM Fundamentals Scraper — Stock Analysis")
    print(f"Date: {date.today()}")
    print("="*60)

    # First print table creation SQL
    create_table_if_needed()

    # Get company IDs
    company_ids = get_company_ids()
    print(f"\n✅ {len(company_ids)} companies found in Supabase")

    # Test with 5 tickers first
    TEST_TICKERS = ['SNTS', 'BOAC', 'CBIBF', 'BOAB', 'ETIT']
    print(f"\n🔍 Testing with: {TEST_TICKERS}\n")

    results = []
    for ticker in TEST_TICKERS:
        print(f"Scraping {ticker}...")

        # Income statement
        income = scrape_income_statement(ticker)
        if income:
            # Ratios
            time.sleep(1)  # Be polite
            ratios = scrape_ratios(ticker)
            income.update(ratios)

            # Add company_id
            income['company_id'] = company_ids.get(ticker)
            income['scraped_at'] = date.today().isoformat()

            results.append(income)
            print(f"  ✅ Revenue: {income.get('revenue')}, Net Income: {income.get('net_income')}, P/E: {income.get('pe_ratio')}")
        else:
            print(f"  ❌ No data found")

        time.sleep(2)  # Rate limiting

    print(f"\n{'='*60}")
    print(f"Results: {len(results)}/{len(TEST_TICKERS)} tickers scraped")
    print("\nSample data:")
    for r in results:
        print(f"\n{r['ticker']}:")
        print(f"  Revenue: {r.get('revenue')} M FCFA")
        print(f"  Net Income: {r.get('net_income')} M FCFA")
        print(f"  EPS: {r.get('eps')} FCFA")
        print(f"  Dividend/share: {r.get('dividend_per_share')} FCFA")
        print(f"  Operating Margin: {r.get('operating_margin')}%")
        print(f"  P/E: {r.get('pe_ratio')}")
        print(f"  ROE: {r.get('roe')}%")

    print("\n⚠️  Before running full scrape, create the table in Supabase SQL editor (SQL printed above)")
    print("Then uncomment the upsert section below and run: python scrape_fundamentals.py --full")
