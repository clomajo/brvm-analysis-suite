import os
import json
import time
import requests
from supabase import create_client
from collections import defaultdict

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

PROMPT = """Tu es un analyste financier spécialisé en Afrique de l'Ouest.
Lis cette analyse financière d'une société cotée à la BRVM et réponds 
UNIQUEMENT en JSON valide, sans texte avant ou après :

{{
  "croissance_ca_pct": 6.7,
  "tendance": "hausse",
  "signal": "positif",
  "resume": "PNB +6.7% porté par hausse des crédits"
}}

Règles :
- croissance_ca_pct : croissance CA ou PNB en %, négatif si baisse, 0 si inconnu
- tendance : "hausse", "stable", ou "baisse"
- signal : "positif", "neutre", ou "négatif"
- resume : une phrase factuelle, max 100 caractères

Analyse :
{text}"""

def extract_signal(text):
    try:
        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "mistral-small-latest",
            "messages": [{"role": "user", "content": PROMPT.format(text=text[:3000])}],
            "temperature": 0.1
        }
        response = requests.post(MISTRAL_URL, headers=headers, json=data, timeout=60)
        raw = response.json()["choices"][0]["message"]["content"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"Erreur : {e}")
        return None

def main():
    analyses = supabase.table("fundamental_analysis")\
        .select("id, company_id, analysis_summary")\
        .not_.is_("analysis_summary", "null")\
        .execute()
    print(f"{len(analyses.data)} analyses trouvées")

    companies = supabase.table("companies")\
        .select("id, symbol")\
        .execute()
    id_to_ticker = {c["id"]: c["symbol"] for c in companies.data}

    by_company = defaultdict(list)
    for a in analyses.data:
        by_company[a["company_id"]].append(a)
    print(f"{len(by_company)} sociétés à traiter")

    for company_id, company_analyses in by_company.items():
        ticker = id_to_ticker.get(company_id, "???")
        best = max(company_analyses, key=lambda x: len(x["analysis_summary"] or ""))
        text = best["analysis_summary"]

        if not text or len(text) < 100:
            print(f"  {ticker} — texte trop court, ignoré")
            continue

        print(f"  {ticker}...", end=" ", flush=True)
        result = extract_signal(text)

        if not result:
            print("échec")
            continue

        supabase.table("company_fundamentals").upsert({
            "company_id": company_id,
            "ticker": ticker,
            "signal_fondamental": result.get("signal"),
            "resume_fondamental": result.get("resume"),
            "croissance_ca_pct": result.get("croissance_ca_pct"),
            "tendance_fondamentale": result.get("tendance"),
            "signal_date": "2026-04-30",
            "fiscal_year": "FY2025"
        }, on_conflict="company_id,fiscal_year").execute()

        print(f"{result.get('signal')} — {result.get('resume')}")
        time.sleep(0.5)

    print("\nTerminé.")

if __name__ == "__main__":
    main()
