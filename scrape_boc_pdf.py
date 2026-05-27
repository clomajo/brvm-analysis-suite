#!/usr/bin/env python3
import os, ssl, urllib.request, fitz, re, requests
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()
URL_BASE = os.getenv("SUPABASE_URL","").rstrip("/")
KEY      = os.getenv("SUPABASE_SERVICE_ROLE_KEY","")
HEADERS  = {"apikey":KEY,"Authorization":f"Bearer {KEY}","Content-Type":"application/json"}

def get_pdf_url(d): return f"https://www.brvm.org/sites/default/files/boc_{d.strftime('%Y%m%d')}_2.pdf"

def download_pdf(url):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(url, context=ctx, timeout=30) as r: return r.read()

def find_latest_pdf():
    d = date.today()
    for _ in range(10):
        try:
            url = get_pdf_url(d)
            data = download_pdf(url)
            print(f"  PDF trouve: {url}")
            return data, d
        except: d -= timedelta(days=1)
    raise Exception("Aucun PDF trouve dans les 10 derniers jours")

def parse_number(s):
    if not s: return None
    s = str(s).strip().replace(" ","").replace(" ","").replace(",",".").replace("%","")
    try: return float(s)
    except: return None

def parse_date_fr(s):
    if not s or str(s).strip() in ["None",""]: return None
    s = str(s).strip()
    mois = {"janv.":"01","févr.":"02","mars":"03","avr.":"04","mai":"05",
            "juin":"06","juil.":"07","août":"08","sept.":"09","oct.":"10",
            "nov.":"11","déc.":"12","jan":"01","fev":"02","avr":"04",
            "jul":"07","aou":"08","sep":"09","oct":"10","nov":"11","dec":"12"}
    for fr,num in mois.items():
        s = s.replace(fr,num)
    s = re.sub(r"[.\\s]+","-",s).strip("-")
    for fmt in ["%d-%m-%y","%d-%m-%Y"]:
        try: return datetime.strptime(s,fmt).strftime("%Y-%m-%d")
        except: pass
    return None

def is_actions_table(cols):
    """Detecter les tables du marche des actions (16 colonnes, col 1 = symbole ticker)"""
    col_str = str(cols)
    # Format: 0-CB, 1-TICKER, 2-NOM, Col3, 4-cours_prec, 5-ouv, 6-clot, 7-var...
    return (len(cols) >= 16 and
            any(re.match(r"0-[A-Z]{2,3}$", str(c)) for c in cols[:2]))

def parse_row(row):
    """
    Index des colonnes dans le bulletin:
    0=code_secteur, 1=symbole, 2=titre, 3=vide,
    4=cours_prec, 5=ouv, 6=clot, 7=var_jour,
    8=volume, 9=valeur, 10=cours_ref, 11=var_annee,
    12=dividende, 13=date_div, 14=rdt_net, 15=per
    """
    try:
        sym = str(row[1]).strip() if row[1] else None
        if not sym or len(sym) < 2 or sym in ["None","nan"]: return None
        # Nettoyer symbole si prefixe numerique
        if re.match(r"^\d+-", sym): sym = sym.split("-",1)[1].strip()
        if not re.match(r"^[A-Z]{3,5}$", sym): return None
        return {
            "symbole":    sym,
            "cours_ref":  parse_number(row[10]) if len(row)>10 else None,
            "dividende":  parse_number(row[12]) if len(row)>12 else None,
            "date_div":   parse_date_fr(row[13]) if len(row)>13 else None,
            "rdt_net":    parse_number(row[14]) if len(row)>14 else None,
            "per":        parse_number(row[15]) if len(row)>15 else None,
        }
    except: return None

def parse_boc(data):
    doc = fitz.open(stream=data, filetype="pdf")
    records = {}
    for page in doc:
        tabs = page.find_tables()
        for tab in tabs.tables:
            df = tab.to_pandas()
            cols = list(df.columns)
            if not is_actions_table(cols): continue
            # Premiere ligne = donnees du premier ticker (dans les colonnes)
            # Extraire header ticker depuis col 1
            first_sym = str(cols[1]).split("-",1)[-1].strip() if "-" in str(cols[1]) else None
            if first_sym and re.match(r"^[A-Z]{3,5}$", first_sym):
                # Reconstruire la premiere ligne depuis les colonnes
                first_row = [str(c).split("-",1)[-1].strip() if re.match(r"^\d+-",str(c)) else str(c)
                             for c in cols]
                rec = parse_row(first_row)
                if rec: records[rec["symbole"]] = rec
            # Lignes suivantes
            for _, row in df.iterrows():
                vals = row.tolist()
                rec = parse_row(vals)
                if rec: records[rec["symbole"]] = rec
    return list(records.values())

def get_company_ids():
    r = requests.get(f"{URL_BASE}/rest/v1/companies?select=id,symbol",headers=HEADERS)
    return {row["symbol"]:row["id"] for row in r.json()}

def upsert_fundamentals(records, trade_date):
    company_ids = get_company_ids()
    fy = f"FY{trade_date.year}"
    upserts = []
    for rec in records:
        cid = company_ids.get(rec["symbole"])
        if not cid: continue
        upserts.append({
            "company_id":       cid,
            "ticker":           rec["symbole"],
            "fiscal_year":      fy,
            "pe_ratio":         rec["per"],
            "dividend_yield":   rec["rdt_net"],
            "dividend_per_share": rec["dividende"],
            "ex_dividend_date": rec["date_div"],
            "scraped_at":       datetime.utcnow().isoformat()
        })
    if not upserts: print("  Aucune donnee"); return
    r = requests.post(
        f"{URL_BASE}/rest/v1/company_fundamentals",
        headers={**HEADERS,"Prefer":"resolution=merge-duplicates"},
        json=upserts
    )
    print(f"  Upsert {len(upserts)} tickers: {r.status_code}")

def main():
    print("Recherche du dernier bulletin PDF BRVM...")
    data, trade_date = find_latest_pdf()
    print(f"  {len(data)} bytes")
    records = parse_boc(data)
    print(f"  {len(records)} tickers parses")
    for r in records[:5]: print(f"    {r}")
    upsert_fundamentals(records, trade_date)
    print("Termine.")

if __name__=="__main__": main()
