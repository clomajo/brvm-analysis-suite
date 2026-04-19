import os, re, requests, urllib3, time
from bs4 import BeautifulSoup
from datetime import date
from dotenv import load_dotenv

urllib3.disable_warnings()
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'})

def parse_value(text):
    """Extract first number from text like '2.85T+14.0%' or '1,933.33 (6.78%)'"""
    if not text or text.strip() in ['-', 'N/A', 'n/a', '']:
        return None
    text = text.strip()
    # Extract first numeric token (before +/- growth or parenthesis)
    m = re.match(r'^([0-9,\.]+)\s*([TBM])?', text.replace(',', ''))
    if not m:
        return None
    val = float(m.group(1).replace(',', ''))
    suffix = m.group(2)
    if suffix == 'T': val *= 1_000_000
    elif suffix == 'B': val *= 1_000
    return val

def parse_pct(text):
    """Extract percentage from '1,933.33 (6.78%)' → 6.78"""
    if not text:
        return None
    m = re.search(r'\(([0-9\.]+)%\)', text)
    return float(m.group(1)) if m else None

def scrape_overview(ticker):
    url = f"https://stockanalysis.com/quote/brvm/{ticker}/"
    r = SESSION.get(url, timeout=20, verify=False)
    if r.status_code != 200:
        return {}
    soup = BeautifulSoup(r.text, 'html.parser')
    result = {}
    for row in soup.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 2:
            continue
        label = cells[0].get_text(strip=True).lower()
        raw = cells[1].get_text(strip=True)
        if 'market cap' in label:
            result['market_cap'] = parse_value(raw)
        elif 'revenue' in label:
            result['revenue_ttm'] = parse_value(raw)
        elif 'net income' in label:
            result['net_income_ttm'] = parse_value(raw)
        elif label == 'eps':
            result['eps'] = parse_value(raw)
        elif 'pe ratio' in label and 'forward' not in label:
            result['pe_ratio'] = parse_value(raw)
        elif 'forward pe' in label:
            result['forward_pe'] = parse_value(raw)
        elif label == 'dividend':
            result['dividend_per_share'] = parse_value(raw)
            result['dividend_yield'] = parse_pct(raw)
        elif 'ex-dividend' in label:
            result['ex_dividend_date'] = raw
        elif label == 'beta':
            result['beta'] = parse_value(raw)
        elif label == 'rsi':
            result['rsi'] = parse_value(raw)
        elif 'shares out' in label:
            result['shares_outstanding'] = parse_value(raw)
        elif 'earnings date' in label:
            result['earnings_date'] = raw
    return result

def scrape_financials(ticker):
    url = f"https://stockanalysis.com/quote/brvm/{ticker}/financials/"
    r = SESSION.get(url, timeout=20, verify=False)
    if r.status_code != 200:
        return {}
    soup = BeautifulSoup(r.text, 'html.parser')
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
        val = parse_value(cells[1].get_text(strip=True))
        val_prev = parse_value(cells[2].get_text(strip=True)) if len(cells) > 2 else None
        if metric == 'revenue':
            result['revenue'] = val
            result['revenue_prev'] = val_prev
        elif 'revenue growth' in metric:
            result['revenue_growth'] = parse_value(cells[1].get_text(strip=True).replace('%',''))
        elif metric == 'gross profit':
            result['gross_profit'] = val
        elif metric == 'operating income':
            result['operating_income'] = val
        elif metric == 'net income':
            result['net_income'] = val
            result['net_income_prev'] = val_prev
        elif 'net income growth' in metric:
            result['net_income_growth'] = parse_value(cells[1].get_text(strip=True).replace('%',''))
        elif 'eps (basic)' in metric:
            result['eps'] = val
        elif 'eps growth' in metric:
            result['eps_growth'] = parse_value(cells[1].get_text(strip=True).replace('%',''))
        elif 'dividend per share' in metric:
            result['dividend_per_share'] = val
        elif 'gross margin' in metric:
            result['gross_margin'] = parse_value(cells[1].get_text(strip=True).replace('%',''))
        elif 'operating margin' in metric:
            result['operating_margin'] = parse_value(cells[1].get_text(strip=True).replace('%',''))
        elif 'profit margin' in metric:
            result['profit_margin'] = parse_value(cells[1].get_text(strip=True).replace('%',''))
        elif metric == 'ebitda':
            result['ebitda'] = val
        elif 'ebitda margin' in metric:
            result['ebitda_margin'] = parse_value(cells[1].get_text(strip=True).replace('%',''))
        elif 'free cash flow' in metric and 'per share' not in metric and 'margin' not in metric:
            result['free_cash_flow'] = val
    return result

def scrape_ratios(ticker):
    url = f"https://stockanalysis.com/quote/brvm/{ticker}/financials/ratios/"
    r = SESSION.get(url, timeout=20, verify=False)
    if r.status_code != 200:
        return {}
    soup = BeautifulSoup(r.text, 'html.parser')
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
        # Try current col first, then FY2025
        val = parse_value(cells[1].get_text(strip=True))
        if val is None and len(cells) > 2:
            val = parse_value(cells[2].get_text(strip=True))
        if 'pb ratio' in metric:
            result['pb_ratio'] = val
        elif 'return on equity' in metric or metric == 'roe':
            result['roe'] = val
        elif 'return on asset' in metric or metric == 'roa':
            result['roa'] = val
        elif 'debt / equity' in metric:
            result['debt_to_equity'] = val
        elif 'ev/ebitda' in metric:
            result['ev_ebitda'] = val
    return result

def get_company_ids():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/companies?select=id,symbol",
        headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
    )
    return {c['symbol']: c['id'] for c in r.json()} if r.status_code == 200 else {}

def upsert(record):
    clean = {k: v for k, v in record.items() if v is not None}
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

# --- MAIN ---
import sys
full_run = '--full' in sys.argv
test_tickers = ['SNTS', 'BOAC', 'CBIBF', 'BOAB', 'SIVC']
tickers = ['ABJC','BICC','BNBC','BOAB','BOABF','BOAC','BOAM','BOAN','BOAS',
    'CABC','CBIBF','CFAC','CIEC','ECOC','ETIT','FTSC','LNBB','NEIC',
    'NSBC','NTLC','ONTBF','ORAC','ORGT','PALC','PRSC','SAFC','SCRC',
    'SDCC','SDSC','SEMC','SGBC','SHEC','SIBC','SICC','SIVC','SLBC',
    'SMBC','SNTS','SOGC','SPHC','STAC','STBC','TTLC','TTLS','UNLC','UNXC'] if full_run else test_tickers

print(f"Mode: {'FULL' if full_run else 'TEST'} — {len(tickers)} tickers")
company_ids = get_company_ids()
print(f"Companies in Supabase: {len(company_ids)}\n")

success, failed = 0, []
for ticker in tickers:
    print(f"{ticker}...", end=' ', flush=True)
    overview = scrape_overview(ticker); time.sleep(1)
    financials = scrape_financials(ticker); time.sleep(1)
    ratios = scrape_ratios(ticker); time.sleep(1)

    data = {**overview, **financials, **ratios}
    data['ticker'] = ticker
    data['fiscal_year'] = 'FY2025'
    data['company_id'] = company_ids.get(ticker)
    data['scraped_at'] = date.today().isoformat()

    if data.get('revenue') or data.get('pe_ratio') or data.get('net_income_ttm'):
        status = upsert(data)
        print(f"✅ Rev={data.get('revenue')} NI={data.get('net_income') or data.get('net_income_ttm')} PE={data.get('pe_ratio')} Div={data.get('dividend_per_share')} [Supabase:{status}]")
        success += 1
    else:
        print(f"❌ No data")
        failed.append(ticker)
    time.sleep(2)

print(f"\n✅ {success}/{len(tickers)} success")
if failed: print(f"❌ Failed: {failed}")

# --- RUN FILTERED ---
ALLOWED = {
    'company_id','ticker','fiscal_year','revenue','revenue_growth',
    'gross_profit','operating_income','net_income','net_income_growth',
    'eps','eps_growth','dividend_per_share','gross_margin','operating_margin',
    'profit_margin','ebitda','ebitda_margin','free_cash_flow',
    'pe_ratio','pb_ratio','roe','roa','debt_to_equity','dividend_yield','scraped_at'
}

if __name__ == '__main__':
    import sys
    full_run = '--full' in sys.argv
    test_tickers = ['SNTS','BOAC','CBIBF','BOAB','SIVC']
    all_tickers = ['ABJC','BICC','BNBC','BOAB','BOABF','BOAC','BOAM','BOAN','BOAS',
        'CABC','CBIBF','CFAC','CIEC','ECOC','ETIT','FTSC','LNBB','NEIC',
        'NSBC','NTLC','ONTBF','ORAC','ORGT','PALC','PRSC','SAFC','SCRC',
        'SDCC','SDSC','SEMC','SGBC','SHEC','SIBC','SICC','SIVC','SLBC',
        'SMBC','SNTS','SOGC','SPHC','STAC','STBC','TTLC','TTLS','UNLC','UNXC']
    tickers = all_tickers if full_run else test_tickers

    company_ids = get_company_ids()
    success, failed = 0, []

    for ticker in tickers:
        print(f'{ticker}...', end=' ', flush=True)
        overview = scrape_overview(ticker); time.sleep(1)
        financials = scrape_financials(ticker); time.sleep(1)
        ratios = scrape_ratios(ticker); time.sleep(1)

        data = {**overview, **financials, **ratios}
        data['ticker'] = ticker
        data['fiscal_year'] = 'FY2025'
        data['company_id'] = company_ids.get(ticker)
        data['scraped_at'] = date.today().isoformat()

        clean = {k: v for k, v in data.items() if k in ALLOWED and v is not None}

        r = requests.post(
            f'{SUPABASE_URL}/rest/v1/company_fundamentals',
            headers={
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json',
                'Prefer': 'resolution=merge-duplicates'
            },
            json=clean
        )
        if r.status_code in [200, 201]:
            print(f'✅ PE={clean.get("pe_ratio")} Rev={clean.get("revenue")} NI={clean.get("net_income")} Div={clean.get("dividend_per_share")} [{r.status_code}]')
            success += 1
        else:
            print(f'❌ {r.status_code}: {r.text[:100]}')
            failed.append(ticker)
        time.sleep(2)

    print(f'\nDone: {success}/{len(tickers)}')
    if failed:
        print(f'Failed: {failed}')
