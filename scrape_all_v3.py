"""
scrape_all_v3.py
Scrape complet depuis stockanalysis.com pour tous les tickers BRVM
Capture: fondamentaux + ratios + balance sheet + cash flow + management + événements
"""

import os, re, json, time, requests, urllib3
from bs4 import BeautifulSoup
from datetime import date
from dotenv import load_dotenv

urllib3.disable_warnings()
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.9',
})

TICKERS = [
    'ABJC','BICC','BNBC','BOAB','BOABF','BOAC','BOAM','BOAN','BOAS',
    'CABC','CBIBF','CFAC','CIEC','ECOC','ETIT','FTSC','LNBB','NEIC',
    'NSBC','NTLC','ONTBF','ORAC','ORGT','PALC','PRSC','SAFC','SCRC',
    'SDCC','SDSC','SEMC','SGBC','SHEC','SIBC','SICC','SIVC','SLBC',
    'SMBC','SNTS','SOGC','SPHC','STAC','STBC','TTLC','TTLS','UNLC','UNXC'
]

FUNDAMENTALS_ALLOWED = {
    'company_id','ticker','fiscal_year','revenue','revenue_growth','revenue_ttm',
    'gross_profit','operating_income','net_income','net_income_growth','net_income_ttm',
    'eps','eps_growth','dividend_per_share','dividend_yield','dividend_growth',
    'gross_margin','operating_margin','profit_margin','ebitda','ebitda_margin',
    'free_cash_flow','pe_ratio','forward_pe','pb_ratio','ps_ratio','ev_ebitda',
    'roe','roa','debt_to_equity','payout_ratio','earnings_yield','fcf_yield',
    'market_cap','enterprise_value','shares_outstanding','beta','rsi_current',
    'week52_high','week52_low','ex_dividend_date','earnings_date',
    'cash_and_equivalents','total_assets','total_debt','total_equity',
    'operating_cash_flow','capital_expenditures','ma50','ma200','scraped_at'
}

def parse_val(text):
    """Extract first number from text like '2.85T+14%' or '1,933.33 (6.78%)'"""
    if not text or str(text).strip() in ['-','N/A','n/a','','—','na']:
        return None
    text = str(text).strip().replace(',','')
    m = re.match(r'^[-]?([0-9]+\.?[0-9]*)\s*([TBM])?', text)
    if not m:
        return None
    val = float(m.group(1))
    suffix = m.group(2)
    if suffix == 'T': val *= 1_000_000
    elif suffix == 'B': val *= 1_000
    return val

def parse_pct(text):
    """Extract % from '1,933.33 (6.78%)' → 6.78"""
    if not text: return None
    m = re.search(r'\(([0-9\.]+)%\)', text)
    return float(m.group(1)) if m else None

def parse_range(text):
    """Extract high/low from '22,341 - 29,300'"""
    if not text or '-' not in text: return None, None
    parts = text.replace(',','').split('-')
    if len(parts) == 2:
        try:
            return float(parts[0].strip()), float(parts[1].strip())
        except: pass
    return None, None

def get_soup(url, delay=1.5):
    try:
        time.sleep(delay)
        r = SESSION.get(url, timeout=20, verify=False)
        if r.status_code == 200:
            return BeautifulSoup(r.text, 'html.parser')
        return None
    except:
        return None

def get_table_data(soup):
    """Extract all rows from first table as {metric: value}"""
    data = {}
    if not soup: return data
    table = soup.find('table')
    if not table: return data
    tbody = table.find('tbody') or table
    for row in tbody.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) >= 2:
            metric = cells[0].get_text(strip=True).lower()
            vals = [c.get_text(strip=True) for c in cells[1:]]
            data[metric] = vals
    return data

def scrape_overview(ticker):
    """Overview: PE, EPS, Dividend, Market Cap, Beta, RSI, Dates"""
    soup = get_soup(f"https://stockanalysis.com/quote/brvm/{ticker}/")
    if not soup: return {}
    result = {}
    for row in soup.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 2: continue
        label = cells[0].get_text(strip=True).lower()
        raw = cells[1].get_text(strip=True)
        if 'market cap' in label:
            result['market_cap'] = parse_val(raw)
        elif 'revenue' in label and 'ttm' in label:
            result['revenue_ttm'] = parse_val(raw)
        elif 'net income' in label:
            result['net_income_ttm'] = parse_val(raw)
        elif label == 'eps':
            result['eps'] = parse_val(raw)
        elif 'pe ratio' in label and 'forward' not in label:
            result['pe_ratio'] = parse_val(raw)
        elif 'forward pe' in label:
            result['forward_pe'] = parse_val(raw)
        elif label == 'dividend':
            result['dividend_per_share'] = parse_val(raw)
            result['dividend_yield'] = parse_pct(raw)
        elif 'ex-dividend' in label:
            result['ex_dividend_date'] = raw
        elif 'earnings date' in label:
            result['earnings_date'] = raw
        elif label == 'beta':
            result['beta'] = parse_val(raw)
        elif label == 'rsi':
            result['rsi_current'] = parse_val(raw)
        elif 'shares out' in label:
            result['shares_outstanding'] = parse_val(raw)
        elif '52-week range' in label:
            low, high = parse_range(raw)
            result['week52_low'] = low
            result['week52_high'] = high
    return result

def scrape_financials(ticker):
    """Income statement: Revenue, Net Income, EPS, Margins, EBITDA"""
    soup = get_soup(f"https://stockanalysis.com/quote/brvm/{ticker}/financials/")
    data = get_table_data(soup)
    result = {}
    for metric, vals in data.items():
        v0 = parse_val(vals[0]) if vals else None
        v1 = parse_val(vals[1]) if len(vals) > 1 else None
        if metric == 'revenue':
            result['revenue'] = v0
            result['revenue_prev'] = v1
        elif 'revenue growth' in metric:
            result['revenue_growth'] = parse_val(vals[0].replace('%','')) if vals else None
        elif metric == 'gross profit':
            result['gross_profit'] = v0
        elif metric == 'operating income':
            result['operating_income'] = v0
        elif metric == 'net income':
            result['net_income'] = v0
            result['net_income_prev'] = v1
        elif 'net income growth' in metric:
            result['net_income_growth'] = parse_val(vals[0].replace('%','')) if vals else None
        elif 'eps (basic)' in metric:
            result['eps'] = v0
        elif 'eps growth' in metric:
            result['eps_growth'] = parse_val(vals[0].replace('%','')) if vals else None
        elif 'dividend per share' in metric:
            result['dividend_per_share'] = v0
        elif 'dividend growth' in metric:
            result['dividend_growth'] = parse_val(vals[0].replace('%','')) if vals else None
        elif 'gross margin' in metric:
            result['gross_margin'] = parse_val(vals[0].replace('%','')) if vals else None
        elif 'operating margin' in metric:
            result['operating_margin'] = parse_val(vals[0].replace('%','')) if vals else None
        elif 'profit margin' in metric:
            result['profit_margin'] = parse_val(vals[0].replace('%','')) if vals else None
        elif metric == 'ebitda':
            result['ebitda'] = v0
        elif 'ebitda margin' in metric:
            result['ebitda_margin'] = parse_val(vals[0].replace('%','')) if vals else None
        elif 'free cash flow' in metric and 'per share' not in metric and 'margin' not in metric:
            result['free_cash_flow'] = v0
    return result

def scrape_balance_sheet(ticker):
    """Balance sheet: Cash, Assets, Debt, Equity"""
    soup = get_soup(f"https://stockanalysis.com/quote/brvm/{ticker}/financials/balance-sheet/")
    data = get_table_data(soup)
    result = {}
    for metric, vals in data.items():
        v0 = parse_val(vals[0]) if vals else None
        if 'cash & equivalents' in metric or metric == 'cash & short-term investments':
            result['cash_and_equivalents'] = v0
        elif metric == 'total assets':
            result['total_assets'] = v0
        elif 'total debt' in metric:
            result['total_debt'] = v0
        elif "total equity" in metric or "shareholders' equity" in metric:
            result['total_equity'] = v0
    return result

def scrape_cashflow(ticker):
    """Cash flow: Operating CF, CapEx"""
    soup = get_soup(f"https://stockanalysis.com/quote/brvm/{ticker}/financials/cash-flow-statement/")
    data = get_table_data(soup)
    result = {}
    for metric, vals in data.items():
        v0 = parse_val(vals[0]) if vals else None
        if metric == 'operating cash flow':
            result['operating_cash_flow'] = v0
        elif 'capital expenditures' in metric:
            result['capital_expenditures'] = v0
    return result

def scrape_ratios(ticker):
    """Ratios: PB, ROE, ROA, Debt/Equity, EV/EBITDA, Yields"""
    soup = get_soup(f"https://stockanalysis.com/quote/brvm/{ticker}/financials/ratios/")
    data = get_table_data(soup)
    result = {}
    for metric, vals in data.items():
        # Use current col (vals[0]) first, fallback to FY2025 (vals[1])
        v = parse_val(vals[0]) if vals else None
        if v is None and len(vals) > 1:
            v = parse_val(vals[1])
        if 'pb ratio' in metric:
            result['pb_ratio'] = v
        elif 'ps ratio' in metric:
            result['ps_ratio'] = v
        elif 'return on equity' in metric or metric == 'roe':
            result['roe'] = v
        elif 'return on asset' in metric or metric == 'roa':
            result['roa'] = v
        elif 'debt / equity' in metric:
            result['debt_to_equity'] = v
        elif 'ev/ebitda' in metric:
            result['ev_ebitda'] = v
        elif 'payout ratio' in metric:
            result['payout_ratio'] = parse_val(vals[0].replace('%','')) if vals else None
        elif 'earnings yield' in metric:
            result['earnings_yield'] = parse_val(vals[0].replace('%','')) if vals else None
        elif 'fcf yield' in metric:
            result['fcf_yield'] = parse_val(vals[0].replace('%','')) if vals else None
        elif '50-day' in metric or 'ma50' in metric:
            result['ma50'] = v
        elif '200-day' in metric or 'ma200' in metric:
            result['ma200'] = v
        elif 'enterprise value' in metric and 'ratio' not in metric:
            result['enterprise_value'] = v
    return result

def scrape_statistics(ticker):
    """Statistics page: MA50, MA200, Payout Ratio, Yields"""
    soup = get_soup(f"https://stockanalysis.com/quote/brvm/{ticker}/statistics/")
    if not soup: return {}
    result = {}
    for row in soup.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 2: continue
        label = cells[0].get_text(strip=True).lower()
        raw = cells[1].get_text(strip=True)
        if '50-day moving' in label:
            result['ma50'] = parse_val(raw)
        elif '200-day moving' in label:
            result['ma200'] = parse_val(raw)
        elif 'payout ratio' in label:
            result['payout_ratio'] = parse_val(raw.replace('%',''))
        elif 'earnings yield' in label:
            result['earnings_yield'] = parse_val(raw.replace('%',''))
        elif 'fcf yield' in label:
            result['fcf_yield'] = parse_val(raw.replace('%',''))
        elif 'dividend growth' in label and 'yoy' in label:
            result['dividend_growth'] = parse_val(raw.replace('%',''))
        elif 'enterprise value' in label:
            result['enterprise_value'] = parse_val(raw)
    return result

def scrape_profile(ticker):
    """Profile: CEO, CFO, executives, employees, country, industry"""
    soup = get_soup(f"https://stockanalysis.com/quote/brvm/{ticker}/company/")
    if not soup: return {}
    result = {'ticker': ticker}

    # Key-value pairs in profile
    for row in soup.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 2: continue
        label = cells[0].get_text(strip=True).lower()
        value = cells[1].get_text(strip=True)
        if 'employee' in label:
            try: result['employees'] = int(value.replace(',',''))
            except: pass
        elif 'country' in label:
            result['country'] = value
        elif 'industry' in label:
            result['industry'] = value
        elif 'sector' in label:
            result['sector'] = value
        elif 'founded' in label:
            result['founded'] = value
        elif 'website' in label or 'www' in value.lower():
            result['website'] = value
        elif 'ceo' in label:
            result['ceo'] = value

    # Executives table
    executives = []
    ceo = None
    cfo = None
    for table in soup.find_all('table'):
        headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
        if 'name' in headers and 'position' in headers:
            for row in table.find_all('tr')[1:]:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    name = cells[0].get_text(strip=True)
                    position = cells[1].get_text(strip=True)
                    executives.append({'name': name, 'position': position})
                    pos_lower = position.lower()
                    if 'chief executive' in pos_lower or 'ceo' in pos_lower:
                        ceo = name
                    elif 'chief financial' in pos_lower or 'cfo' in pos_lower:
                        cfo = name

    if ceo: result['ceo'] = ceo
    if cfo: result['cfo'] = cfo
    if executives:
        result['other_executives'] = json.dumps(executives)

    # Address
    address_div = soup.find('address')
    if address_div:
        result['address'] = address_div.get_text(separator=', ', strip=True)

    return result

def get_company_ids():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/companies?select=id,symbol",
        headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
    )
    return {c['symbol']: c['id'] for c in r.json()} if r.status_code == 200 else {}

def upsert_fundamentals(record):
    clean = {k: v for k, v in record.items() if k in FUNDAMENTALS_ALLOWED and v is not None}
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/company_fundamentals",
        headers={
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'resolution=merge-duplicates'
        },
        json=clean
    )
    return r.status_code

def upsert_management(record):
    clean = {k: v for k, v in record.items() if v is not None}
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/company_management",
        headers={
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'resolution=merge-duplicates'
        },
        json=clean
    )
    return r.status_code

if __name__ == '__main__':
    import sys
    full_run = '--full' in sys.argv
    test_tickers = ['SNTS', 'BOAC', 'CBIBF', 'ETIT', 'SGBC']
    tickers = TICKERS if full_run else test_tickers

    print("="*60)
    print(f"BRVM Scraper v3 — {'FULL 47 tickers' if full_run else 'TEST 5 tickers'}")
    print(f"Date: {date.today()}")
    print("="*60)

    company_ids = get_company_ids()
    print(f"✅ {len(company_ids)} companies in Supabase\n")

    fund_ok, mgmt_ok, fund_fail, mgmt_fail = 0, 0, [], []

    for i, ticker in enumerate(tickers):
        print(f"[{i+1}/{len(tickers)}] {ticker}...")

        # --- FUNDAMENTALS ---
        overview   = scrape_overview(ticker)
        financials = scrape_financials(ticker)
        balance    = scrape_balance_sheet(ticker)
        cashflow   = scrape_cashflow(ticker)
        ratios     = scrape_ratios(ticker)
        stats      = scrape_statistics(ticker)

        fund_data = {**overview, **financials, **balance, **cashflow, **ratios, **stats}
        fund_data['ticker'] = ticker
        fund_data['fiscal_year'] = 'FY2025'
        fund_data['company_id'] = company_ids.get(ticker)
        fund_data['scraped_at'] = date.today().isoformat()

        status = upsert_fundamentals(fund_data)
        if status in [200, 201]:
            fund_ok += 1
            fields_found = sum(1 for k in ['revenue','net_income','pe_ratio','roe',
                'ex_dividend_date','earnings_date','ma50','cash_and_equivalents']
                if fund_data.get(k))
            print(f"  💰 Fundamentals: {fields_found}/8 key fields [{status}]")
            print(f"     PE={fund_data.get('pe_ratio')} ROE={fund_data.get('roe')} "
                  f"EarningsDate={fund_data.get('earnings_date')} "
                  f"ExDiv={fund_data.get('ex_dividend_date')}")
        else:
            fund_fail.append(ticker)
            print(f"  ❌ Fundamentals failed [{status}]")

        # --- MANAGEMENT ---
        profile = scrape_profile(ticker)
        profile['company_id'] = company_ids.get(ticker)
        profile['scraped_at'] = date.today().isoformat()

        status = upsert_management(profile)
        if status in [200, 201]:
            mgmt_ok += 1
            print(f"  👤 Management: CEO={profile.get('ceo')} CFO={profile.get('cfo')} "
                  f"Employees={profile.get('employees')} [{status}]")
        else:
            mgmt_fail.append(ticker)
            print(f"  ❌ Management failed [{status}]")

        print()
        time.sleep(3)

    print("="*60)
    print(f"✅ Fundamentals: {fund_ok}/{len(tickers)}")
    print(f"✅ Management:   {mgmt_ok}/{len(tickers)}")
    if fund_fail: print(f"❌ Fund failed:  {fund_fail}")
    if mgmt_fail: print(f"❌ Mgmt failed:  {mgmt_fail}")
    if not full_run:
        print(f"\n👉 Pour lancer sur 47 tickers: python scrape_all_v3.py --full")
