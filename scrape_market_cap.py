#!/usr/bin/env python3
"""
scrape_market_cap.py — Scrape market_cap + shares_outstanding depuis stockanalysis.com
=======================================================================================
URL : https://stockanalysis.com/quote/brvm/{ticker}/statistics/

Usage :
    python3 scrape_market_cap.py          # dry run
    python3 scrape_market_cap.py --apply  # met à jour company_fundamentals
"""

import os
import sys
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS_SB = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

DRY_RUN = "--apply" not in sys.argv

TICKERS = [
    "ABJC","BICC","BNBC","BOAB","BOABF","BOAC","BOAM","BOAN","BOAS",
    "CABC","CBIBF","CFAC","CIEC","ECOC","ETIT","FTSC","LNBB","NEIC",
    "NSBC","NTLC","ONTBF","ORAC","ORGT","PALC","PRSC","SAFC","SCRC",
    "SDCC","SDSC","SEMC","SGBC","SHEC","SIBC","SICC","SIVC","SLBC",
    "SMBC","SNTS","SOGC","SPHC","STAC","STBC","TTLC","TTLS","UNLC","UNXC"
]

HEADERS_HTTP = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


def parse_value(text):
    """Parse '137.25B' → 137250000000, '27.45M' → 27450000, '1.23T' → 1230000000000"""
    if not text or text.strip() in ("n/a", "—", ""):
        return None
    text = text.strip().replace(",", "").replace(" ", "")
    multipliers = {"T": 1e12, "B": 1e9, "M": 1e6, "K": 1e3}
    for suffix, mult in multipliers.items():
        if text.endswith(suffix):
            try:
                return int(float(text[:-1]) * mult)
            except ValueError:
                return None
    try:
        return int(float(text))
    except ValueError:
        return None


def scrape_ticker(ticker):
    """Scrape market_cap et shares_outstanding pour un ticker."""
    url = f"https://stockanalysis.com/quote/brvm/{ticker.lower()}/statistics/"
    try:
        r = requests.get(url, headers=HEADERS_HTTP, timeout=15)
        if r.status_code != 200:
            return None, None, f"HTTP {r.status_code}"

        soup = BeautifulSoup(r.text, "html.parser")

        market_cap = None
        shares_outstanding = None

        # Chercher dans les tableaux
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)

                if "Market Cap" in label and market_cap is None:
                    market_cap = parse_value(value)
                elif "Shares Outstanding" in label and shares_outstanding is None:
                    shares_outstanding = parse_value(value)

        # Aussi chercher dans les divs (format alternatif)
        if market_cap is None:
            for div in soup.find_all(["div", "td", "span"]):
                text = div.get_text(strip=True)
                if "market cap" in text.lower() and ("B" in text or "T" in text):
                    # Chercher le frère ou enfant avec la valeur
                    parent = div.parent
                    if parent:
                        vals = [t for t in parent.get_text("|").split("|")
                                if any(c in t for c in ["B", "M", "T"]) and
                                any(c.isdigit() for c in t)]
                        for v in vals:
                            parsed = parse_value(v.strip())
                            if parsed and parsed > 1e8:
                                market_cap = parsed
                                break

        return market_cap, shares_outstanding, None

    except Exception as e:
        return None, None, str(e)


def update_supabase(ticker, market_cap, shares_outstanding):
    """Met à jour company_fundamentals pour le ticker (toutes les années)."""
    payload = {}
    if market_cap:
        payload["market_cap"] = market_cap
    if shares_outstanding:
        payload["shares_outstanding"] = shares_outstanding

    if not payload:
        return False

    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/company_fundamentals?ticker=eq.{ticker}",
        headers=HEADERS_SB,
        json=payload
    )
    return r.status_code in (200, 204)


def main():
    print("=" * 65)
    print(f"scrape_market_cap.py — {'DRY RUN' if DRY_RUN else 'APPLY MODE'}")
    print("=" * 65)

    results = []
    errors = []

    for ticker in TICKERS:
        market_cap, shares, error = scrape_ticker(ticker)
        time.sleep(1.5)  # Délai poli

        if error:
            errors.append((ticker, error))
            print(f"  ❌ {ticker:<6} : {error}")
            continue

        if not market_cap and not shares:
            errors.append((ticker, "aucune donnée trouvée"))
            print(f"  ⚠️  {ticker:<6} : aucune donnée trouvée")
            continue

        cap_str = f"{market_cap/1e9:.1f}B" if market_cap else "N/A"
        shr_str = f"{shares/1e6:.2f}M" if shares else "N/A"
        print(f"  ✅ {ticker:<6} : Cap={cap_str:<10} Shares={shr_str}")

        results.append((ticker, market_cap, shares))

        if not DRY_RUN and (market_cap or shares):
            ok = update_supabase(ticker, market_cap, shares)
            if not ok:
                print(f"       ⚠️  Erreur mise à jour Supabase pour {ticker}")

    print(f"\n{'='*65}")
    print(f"Scraped  : {len(results)}/{len(TICKERS)} tickers")
    print(f"Erreurs  : {len(errors)}")

    if errors:
        print(f"\nTickers en erreur :")
        for t, e in errors:
            print(f"  {t}: {e}")

    if DRY_RUN:
        print(f"\n→ Pour appliquer : python3 scrape_market_cap.py --apply")
    else:
        print(f"\n✅ Mise à jour Supabase terminée.")
        print(f"\nRelancer backtest_value.py pour valider le filtre cap+qualité :")
        print(f"  python3 backtest_value.py")


if __name__ == "__main__":
    main()
