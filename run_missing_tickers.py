import os, sys, logging, requests
from datetime import datetime
from fundamental_analyzer import BRVMAnalyzer

logging.basicConfig(level=logging.INFO)

MISSING = {'CBIBF', 'FTSC', 'BOAS', 'PRSC', 'SIVC'}
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

def save_via_rest(company_id, report, summary, ai_provider="mistral"):
    enhanced_summary = f"[Analysé par {ai_provider.upper()} — {datetime.now().strftime('%Y-%m-%d')}]\n\n{summary}"
    payload = {
        "company_id": company_id,
        "report_url": report['url'],
        "report_title": report['titre'],
        "report_date": str(report['date']) if report.get('date') else None,
        "analysis_summary": enhanced_summary,
    }
    resp = requests.post(f"{SUPABASE_URL}/rest/v1/fundamental_analysis", headers=HEADERS, json=payload)
    if resp.status_code in (200, 201):
        logging.info(f"    ✅ Sauvegardé via REST (Provider: {ai_provider.upper()})")
        return True
    else:
        logging.error(f"    ❌ Erreur REST: {resp.status_code} {resp.text}")
        return False

class PatchedAnalyzer(BRVMAnalyzer):
    def _load_analysis_memory_from_db(self):
        logging.info("📂 Mémoire vide — mode UPSERT forcé")
        self.analysis_memory = set()

    def connect_to_db(self):
        return None

    def _save_to_db(self, company_id, report, summary, ai_provider="mistral"):
        result = save_via_rest(company_id, report, summary, ai_provider)
        if result:
            self.analysis_memory.add(report['url'])
        return result

    def run_and_get_results(self):
        # Charger company_ids via REST
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/companies?select=symbol,id,name",
            headers=HEADERS
        )
        companies = resp.json()
        self.company_ids = {
            c["symbol"]: (c["id"], c.get("name", c["symbol"]))
            for c in companies
            if c["symbol"] in MISSING
        }
        logging.info(f"✅ {len(self.company_ids)} sociétés chargées via REST")

        self._load_analysis_memory_from_db()

        logging.info("🔍 Phase 1: Collecte des rapports...")
        all_reports = self._find_all_reports()

        logging.info("🤖 Phase 2: Analyse Mistral...")
        for symbol, (company_id, company_name) in self.company_ids.items():
            logging.info(f"\n📊 {symbol} - {company_name}")
            company_reports = all_reports.get(symbol, [])
            if not company_reports:
                logging.info(f"   ⏭️  Aucun rapport disponible")
                continue
            for report in company_reports[:3]:  # max 3 rapports par ticker
                if report['url'] in self.analysis_memory:
                    logging.info(f"   ⏭️  Déjà analysé: {report['titre']}")
                    continue
                logging.info(f"   📄 Analyse: {report['titre']}")
                summary = self._analyze_pdf_with_multi_ai(company_id, symbol, report)
                if summary:
                    self._save_to_db(company_id, report, summary)

analyzer = PatchedAnalyzer()
analyzer.symbol_to_slug = {
    k: v for k, v in analyzer.symbol_to_slug.items()
    if k in MISSING
}

print(f"Tickers à traiter : {list(analyzer.symbol_to_slug.keys())}")
analyzer.run_and_get_results()
