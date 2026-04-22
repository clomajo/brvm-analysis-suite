"""
scrape_corporate_events.py
Scrape dividendes et AG depuis Sikafinance + brvm.org
Alimente la table corporate_events dans Supabase
Tourne hebdomadairement dans GitHub Actions
"""

import os, re, time, requests, urllib3, json
from bs4 import BeautifulSoup
from datetime import date, datetime
from dotenv import load_dotenv

urllib3.disable_warnings()
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
})

# Mapping nom complet → ticker BRVM
NAME_TO_TICKER = {
    'BANK OF AFRICA BURKINA FASO': 'BOABF',
    'BANK OF AFRICA CI': 'BOAC',
    'BANK OF AFRICA BENIN': 'BOAB',
    'BANK OF AFRICA SENEGAL': 'BOAS',
    'BANK OF AFRICA MALI': 'BOAM',
    'BANK OF AFRICA NIGER': 'BOAN',
    'SONATEL': 'SNTS',
    'ORANGE CI': 'ORAC',
    'SOCIETE GENERALE CI': 'SGBC',
    'ECOBANK CI': 'ECOC',
    'ECOBANK TRANSNATIONAL': 'ETIT',
    'CORIS BANK': 'CBIBF',
    'NSIA BANQUE': 'NSBC',
    'SIB': 'SIBC',
    'PALM CI': 'PALC',
    'SAPH': 'SPHC',
    'ONATEL': 'ONTBF',
    'TOTAL CI': 'TTLC',
    'TOTAL SENEGAL': 'TTLS',
    'NESTLE CI': 'NTLC',
    'SOLIBRA': 'SLBC',
    'UNILEVER CI': 'UNLC',
    'SOGB': 'SOGC',
    'SUCRIVOIRE': 'SCRC',
    'SICOR': 'SICC',
    'FILTISAC': 'FTSC',
    'NEI-CEDA': 'NEIC',
    'SICABLE': 'CABC',
    'CFAO': 'CFAC',
    'TRACTAFRIC': 'PRSC',
    'VIVO ENERGY': 'SHEC',
    'CIE': 'CIEC',
    'SODECI': 'SDCC',
    'BOLLORE': 'SDSC',
    'SETAO': 'STAC',
    'SITAB': 'STBC',
    'BERNABE': 'BNBC',
    'SMB': 'SMBC',
    'CROWN SIEM': 'SEMC',
    'SERVAIR': 'ABJC',
    'SAFCA': 'SAFC',
    'ORAGROUP': 'ORGT',
    'UNIWAX': 'UNXC',
    'AIR LIQUIDE': 'SIVC',
    'LOTERIE NATIONALE BENIN': 'LNBB',
    'BICC': 'BICC',
}

def find_ticker(name):
    """Trouver le ticker depuis le nom complet."""
    name_upper = name.upper().strip()
    for key, ticker in NAME_TO_TICKER.items():
        if key in name_upper or name_upper in key:
            return ticker
    return None

def parse_date_fr(date_str):
    """Convertir '22/04/2026' en '2026-04-22'."""
    try:
        return datetime.strptime(date_str.strip(), '%d/%m/%Y').strftime('%Y-%m-%d')
    except:
        return None

def parse_amount(text):
    """Convertir '397,00' en 397.0."""
    try:
        return float(text.replace('\xa0','').replace(' ','').replace(',','.'))
    except:
        return None

def scrape_dividends():
    """Scrape calendrier dividendes depuis Sikafinance."""
    print("Scraping dividendes depuis Sikafinance...")
    url = 'https://www.sikafinance.com/marches/dividendes'
    r = SESSION.get(url, verify=False, timeout=15)
    if r.status_code != 200:
        print(f"  Erreur: {r.status_code}")
        return []

    soup = BeautifulSoup(r.text, 'html.parser')
    tables = soup.find_all('table')
    events = []

    # Table 0 — Dividendes 2026 avec dates
    if tables:
        rows = tables[0].find_all('tr')[1:]  # Skip header
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all('td')]
            if len(cells) >= 3:
                date_str = parse_date_fr(cells[0])
                name = cells[1]
                amount = parse_amount(cells[2])
                yield_pct = parse_amount(cells[3].replace('%','').replace(',','.')) if len(cells) > 3 else None
                ticker = find_ticker(name)

                if date_str and amount:
                    events.append({
                        'ticker': ticker,
                        'company_name': name,
                        'event_type': 'DIVIDEND',
                        'event_date': date_str,
                        'amount': amount,
                        'yield_pct': yield_pct,
                        'fiscal_year': '2025',
                        'source': 'sikafinance',
                        'scraped_at': date.today().isoformat()
                    })
                    print(f"  ✅ {ticker or name}: {amount} FCFA le {date_str}")

    # Table 1 — Historique dividendes 4 ans
    hist_events = []
    if len(tables) > 1:
        years = ['2022', '2023', '2024', '2025']
        rows = tables[1].find_all('tr')[1:]
        for row in rows:
            cells = row.find_all('td')
            if not cells: continue
            name = cells[0].get_text(strip=True)
            ticker = find_ticker(name)
            for j, year in enumerate(years):
                idx_div = 1 + j*2
                idx_rend = 2 + j*2
                if idx_div < len(cells):
                    div_text = cells[idx_div].get_text(strip=True)
                    rend_text = cells[idx_rend].get_text(strip=True) if idx_rend < len(cells) else None
                    amount = parse_amount(div_text)
                    yield_val = parse_amount(rend_text.replace('%','').replace(',','.')) if rend_text else None
                    if amount:
                        hist_events.append({
                            'ticker': ticker,
                            'company_name': name,
                            'event_type': 'DIVIDEND_HISTORY',
                            'event_date': f'{year}-12-31',
                            'amount': amount,
                            'yield_pct': yield_val,
                            'fiscal_year': str(int(year)-1),
                            'source': 'sikafinance_history',
                            'scraped_at': date.today().isoformat()
                        })

    print(f"  📊 {len(events)} dividendes 2026, {len(hist_events)} historiques")
    return events + hist_events

def get_company_ids():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/companies?select=id,symbol",
        headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
    )
    return {c['symbol']: c['id'] for c in r.json()} if r.status_code == 200 else {}

def upsert_events(events, company_ids):
    """Insérer les événements dans Supabase."""
    success = 0
    for event in events:
        ticker = event.get('ticker')
        if ticker:
            event['company_id'] = company_ids.get(ticker)

        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/corporate_events",
            headers={
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json',
                'Prefer': 'resolution=merge-duplicates'
            },
            json={k: v for k, v in event.items() if v is not None}
        )
        if r.status_code in [200, 201]:
            success += 1
    return success

if __name__ == '__main__':
    print("="*60)
    print(f"Corporate Events Scraper — {date.today()}")
    print("="*60)

    company_ids = get_company_ids()
    print(f"✅ {len(company_ids)} companies in Supabase\n")

    # Scrape dividendes
    events = scrape_dividends()

    print(f"\nTotal events: {len(events)}")
    print("\n⚠️  Créer la table corporate_events dans Supabase avant de continuer:")
    print("""
CREATE TABLE IF NOT EXISTS corporate_events (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    ticker TEXT,
    company_name TEXT,
    event_type TEXT,  -- DIVIDEND, DIVIDEND_HISTORY, AG, EARNINGS
    event_date DATE,
    amount NUMERIC,
    yield_pct NUMERIC,
    fiscal_year TEXT,
    source TEXT,
    notes TEXT,
    scraped_at DATE,
    UNIQUE(ticker, event_type, event_date)
);
""")

    confirm = input("Table créée? (o/n): ")
    if confirm.lower() == 'o':
        ok = upsert_events(events, company_ids)
        print(f"✅ {ok}/{len(events)} events insérés")
    else:
        print("Créer la table d'abord puis relancer.")


# ─────────────────────────────────────────────────────────────
# RICHBOURSE CALENDAR SCRAPER
# ─────────────────────────────────────────────────────────────

TITLE_TO_TICKER = {
    'BOA BURKINA': 'BOABF',
    'BOA SENEGAL': 'BOAS',
    'BOA MALI': 'BOAM',
    'BOA NIGER': 'BOAN',
    'BOA CI': 'BOAC',
    'BOA BENIN': 'BOAB',
    'SONATEL': 'SNTS',
    'ORANGE CI': 'ORAC',
    'CORIS BANK': 'CBIBF',
    'ONATEL': 'ONTBF',
    'ECOBANK CI': 'ECOC',
    'ECOBANK GROUP': 'ETIT',
    'SOCIETE GENERALE': 'SGBC',
    'PALM CI': 'PALC',
    'SAPH': 'SPHC',
    'TOTAL CI': 'TTLC',
    'TOTAL SENEGAL': 'TTLS',
    'NESTLE': 'NTLC',
    'SOLIBRA': 'SLBC',
    'UNILEVER': 'UNLC',
    'SOGB': 'SOGC',
    'SUCRIVOIRE': 'SCRC',
    'SICOR': 'SICC',
    'FILTISAC': 'FTSC',
    'NEI': 'NEIC',
    'SICABLE': 'CABC',
    'CFAO': 'CFAC',
    'TRACTAFRIC': 'PRSC',
    'VIVO ENERGY': 'SHEC',
    'CIE': 'CIEC',
    'SODECI': 'SDCC',
    'BOLLORE': 'SDSC',
    'SETAO': 'STAC',
    'SITAB': 'STBC',
    'BERNABE': 'BNBC',
    'SMB': 'SMBC',
    'BICI': 'BICC',
    'NSIA': 'NSBC',
    'SIB': 'SIBC',
    'ORAGROUP': 'ORGT',
    'LOTERIE': 'LNBB',
    'AIR LIQUIDE': 'SIVC',
}

def find_ticker_from_title(title):
    title_upper = title.upper()
    for key, ticker in TITLE_TO_TICKER.items():
        if key in title_upper:
            return ticker
    return None

def scrape_richbourse_calendar():
    """Scrape le calendrier JSON depuis RichBourse."""
    print("\nScraping calendrier depuis RichBourse API...")
    url = 'https://www.richbourse.com/outils/calendrier/events'
    r = SESSION.get(url, timeout=15, verify=False)
    if r.status_code != 200:
        print(f"  Erreur: {r.status_code}")
        return []

    data = r.json()
    events = []
    today = date.today()
    current_year = str(today.year)

    for item in data:
        title = item.get('title', '')
        start = item.get('start', '')
        color = item.get('color', '')
        if not start:
            continue

        event_date = start[:10]  # YYYY-MM-DD

        # Ignorer les jours fériés
        if 'férié' in title.lower() or 'rappel' in title.lower():
            continue

        # Déterminer le type
        title_lower = title.lower()
        if 'assemblée générale' in title_lower:
            event_type = 'AG'
            company = title.replace('Assemblée Générale', '').strip()
        elif 'cotation ex-dividende' in title_lower:
            event_type = 'EX_DIVIDEND'
            company = title.replace('Cotation ex-dividende', '').strip()
        elif 'paiement des dividendes' in title_lower:
            event_type = 'DIVIDEND_PAYMENT'
            company = title.replace('Paiement des dividendes', '').strip()
        else:
            continue

        ticker = find_ticker_from_title(company)
        fiscal_year = str(int(event_date[:4]) - 1)

        events.append({
            'ticker': ticker,
            'company_name': company.strip(),
            'event_type': event_type,
            'event_date': event_date,
            'fiscal_year': fiscal_year,
            'source': 'richbourse_calendar',
            'scraped_at': today.isoformat()
        })

    ag = len([e for e in events if e['event_type'] == 'AG'])
    div = len([e for e in events if 'DIVIDEND' in e['event_type']])
    print(f"  📊 {ag} AG + {div} événements dividendes ({len(events)} total)")
    return events


def run_full_scrape():
    """Scraper complet — dividendes Sikafinance + calendrier RichBourse."""
    company_ids = get_company_ids()
    print(f"✅ {len(company_ids)} companies in Supabase\n")

    # Dividendes depuis Sikafinance
    div_events = scrape_dividends()

    # Calendrier AG + dividendes depuis RichBourse
    cal_events = scrape_richbourse_calendar()

    all_events = div_events + cal_events
    print(f"\nTotal: {len(all_events)} events à insérer")

    ok = upsert_events(all_events, company_ids)
    print(f"✅ {ok}/{len(all_events)} events insérés/mis à jour")


if __name__ == '__main__':
    import sys
    print("="*60)
    print(f"Corporate Events Scraper v2 — {date.today()}")
    print("="*60)
    run_full_scrape()
