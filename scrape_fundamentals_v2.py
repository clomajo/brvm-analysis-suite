"""
scrape_fundamentals_v2.py
Scrape financial data from stockanalysis.com for all BRVM tickers
Sources:
  - /quote/brvm/TICKER/           → PE, EPS, Dividend, Market Cap
  - /quote/brvm/TICKER/financials/ → Revenue, Net Income, Margins
  - /quote/brvm/TICKER/financials/ratios/ → ROE, PB, Debt/Equity
  - /quote/brvm/TICKER/dividend/  → Dividend history, Ex-date
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

HEADERS_SUPA = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates'
}

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
})

TICKERS = [
    'ABJC','BICC','BNBC','BOAB','BOABF','BOAC','BOAM','BOAN','BOAS',
    'CABC','CBIBF','CFAC','CIEC','ECOC','ETIT','FTSC','LNBB','NEIC',
    'NSBC','NTLC','ONTBF','ORAC','ORGT','PALC','PRSC','SAFC','SCRC',
    'SDCC','SDSC','SEMC','SGBC','SHEC','SIBC','SICC','SIVC','SLBC',
    'SMBC','SNTS','SOGC','SPHC','STAC','STBC','TTLC','TTLS','UNLC','UNXC'
]

def parse_number(text):
    """Convert '1,923,122' or '35.41%' or '2.85T' to float."""
    if not text or str(text).strip() in ['-', 'N/A', '', 'n/a', 'NA']:
        return None
    text = str(text).strip()
    text = text.replace('%', '').replace(',', '').replace('+', '')
    # Handle T/B/M suffixes
    multiplier = 1
    if text.endswith('T'):
        multiplier = 1_000_000
        text = text[:-1]
    elif text.endswith('B'):
        multiplier = 1_000
        text = text[:-1]
    elif text.endswith('M'):
        multiplier = 1
        text = text[:-1]
    try:
        return float(text) * multiplier
    except:
        return None

def get_soup(url):
    """Fetch URL and return BeautifulSoup."""
    try:
        r = SESSION.get(url, timeout=20, verify=False)
        if r.status_code == 200:
            return BeautifulSoup(r.text, 'html.parser')
        else:
            print(f"    HTTP {r.status_code} for {url}")
            return None
    except Exception as e:
        print(f"    Error fetching {url}: {e}")
        return None

def scrape_overview(ticker):
    """
    Scrape overview page for: PE, EPS, Dividend, Market Cap, Beta, RSI
    These appear as key-value pairs in the overview table.
    """
    url = f"https://stockanalysis.com/quote/brvm/{ticker}/"
    soup = get_soup(url)
    if not soup:
        return {}

    result = {}

    # Find all table rows with 2 cells (label: value)
    for row in soup.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) == 2:
            label = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)
            label_lower = label.lower()

            if 'pe ratio' in label_lower or label_lower == 'pe ratio':
                result['pe_ratio'] = parse_number(value)
            elif 'forward pe' in label_lower:
                result['forward_pe'] = parse_number(value)
            elif label_lower == 'eps':
                result['eps'] = parse_number(value)
            elif 'market cap' in label_lower:
                result['market_cap'] = parse_number(value)
            elif label_lower == 'dividend':
                # "1,933.33 (6.78%)" → extract both
                m = re.match(r'([\d,\.]+)\s*\(([\d\.]+)%\)', value)
                if m:
                    result['dividend_per_share'] = parse_number(m.group(1))
                    result['dividend_yield'] = parse_number(m.group(2))
                else:
                    result['dividend_per_share'] = parse_number(value.split('(')[0])
            elif 'beta' in label_lower:
                result['beta'] = parse_number(value)
            elif label_lower == 'rsi':
                result['rsi'] = parse_number(value)
            elif 'revenue' in label_lower and 'ttm' in label_lower:
                result['revenue_ttm'] = parse_number(value)
            elif 'net income' in label_lower:
                result['net_income_ttm'] = parse_number(value)
            elif 'shares out' in label_lower:
                result['shares_outstanding'] = parse_number(value)
            elif 'ex-dividend' in label_lower or 'ex-div' in label_lower:
                result['ex_dividend_date'] = value

    return result

def scrape_financials(ticker):
    """
    Scrape income statement for: Revenue, Net Income, EPS, Margins, EBITDA
    Table rows: metric name | FY2025 | FY2024 | ...
    """
    url = f"https://stockanalysis.com/quote/brvm/{ticker}/financials/"
    soup = get_soup(url)
    if not soup:
        return {}

    result = {}
    table = soup.find('table')
    if not table:
        return result

    tbody = table.find('tbody')
    if not tbody:
        return result

    for row in tbody.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 2:
            continue

        # Get metric name — remove any SVG/icon text
        metric = cells[0].get_text(strip=True)
        # Most recent year is cells[1]
        val = parse_number(cells[1].get_text(strip=True))
        # Previous year is cells[2]
        val_prev = parse_number(cells[2].get_text(strip=True)) if len(cells) > 2 else None

        metric_lower = metric.lower()

        if metric_lower == 'revenue':
            result['revenue'] = val
            result['revenue_prev'] = val_prev
        elif 'revenue growth' in metric_lower:
            result['revenue_growth'] = val
        elif 'gross profit' in metric_lower and 'margin' not in metric_lower:
            result['gross_profit'] = val
        elif 'operating income' in metric_lower and 'margin' not in metric_lower:
            result['operating_income'] = val
        elif metric_lower == 'net income':
            result['net_income'] = val
            result['net_income_prev'] = val_prev
        elif 'net income growth' in metric_lower:
            result['net_income_growth'] = val
        elif 'eps (basic)' in metric_lower:
            result['eps'] = val
        elif 'eps growth' in metric_lower:
            result['eps_growth'] = val
        elif 'dividend per share' in metric_lower:
            result['dividend_per_share'] = val
        elif 'dividend growth' in metric_lower:
            result['dividend_growth'] = val
        elif 'gross margin' in metric_lower:
            result['gross_margin'] = val
        elif 'operating margin' in metric_lower:
            result['operating_margin'] = val
        elif 'profit margin' in metric_lower:
            result['profit_margin'] = val
        elif metric_lower == 'ebitda':
            result['ebitda'] = val
        elif 'ebitda margin' in metric_lower:
            result['ebitda_margin'] = val
        elif 'free cash flow' in metric_lower and 'per share' not in metric_lower and 'margin' not in metric_lower:
            result['free_cash_flow'] = val

    return result

def scrape_ratios(ticker):
    """
    Scrape ratios page for: PB, ROE, ROA, Debt/Equity
    """
    url = f"https://stockanalysis.com/quote/brvm/{ticker}/financials/ratios/"
    soup = get_soup(url)
    if not soup:
        return {}

    result = {}
    table = soup.find('table')
    if not table:
        return result

    tbody = table.find('tbody')
    if not tbody:
        return result

    for row in tbody.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 2:
            continue

        metric = cells[0].get_text(strip=True).lower()
        # "Current" column is cells[1], FY2025 is cells[2]
        val = parse_number(cells[1].get_text(strip=True))
        if val is None and len(cells) > 2:
            val = parse_number(cells[2].get_text(strip=True))

        if 'pe ratio' in metric:
            result['pe_ratio'] = val
        elif 'pb ratio' in metric or 'price/book' in metric:
            result['pb_ratio'] = val
        elif metric.startswith('ps ratio'):
            result['ps_ratio'] = val
        elif 'return on equity' in metric or metric == 'roe':
            result['roe'] = val
        elif 'return on asset' in metric or metric == 'roa':
            result['roa'] = val
        elif 'debt / equity' in metric or 'debt/equity' in metric:
            result['debt_to_equity'] = val
        elif 'dividend yield' in metric:
            result['dividend_yield'] = val
        elif 'ev/ebitda' in metric:
            result['ev_ebitda'] = val

    return result

def scrape_all(ticker):
    """Combine all sources for one ticker."""
    print(f"  Scraping {ticker}...")

    overview = scrape_overview(ticker)
    time.sleep(1.5)

    financials = scrape_financials(ticker)
    time.sleep(1.5)

    ratios = scrape_ratios(ticker)
    time.sleep(1.5)

    # Merge — financials override overview for overlapping fields
    combined = {**overview, **financials, **ratios}
    combined['ticker'] = ticker
    combined['fiscal_year'] = 'FY2025'
    combined['scraped_at'] = date.today().isoformat()

    # Log what we got
    key_fields = ['revenue', 'net_income', 'eps', 'dividend_per_share',
                  'pe_ratio', 'pb_ratio', 'roe', 'operating_margin']
    found = [f for f in key_fields if combined.get(f) is not None]
    print(f"    ✅ {len(found)}/{len(key_fields)} key fields: {found}")

    return combined

def get_company_ids():
    """Get mapping symbol -> company_id from Supabase."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/companies?select=id,symbol",
        headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
    )
    if r.status_code == 200:
        return {c['symbol']: c['id'] for c in r.json()}
    return {}

def upsert_to_supabase(record):
    """Upsert record to company_fundamentals table."""
    # Remove None values
    clean = {k: v for k, v in record.items() if v is not None}
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/company_fundamentals",
        headers=HEADERS_SUPA,
        json=clean
    )
    return r.status_code

if __name__ == '__main__':
    import sys

    full_run = '--full' in sys.argv
    test_tickers = ['SNTS', 'BOAC', 'CBIBF', 'BOAB', 'SIVC']

    print("="*60)
    print("BRVM Fundamentals Scraper v2 — Stock Analysis")
    print(f"Date: {date.today()}")
    print(f"Mode: {'FULL (47 tickers)' if full_run else 'TEST (5 tickers)'}")
    print("="*60)

    company_ids = get_company_ids()
    print(f"✅ {len(company_ids)} companies in Supabase\n")

    tickers_to_run = TICKERS if full_run else test_tickers
    results = []
    errors = []

    for ticker in tickers_to_run:
        data = scrape_all(ticker)

        if data.get('revenue') or data.get('net_income') or data.get('pe_ratio'):
            data['company_id'] = company_ids.get(ticker)
            results.append(data)

            # Upsert to Supabase
            status = upsert_to_supabase(data)
            if status in [200, 201]:
                print(f"    💾 Saved to Supabase")
            else:
                print(f"    ⚠️  Supabase status: {status}")
        else:
            errors.append(ticker)
            print(f"    ❌ No data found")

        time.sleep(2)  # Be polite

    print(f"\n{'='*60}")
    print(f"✅ Success: {len(results)}/{len(tickers_to_run)}")
    if errors:
        print(f"❌ Failed: {errors}")

    print("\n--- SUMMARY ---")
    for r in results:
        t = r['ticker']
        print(f"\n{t}:")
        print(f"  Revenue:    {r.get('revenue')} M FCFA")
        print(f"  Net Income: {r.get('net_income')} M FCFA")
        print(f"  EPS:        {r.get('eps')} FCFA")
        print(f"  Dividend:   {r.get('dividend_per_share')} FCFA")
        print(f"  PE:         {r.get('pe_ratio')}")
        print(f"  PB:         {r.get('pb_ratio')}")
        print(f"  ROE:        {r.get('roe')}%")
        print(f"  Op Margin:  {r.get('operating_margin')}%")

    if not full_run:
        print(f"\n👉 Pour lancer sur les 47 tickers: python scrape_fundamentals_v2.py --full")
