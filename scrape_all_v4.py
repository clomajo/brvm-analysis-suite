"""
scrape_all_v4.py
Scrape 5 ans de données financières depuis stockanalysis.com pour tous les tickers BRVM
- company_fundamentals: FY2021 à FY2025 (5 lignes par ticker)
- company_management: CEO, CFO, employés, profil
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
    'ABJC','BICB','BICC','BNBC','BOAB','BOABF','BOAC','BOAM','BOAN','BOAS',
    'CABC','CBIBF','CFAC','CIEC','ECOC','ETIT','FTSC','LNBB','NEIC',
    'NSBC','NTLC','ONTBF','ORAC','ORGT','PALC','PRSC','SAFC','SCRC',
    'SDCC','SDSC','SEMC','SGBC','SHEC','SIBC','SICC','SIVC','SLBC',
    'SMBC','SNTS','SOGC','SPHC','STAC','STBC','TTLC','TTLS','UNLC','UNXC'
]

FISCAL_YEARS = ['FY 2025', 'FY 2024', 'FY 2023', 'FY 2022', 'FY 2021']
FY_MAP = {
    'FY 2025': 'FY2025', 'FY 2024': 'FY2024', 'FY 2023': 'FY2023',
    'FY 2022': 'FY2022', 'FY 2021': 'FY2021'
}

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
    if not text or str(text).strip() in ['-','N/A','n/a','','—','na','NC']:
        return None
    text = str(text).strip().replace(',','')
    # Remove percentage signs and growth indicators
    text = re.sub(r'[+]', '', text)
    m = re.match(r'^-?([0-9]+\.?[0-9]*)\s*([TBM])?', text)
    if not m:
        return None
    val = float(m.group(1))
    if text.startswith('-'):
        val = -val
    suffix = m.group(2)
    if suffix == 'T': val *= 1_000_000
    elif suffix == 'B': val *= 1_000
    return val

def parse_pct(text):
    if not text: return None
    m = re.search(r'\(([0-9\.]+)%\)', text)
    return float(m.group(1)) if m else None

def parse_range(text):
    if not text: return None, None
    parts = re.split(r'\s*[-–]\s*', text.replace(',',''))
    if len(parts) == 2:
        try:
            return float(parts[0].strip()), float(parts[1].strip())
        except: pass
    return None, None

def check_eps_coherence(eps_scraped, net_income, shares_outstanding, ticker, fy, seuil_pct=10):
    """
    Vérifie la cohérence entre l'EPS scrapé tel quel depuis stockanalysis.com et
    l'EPS recalculé à partir de net_income / shares_outstanding.

    Contexte (cf. ADR-012 + investigation 25/06/2026) : eps est scrapé directement
    depuis le champ "EPS (Basic)" de stockanalysis.com (ligne ~157), sans aucun
    recalcul local. Si le nombre d'actions utilisé par stockanalysis.com diverge
    de la valeur shares_outstanding stockée côté Supabase (corrigée manuellement
    pour NTLC en ADR-012, par exemple), l'EPS scrapé reste incohérent même après
    correction de shares_outstanding — exactement le bug découvert sur NTLC (eps
    ~20x trop élevé), et retrouvé à des degrés divers sur BICC (~1.5x) et SOGC
    (~0.73x, mais seulement sur 2 années anciennes sur 5).

    shares_outstanding n'est disponible qu'au niveau "overview" (FY2025 uniquement,
    cf. scrape_overview ligne ~278) — pas par année historique. On réutilise donc
    le shares_outstanding de FY2025 comme approximation pour vérifier aussi les
    années passées (FY2021-2024), sous l'hypothèse que le nombre d'actions n'a pas
    changé sur la période. C'est une approximation, pas un fait : un split ou une
    augmentation de capital donnerait un faux-positif. D'où le message explicite
    ci-dessous plutôt qu'une correction automatique — on ne réécrit JAMAIS eps
    automatiquement, on log seulement pour investigation manuelle (cf. discussion
    25/06/2026 : ne jamais corriger une donnée sans en comprendre la cause racine).

    T4 (07/2026) : eps_recalcule est désormais utilisé par l'appelant (cf. bloc
    dans __main__) comme valeur primaire écrite dans company_fundamentals.eps ;
    l'eps scrapé devient le signal de cross-check. Un garde-fou de sanité côté
    appelant bloque le remplacement si le ratio eps_scrapé/eps_recalcule est
    hors [0.2, 5] ou de signe incohérent (cf. bug parse_val() suffixe 'M' +
    splits non répercutés à la source, ex. NTLC — cf. BACKLOG.md). Cette
    fonction elle-même ne modifie jamais le dict row.

    Retourne (eps_recalcule, warning) — (float|None, str|None).
    """
    if eps_scraped is None or net_income is None or not shares_outstanding:
        return None, None

    eps_recalcule = round((net_income * 1_000_000) / shares_outstanding, 2)

    if eps_scraped == 0:
        return eps_recalcule, None

    ecart_pct = abs(eps_scraped - eps_recalcule) / abs(eps_scraped) * 100
    if ecart_pct > seuil_pct:
        ratio = round(eps_scraped / eps_recalcule, 2) if eps_recalcule else None
        warning = (
            f"{ticker} {fy} : eps scrapé={eps_scraped} vs recalculé "
            f"(net_income×1M/shares_outstanding)={eps_recalcule} — écart {ecart_pct:.1f}% "
            f"(ratio {ratio}x). shares_outstanding utilisé = celui de FY2025 "
            f"(approximation pour les années historiques — peut être un "
            f"faux-positif si split/augmentation de capital sur la période, "
            f"à vérifier manuellement avant toute correction)."
        )
        return eps_recalcule, warning

    return eps_recalcule, None

def get_soup(url, delay=1.5):
    try:
        time.sleep(delay)
        r = SESSION.get(url, timeout=20, verify=False)
        if r.status_code == 200:
            return BeautifulSoup(r.text, 'html.parser')
        return None
    except:
        return None

def extract_table_by_year(soup):
    """
    Extract table data indexed by fiscal year.
    Returns: {
        'FY 2025': {'revenue': 1923122, ...},
        'FY 2024': {'revenue': 1776443, ...},
        ...
    }
    And also the column headers to know which years are available.
    """
    if not soup: return {}, []
    table = soup.find('table')
    if not table: return {}, []

    # Get headers to find year columns
    header_row = table.find('tr')
    if not header_row: return {}, []
    headers = [th.get_text(strip=True) for th in header_row.find_all(['th','td'])]

    # Find which columns correspond to fiscal years
    year_cols = {}  # {col_index: 'FY 2025'}
    for i, h in enumerate(headers):
        if h in FISCAL_YEARS:
            year_cols[i] = h

    if not year_cols: return {}, []

    # Initialize result
    result = {fy: {} for fy in year_cols.values()}

    tbody = table.find('tbody') or table
    for row in tbody.find_all('tr'):
        cells = row.find_all('td')
        if not cells: continue
        metric = cells[0].get_text(strip=True).lower()
        for col_idx, fy in year_cols.items():
            if col_idx < len(cells):
                val_text = cells[col_idx].get_text(strip=True)
                result[fy][metric] = val_text

    return result, list(year_cols.values())

def parse_income_by_year(table_data):
    """Parse income statement data for each year."""
    results = {}
    for fy, data in table_data.items():
        r = {}
        for metric, val_text in data.items():
            v = parse_val(val_text)
            pct = parse_val(val_text.replace('%','')) if '%' in val_text else None

            if metric == 'revenue':
                r['revenue'] = v
            elif 'revenue growth' in metric:
                r['revenue_growth'] = pct
            elif metric == 'gross profit':
                r['gross_profit'] = v
            elif metric == 'operating income':
                r['operating_income'] = v
            elif metric == 'net income' and 'common' not in metric:
                r['net_income'] = v
            elif 'net income growth' in metric:
                r['net_income_growth'] = pct
            elif 'eps (basic)' in metric:
                r['eps'] = v
            elif 'eps growth' in metric:
                r['eps_growth'] = pct
            elif 'dividend per share' in metric:
                r['dividend_per_share'] = v
            elif 'dividend growth' in metric:
                r['dividend_growth'] = pct
            elif 'gross margin' in metric:
                r['gross_margin'] = pct
            elif 'operating margin' in metric:
                r['operating_margin'] = pct
            elif 'profit margin' in metric:
                r['profit_margin'] = pct
            elif metric == 'ebitda':
                r['ebitda'] = v
            elif 'ebitda margin' in metric:
                r['ebitda_margin'] = pct
            elif 'free cash flow' in metric and 'per share' not in metric and 'margin' not in metric:
                r['free_cash_flow'] = v
        results[fy] = r
    return results

def parse_balance_by_year(table_data):
    results = {}
    for fy, data in table_data.items():
        r = {}
        for metric, val_text in data.items():
            v = parse_val(val_text)
            if 'cash & short-term' in metric or metric == 'cash & equivalents':
                r['cash_and_equivalents'] = v
            elif metric == 'total assets':
                r['total_assets'] = v
            elif 'total debt' in metric:
                r['total_debt'] = v
            elif 'total equity' in metric or "shareholders' equity" in metric:
                r['total_equity'] = v
        results[fy] = r
    return results

def parse_cashflow_by_year(table_data):
    results = {}
    for fy, data in table_data.items():
        r = {}
        for metric, val_text in data.items():
            v = parse_val(val_text)
            if metric == 'operating cash flow':
                r['operating_cash_flow'] = v
            elif 'capital expenditures' in metric:
                r['capital_expenditures'] = v
        results[fy] = r
    return results

def parse_ratios_by_year(table_data):
    results = {}
    for fy, data in table_data.items():
        r = {}
        for metric, val_text in data.items():
            v = parse_val(val_text)
            pct = parse_val(val_text.replace('%','')) if '%' in val_text else None
            if 'pb ratio' in metric:
                r['pb_ratio'] = v
            elif 'ps ratio' in metric:
                r['ps_ratio'] = v
            elif 'return on equity' in metric or metric == 'roe':
                r['roe'] = pct if pct is not None else v
            elif 'return on asset' in metric or metric == 'roa':
                r['roa'] = pct if pct is not None else v
            elif 'debt / equity' in metric:
                r['debt_to_equity'] = v
            elif 'ev/ebitda' in metric:
                r['ev_ebitda'] = v
            elif 'payout ratio' in metric:
                r['payout_ratio'] = pct
            elif 'earnings yield' in metric:
                r['earnings_yield'] = pct
            elif 'fcf yield' in metric:
                r['fcf_yield'] = pct
            elif 'enterprise value' in metric and 'ratio' not in metric:
                r['enterprise_value'] = v
            elif 'pe ratio' in metric and 'forward' not in metric:
                r['pe_ratio'] = v
            elif 'forward pe' in metric:
                r['forward_pe'] = v
        results[fy] = r
    return results

def scrape_overview(ticker):
    """Overview page — only current data (PE, dividend, dates, MA, etc.)"""
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
            result['eps_current'] = parse_val(raw)
        elif 'pe ratio' in label and 'forward' not in label:
            result['pe_ratio_current'] = parse_val(raw)
        elif 'forward pe' in label:
            result['forward_pe'] = parse_val(raw)
        elif label == 'dividend':
            result['dividend_per_share_current'] = parse_val(raw)
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

def scrape_statistics(ticker):
    """Statistics page — MA50, MA200, yields"""
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
        elif 'enterprise value' in label and 'ratio' not in label:
            result['enterprise_value'] = parse_val(raw)
    return result

def scrape_all_years(ticker):
    """
    Scrape all 5 years from all financial pages.
    Returns dict: {'FY2025': {...}, 'FY2024': {...}, ...}
    """
    # Income statement
    soup_inc = get_soup(f"https://stockanalysis.com/quote/brvm/{ticker}/financials/")
    inc_data, years_available = extract_table_by_year(soup_inc)
    income_by_year = parse_income_by_year(inc_data)

    # Balance sheet
    soup_bal = get_soup(f"https://stockanalysis.com/quote/brvm/{ticker}/financials/balance-sheet/")
    bal_data, _ = extract_table_by_year(soup_bal)
    balance_by_year = parse_balance_by_year(bal_data)

    # Cash flow
    soup_cf = get_soup(f"https://stockanalysis.com/quote/brvm/{ticker}/financials/cash-flow-statement/")
    cf_data, _ = extract_table_by_year(soup_cf)
    cashflow_by_year = parse_cashflow_by_year(cf_data)

    # Ratios
    soup_rat = get_soup(f"https://stockanalysis.com/quote/brvm/{ticker}/financials/ratios/")
    rat_data, _ = extract_table_by_year(soup_rat)
    ratios_by_year = parse_ratios_by_year(rat_data)

    # Merge all by year
    merged = {}
    for fy_raw in years_available:
        fy = FY_MAP.get(fy_raw, fy_raw)
        merged[fy] = {}
        merged[fy].update(income_by_year.get(fy_raw, {}))
        merged[fy].update(balance_by_year.get(fy_raw, {}))
        merged[fy].update(cashflow_by_year.get(fy_raw, {}))
        merged[fy].update(ratios_by_year.get(fy_raw, {}))

    return merged, years_available

def scrape_profile(ticker):
    """Profile: CEO, CFO, executives, employees"""
    soup = get_soup(f"https://stockanalysis.com/quote/brvm/{ticker}/company/")
    if not soup: return {'ticker': ticker}
    result = {'ticker': ticker}

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
        elif 'website' in label:
            result['website'] = value
        elif 'ceo' in label:
            result['ceo'] = value

    executives = []
    ceo = result.get('ceo')
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
                    if 'chief executive' in pos_lower or pos_lower == 'ceo':
                        ceo = name
                    elif 'chief financial' in pos_lower or pos_lower == 'cfo':
                        cfo = name

    if ceo: result['ceo'] = ceo
    if cfo: result['cfo'] = cfo
    if executives:
        result['other_executives'] = json.dumps(executives)

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

def insert_fundamental(record):
    clean = {k: v for k, v in record.items() if k in FUNDAMENTALS_ALLOWED and v is not None}
    # stockanalysis.com publie le dividende BRUT (avant IRVM).
    clean.setdefault('dividend_convention', 'BRUT')
    # on_conflict est OBLIGATOIRE : sans lui, PostgREST ignore quelle contrainte
    # cibler et l'INSERT viole company_fundamentals_company_id_fiscal_year_key
    # (HTTP 409). C'est la cause du gel des ecritures depuis le 27/05/2026.
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/company_fundamentals?on_conflict=company_id,fiscal_year",
        headers={
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'resolution=merge-duplicates'
        },
        json=clean
    )
    if r.status_code not in (200, 201, 204):
        print(f"  ECHEC upsert fundamentals {r.status_code}: {r.text[:400]}")
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
    test_tickers = ['SNTS', 'BOAC', 'LNBB', 'ETIT', 'SGBC']
    tickers = TICKERS if full_run else test_tickers

    print("="*60)
    print(f"BRVM Scraper v4 — 5 ans — {'FULL' if full_run else 'TEST'}")
    print(f"Date: {date.today()}")
    print("="*60)

    company_ids = get_company_ids()
    print(f"✅ {len(company_ids)} companies in Supabase\n")

    fund_ok, mgmt_ok = 0, 0
    fund_fail, mgmt_fail = [], []
    eps_warnings = []  # cf. check_eps_coherence — divergences eps scrapé vs recalculé
    total_rows = 0

    for i, ticker in enumerate(tickers):
        print(f"\n[{i+1}/{len(tickers)}] {ticker}")

        # --- OVERVIEW (current data only) ---
        overview = scrape_overview(ticker)
        stats = scrape_statistics(ticker)

        # --- 5 YEARS OF FINANCIAL DATA ---
        yearly_data, years_found = scrape_all_years(ticker)
        print(f"  📅 Years found: {[FY_MAP.get(y,y) for y in years_found]}")

        # --- INSERT ONE ROW PER YEAR ---
        ticker_rows = 0
        for fy_raw in years_found:
            fy = FY_MAP.get(fy_raw, fy_raw)
            row = yearly_data.get(fy, {})

            # Only add current/overview data to most recent year
            if fy == 'FY2025':
                row.update(overview)
                row.update(stats)
                # Fix field names from overview
                if 'pe_ratio_current' in row:
                    row['pe_ratio'] = row.pop('pe_ratio_current')
                if 'eps_current' in row:
                    row['eps'] = row.get('eps') or row.pop('eps_current')
                if 'dividend_per_share_current' in row:
                    row['dividend_per_share'] = row.get('dividend_per_share') or row.pop('dividend_per_share_current')

            row['ticker'] = ticker
            row['fiscal_year'] = fy
            row['company_id'] = company_ids.get(ticker)
            row['scraped_at'] = date.today().isoformat()

            # T4 (07/2026) : eps_recalcule (net_income/shares_outstanding) devient
            # la valeur primaire stockée dans company_fundamentals.eps. L'eps
            # scrapé (stockanalysis.com "EPS (Basic)") devient le cross-check :
            # conservé en fallback si le recalcul est impossible, et loggé en
            # cas de divergence (cf. check_eps_coherence).
            # GARDE-FOU DE SANITÉ : si le ratio eps_scrapé/eps_recalcule est hors
            # [0.2, 5] ou de signe incohérent, eps_recalcule est jugé non fiable
            # (bug connu : parse_val() n'applique pas le multiplicateur du
            # suffixe 'M' sur shares_outstanding, aggravé par des splits non
            # répercutés à la source pour certains tickers — cf. BACKLOG.md) et
            # row['eps'] N'EST PAS remplacé.
            SEUIL_RATIO_MIN, SEUIL_RATIO_MAX = 0.2, 5.0
            eps_scraped = row.get('eps')
            eps_recalcule, eps_warning = check_eps_coherence(
                eps_scraped, row.get('net_income'), overview.get('shares_outstanding'),
                ticker, fy
            )

            eps_overwrite_bloque = False
            if eps_recalcule is not None:
                if eps_scraped not in (None, 0):
                    if eps_recalcule == 0:
                        eps_overwrite_bloque = True
                    else:
                        ratio = eps_scraped / eps_recalcule
                        if ratio <= 0 or not (SEUIL_RATIO_MIN <= ratio <= SEUIL_RATIO_MAX):
                            eps_overwrite_bloque = True
                if not eps_overwrite_bloque:
                    row['eps'] = eps_recalcule
            # sinon (eps_recalcule None ou garde-fou déclenché) : row['eps']
            # reste la valeur scrapée (fallback déjà en place).

            if eps_warning:
                eps_warnings.append(eps_warning)
                print(f"  ⚠️  INCOHÉRENCE EPS : {eps_warning}")
            if eps_overwrite_bloque:
                garde_fou_msg = (
                    f"{ticker} {fy} : eps recalculé REJETÉ par le garde-fou de "
                    f"sanité (ratio scrapé/recalculé hors [{SEUIL_RATIO_MIN}, "
                    f"{SEUIL_RATIO_MAX}] ou signe incohérent) — eps scrapé conservé."
                )
                eps_warnings.append(garde_fou_msg)
                print(f"  🛑 {garde_fou_msg}")

            status = insert_fundamental(row)
            if status in [200, 201]:
                ticker_rows += 1
                total_rows += 1
            else:
                print(f"  ❌ {fy} failed [{status}]")

        if ticker_rows > 0:
            fund_ok += 1
            print(f"  💰 {ticker_rows} years inserted")
            print(f"     FY2025: Rev={yearly_data.get('FY2025',{}).get('revenue')} "
                  f"NI={yearly_data.get('FY2025',{}).get('net_income')} "
                  f"PE={yearly_data.get('FY2025',{}).get('pe_ratio') or overview.get('pe_ratio_current')} "
                  f"EarningsDate={overview.get('earnings_date')} "
                  f"ExDiv={overview.get('ex_dividend_date')}")
        else:
            fund_fail.append(ticker)

        # --- MANAGEMENT ---
        profile = scrape_profile(ticker)
        profile['company_id'] = company_ids.get(ticker)
        profile['scraped_at'] = date.today().isoformat()

        ms = upsert_management(profile)
        if ms in [200, 201]:
            mgmt_ok += 1
            print(f"  👤 CEO={profile.get('ceo')} CFO={profile.get('cfo')} Employees={profile.get('employees')}")
        else:
            mgmt_fail.append(ticker)
            print(f"  ❌ Management failed [{ms}]")

        time.sleep(3)

    print(f"\n{'='*60}")
    print(f"✅ Tickers with data: {fund_ok}/{len(tickers)}")
    print(f"✅ Total rows inserted: {total_rows}")
    print(f"✅ Management: {mgmt_ok}/{len(tickers)}")
    if fund_fail: print(f"❌ Fund failed: {fund_fail}")
    if mgmt_fail: print(f"❌ Mgmt failed: {mgmt_fail}")
    if eps_warnings:
        print(f"\n⚠️  {len(eps_warnings)} incohérence(s) EPS détectée(s) (cf. ADR-012 / investigation 25/06/2026) :")
        for w in eps_warnings:
            print(f"   - {w}")
        print("   👉 Aucune correction automatique appliquée — eps n'a pas été modifié.")
        print("   👉 Vérifier manuellement avant correction (cf. SKILL.md, ne jamais corriger sans cause racine confirmée).")
    if not full_run:
        print(f"\n👉 Pour lancer sur 47 tickers: python scrape_all_v4.py --full")
