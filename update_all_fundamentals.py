import os, time, requests, urllib3
from datetime import date
from dotenv import load_dotenv
import scrape_all_v3 as v3

urllib3.disable_warnings()
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

def update_fundamentals(ticker, data):
    clean = {k: val for k, val in data.items() if k in v3.FUNDAMENTALS_ALLOWED and val is not None and k not in ['company_id','ticker','fiscal_year']}
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/company_fundamentals?ticker=eq.{ticker}&fiscal_year=eq.FY2025",
        headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}', 'Content-Type': 'application/json'},
        json=clean
    )
    return r.status_code

def update_management(ticker, profile):
    clean = {k: v for k, v in profile.items() if v is not None and k != 'company_id'}
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/company_management?ticker=eq.{ticker}",
        headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}', 'Content-Type': 'application/json'},
        json=clean
    )
    return r.status_code

company_ids = v3.get_company_ids()
print(f"Companies: {len(company_ids)}\n")

fund_ok, mgmt_ok = 0, 0
fund_fail, mgmt_fail = [], []

for i, ticker in enumerate(v3.TICKERS):
    print(f"[{i+1}/{len(v3.TICKERS)}] {ticker}...", end=' ', flush=True)

    data = {}
    data.update(v3.scrape_overview(ticker))
    data.update(v3.scrape_financials(ticker))
    data.update(v3.scrape_balance_sheet(ticker))
    data.update(v3.scrape_cashflow(ticker))
    data.update(v3.scrape_ratios(ticker))
    data.update(v3.scrape_statistics(ticker))
    data.update({'ticker': ticker, 'fiscal_year': 'FY2025',
                 'company_id': company_ids.get(ticker),
                 'scraped_at': date.today().isoformat()})

    fs = update_fundamentals(ticker, data)
    if fs == 204:
        fund_ok += 1
    else:
        # Try INSERT if no existing record
        clean = {k: v for k, v in data.items() if k in v3.FUNDAMENTALS_ALLOWED and v is not None}
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/company_fundamentals",
            headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}',
                     'Content-Type': 'application/json'},
            json=clean
        )
        if r.status_code in [200, 201]:
            fund_ok += 1
            fs = r.status_code
        else:
            fund_fail.append(ticker)

    profile = v3.scrape_profile(ticker)
    profile['company_id'] = company_ids.get(ticker)
    profile['scraped_at'] = date.today().isoformat()

    ms = update_management(ticker, profile)
    if ms == 204:
        mgmt_ok += 1
    else:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/company_management",
            headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}',
                     'Content-Type': 'application/json',
                     'Prefer': 'resolution=merge-duplicates'},
            json={k: v for k, v in profile.items() if v is not None}
        )
        if r.status_code in [200, 201]:
            mgmt_ok += 1
            ms = r.status_code
        else:
            mgmt_fail.append(ticker)

    print(f"Fund:[{fs}] Mgmt:[{ms}] Earnings={data.get('earnings_date')} ExDiv={data.get('ex_dividend_date')}")
    time.sleep(3)

print(f"\n✅ Fundamentals: {fund_ok}/{len(v3.TICKERS)}")
print(f"✅ Management:   {mgmt_ok}/{len(v3.TICKERS)}")
if fund_fail: print(f"❌ Fund failed: {fund_fail}")
if mgmt_fail: print(f"❌ Mgmt failed: {mgmt_fail}")
