#!/usr/bin/env python3
import os, re, sys, json, logging, requests
from io import BytesIO
from datetime import date
from supabase import create_client, Client
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBox

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
CDN_BASE = "https://cdn-media.web-view.net/i/zexxawdwssuc"
ECART_SEUIL = 0.5
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TICKER_MAP = {
    "SUCRIVOIRE": "SCRC", "AFRICA GLOBAL LOGISTICS": "SIVC", "AGL": "SIVC",
    "CROWN SIEM": "CIEC", "CIE CI": "CIEC", "CIE": "CIEC",
    "SMB": "SMBC", "ORAGROUP": "ORGT", "UNIWAX": "UNXC",
    "ORANGE CI": "ORAC", "ORANGE": "ORAC", "NESTLE": "NTLC",
    "BIIC": "BICB", "SONATEL": "SNTS", "SITAB": "STAC",
    "PALM": "PALC", "SAPH": "SPHC", "ERIUM": "EIMC",
    "CFAO": "CFAC", "TOTAL CI": "TTLC", "TOTAL SN": "TTLS",
    "VIVO ENERGY": "SLBC", "FILTISAC": "FTSC", "SETAO": "SETAO",
    "SICABLE": "CABC", "BICI": "BICI", "BOA BF": "BOABF",
    "BOA BN": "BOAB", "BOA CI": "BOAC", "BOA ML": "BOAM",
    "BOA NG": "BOAN", "BOA SN": "BOAS", "CORIS BANK": "CBIBF",
    "ECOBANK": "ECOBANK", "ETI": "ETIT", "NSIA BANQUE": "NSAC",
    "SAFCA": "SAFC", "SIB": "SIBC", "SOCIETE GENERALE": "SGBC",
    "SODE": "SDCC", "ONATEL": "ONTBF", "BERNABE": "BNBC",
    "LOTTERIE": "LNBB", "NEI-CEDA": "NEIC", "SERVAIR": "SEMC",
    "TRACTAFRIC": "TTRC", "SICOR": "SICC", "SOGB": "SOGB",
    "SOLIBRA": "SLBC", "UNILEVER": "UNLC",
}

def build_url(d): return f"{CDN_BASE}/Lettre_quotidienne_{d.strftime('%d-%m-%Y')}.pdf"

def download_pdf(url):
    import urllib3; urllib3.disable_warnings()
    log.info(f"Telechargement: {url}")
    r = requests.get(url, timeout=30, verify=False)
    if not r.ok:
        log.error(f"DIAG status={r.status_code}")
        log.error(f"DIAG headers={dict(r.headers)}")
        log.error(f"DIAG body[:500]={r.text[:500]!r}")
    r.raise_for_status()
    log.info(f"PDF ({len(r.content):,} bytes)")
    return BytesIO(r.content)

def extract_text_by_page(pdf_bytes):
    pages = []
    pdf_bytes.seek(0)
    for page_layout in extract_pages(pdf_bytes):
        lines = [el.get_text().strip() for el in page_layout if isinstance(el, LTTextBox)]
        pages.append("\n".join(lines))
    return pages

def safe_float(val):
    if val is None: return None
    s = str(val).strip().replace("\xa0","").replace(" ","").replace(",",".").replace("%","").replace("x","").replace("\u2212","-").replace("\u2013","-")
    if s in ("","ns","nd","s","-","n/s","n/d"): return None
    try: return float(s)
    except: return None

def extract_ticker(nom):
    u = nom.upper()
    for k,v in TICKER_MAP.items():
        if k in u: return v
    w = u.split()
    return w[0][:4] if w else nom[:4].upper()

def load_company_map():
    companies = supabase.table("companies").select("id,symbol").execute().data
    return {c["symbol"]: c["id"] for c in companies}

def parse_page1(text):
    r = {"brvm_c":None,"brvm_c_perf":None,"brvm_c_ytd":None,
         "brvm_30":None,"brvm_30_perf":None,"brvm_30_ytd":None,
         "volume_marche":None,"top_valeurs":[],"flop_valeurs":[],"top_secteurs":[],"infos_jour":{}}
    pts = re.findall(r"([\d\s]+[,.]?\d*)\s*pts", text)
    if len(pts)>=1: r["brvm_c"]  = safe_float(pts[0])
    if len(pts)>=2: r["brvm_30"] = safe_float(pts[1])
    perfs = re.findall(r"([+-][\d,]+)%\s*\|([+-][\d,]+)%", text)
    if len(perfs)>=1: r["brvm_c_perf"],r["brvm_c_ytd"]   = safe_float(perfs[0][0]),safe_float(perfs[0][1])
    if len(perfs)>=2: r["brvm_30_perf"],r["brvm_30_ytd"] = safe_float(perfs[1][0]),safe_float(perfs[1][1])
    m = re.search(r"FCFA\s+([\d\s]+[,.]?\d+)\s*Md", text)
    if m: r["volume_marche"] = safe_float(m.group(1))
    flop = False
    for line in text.split("\n"):
        if "FLOP" in line.upper(): flop = True
        if "TOP VALEURS" in line.upper(): flop = False
        m = re.search(r"(\d)\.\s+(.+?)\s*\|\s*FCFA\s+([\d\s]+)\s*\|\s*([+-][\d,]+)%\s*\|\s*([\d\s]+)\s*titres", line)
        if m:
            e = {"rang":int(m.group(1)),"ticker":extract_ticker(m.group(2)),"nom":m.group(2).strip(),
                 "cours":safe_float(m.group(3)),"variation":safe_float(m.group(4)),"volume":safe_float(m.group(5).replace(" ",""))}
            (r["flop_valeurs"] if flop else r["top_valeurs"]).append(e)
        m2 = re.search(r"\d\.\s+(BRVM\s+[\w\s.]+?)\s*\|\s*([\d,]+)\s*\|\s*([+-][\d,]+)%\s*\|\s*([+-][\d,]+)%", line)
        if m2:
            r["top_secteurs"].append({"secteur":m2.group(1).strip(),"index":safe_float(m2.group(2)),
                                      "perf_jour":safe_float(m2.group(3)),"perf_ytd":safe_float(m2.group(4))})
    log.info(f"Page1 BRVM-C:{r['brvm_c']} BRVM-30:{r['brvm_30']} Top:{len(r['top_valeurs'])} Flop:{len(r['flop_valeurs'])}")
    return r

def parse_page2(text):
    rows = []
    skip = ["VALEUR","TOTAL MARCHE","CONSOMMATION","ENERGIE","INDUSTRIELS","SERVICES","TELECOM","NB :","BPA","P/E","2023","2024"]
    for line in text.split("\n"):
        line = line.strip()
        if not line or len(line)<10: continue
        if any(k in line.upper() for k in skip): continue
        nums = re.findall(r"[-]?[\d]+(?:[,][\d]+)?", line)
        if len(nums)<4: continue
        ticker = None
        for k,v in TICKER_MAP.items():
            if line.upper().startswith(k): ticker = v; break
        if not ticker: ticker = extract_ticker(line.split()[0] if line.split() else line)
        cours = safe_float(nums[0])
        if not cours or cours < 50: continue
        rows.append({
            "nom":line.split()[0],"ticker":ticker,"cours":cours,
            "perf_ytd":safe_float(nums[2]) if len(nums)>2 else None,
            "bpa_2023":safe_float(nums[3]) if len(nums)>3 else None,
            "bpa_2024":safe_float(nums[4]) if len(nums)>4 else None,
            "pe_2023":safe_float(nums[5]) if len(nums)>5 else None,
            "pe_2024":safe_float(nums[6]) if len(nums)>6 else None,
            "dy_2023":safe_float(nums[7]) if len(nums)>7 else None,
            "dy_2024":safe_float(nums[8]) if len(nums)>8 else None,
            "pb_2023":safe_float(nums[9]) if len(nums)>9 else None,
            "pb_2024":safe_float(nums[10]) if len(nums)>10 else None,
            "capitalisation":safe_float(nums[-1]) if len(nums)>11 else None,
        })
    log.info(f"Page2 {len(rows)} tickers")
    return rows

def upsert_boa_letter(d, url, p1, raw):
    supabase.table("boa_letters").upsert({
        "date":d.isoformat(),"pdf_url":url,
        "brvm_c":p1["brvm_c"],"brvm_c_perf":p1["brvm_c_perf"],"brvm_c_ytd":p1["brvm_c_ytd"],
        "brvm_30":p1["brvm_30"],"brvm_30_perf":p1["brvm_30_perf"],"brvm_30_ytd":p1["brvm_30_ytd"],
        "volume_marche":p1["volume_marche"],
        "top_valeurs":json.dumps(p1["top_valeurs"]),"flop_valeurs":json.dumps(p1["flop_valeurs"]),
        "top_secteurs":json.dumps(p1["top_secteurs"]),"infos_jour":json.dumps(p1["infos_jour"]),
        "raw_json":json.dumps(raw),
    }, on_conflict="date").execute()
    log.info(f"boa_letters OK {d}")

def upsert_boa_fundamentals(d, rows):
    if not rows: log.info("boa_fundamentals: 0 tickers (page2 vide)"); return
    records = [{"date":d.isoformat(),"ticker":r["ticker"],"cours":r["cours"],
        "perf_ytd":r["perf_ytd"],"bpa_2023":r["bpa_2023"],"bpa_2024":r["bpa_2024"],
        "pe_2023":r["pe_2023"],"pe_2024":r["pe_2024"],"dy_2023":r["dy_2023"],"dy_2024":r["dy_2024"],
        "pb_2023":r["pb_2023"],"pb_2024":r["pb_2024"],"capitalisation":r["capitalisation"]} for r in rows]
    supabase.table("boa_fundamentals").upsert(records, on_conflict="date,ticker").execute()
    log.info(f"boa_fundamentals {len(records)} OK")

def backfill_historical_data(d, rows):
    if not rows: return
    sym_to_id = load_company_map()
    existing = {r["company_id"] for r in supabase.table("historical_data").select("company_id").eq("trade_date",d.isoformat()).execute().data}
    n = 0
    for r in rows:
        cid = sym_to_id.get(r["ticker"])
        if cid and cid not in existing and r["cours"]:
            try:
                supabase.table("historical_data").insert({"company_id":cid,"trade_date":d.isoformat(),"price":r["cours"]}).execute()
                n += 1
            except Exception as e: log.warning(f"Backfill {r['ticker']}: {e}")
    log.info(f"Backfill {n} cours")

def _build_log(d, ticker, champ, vb, vp):
    statut,ea,ep = "OK",None,None
    if vb is None and vp is None: statut="MANQUANT_BOA_ET_PIPELINE"
    elif vb is None: statut="MANQUANT_BOA"
    elif vp is None: statut="MANQUANT_PIPELINE"
    else:
        ea = abs(vb-vp); ep = (ea/vp*100) if vp else None
        if ep and ep>ECART_SEUIL: statut="ECART"
    return {"date":d.isoformat(),"ticker":ticker,"champ":champ,"valeur_boa":vb,"valeur_pipeline":vp,"ecart_abs":ea,"ecart_pct":ep,"statut":statut}

def validate_and_log(d, p1, rows):
    ql = []
    sym_to_id = load_company_map()
    hist = supabase.table("historical_data").select("company_id,price").eq("trade_date",d.isoformat()).execute().data
    id_to_price = {r["company_id"]:r["price"] for r in hist}
    for r in rows:
        cid = sym_to_id.get(r["ticker"])
        vp = id_to_price.get(cid) if cid else None
        ql.append(_build_log(d,r["ticker"],"cours",r["cours"],vp))
    if ql:
        supabase.table("boa_data_quality_log").insert(ql).execute()
        ok = sum(1 for l in ql if l["statut"]=="OK")
        ec = sum(1 for l in ql if l["statut"]=="ECART")
        mn = sum(1 for l in ql if "MANQUANT" in l["statut"])
        log.info(f"Quality: {ok} OK | {ec} ECARTS | {mn} MANQUANTS")

def main():
    target_date = date.fromisoformat(sys.argv[1]) if len(sys.argv)>1 else date.today()
    log.info(f"=== {target_date} ===")
    pdf_url = build_url(target_date)
    try: pdf_bytes = download_pdf(pdf_url)
    except requests.HTTPError as e: log.error(f"PDF non dispo: {e}"); sys.exit(1)
    pages = extract_text_by_page(pdf_bytes)
    if len(pages)<2: log.error(f"PDF incomplet: {len(pages)} pages"); sys.exit(1)
    p1 = parse_page1(pages[0])
    p2 = parse_page2(pages[1])
    upsert_boa_letter(target_date, pdf_url, p1, {"page1":p1,"page2":p2})
    upsert_boa_fundamentals(target_date, p2)
    backfill_historical_data(target_date, p2)
    validate_and_log(target_date, p1, p2)
    log.info(f"=== Termine ===")

if __name__ == "__main__":
    main()
