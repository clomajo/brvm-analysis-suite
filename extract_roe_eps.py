# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
extract_roe_eps.py
==================
Extrait ROE, EPS, et dividendes historiques depuis fundamental_analysis
(analyses Mistral FY2025) et met à jour company_fundamentals via Supabase REST.

ADR-nouveau : Extraction ROE/EPS — Couche 2 du modèle Fair Value V3
Auteur      : BRVM Analytics
Date        : 2026-06-04
"""

import os
import json
import time
import requests
from dotenv import load_dotenv, find_dotenv

# ── Environnement ──────────────────────────────────────────────────────────────
load_dotenv(find_dotenv(usecwd=True))

SUPABASE_URL      = os.environ["SUPABASE_URL"]
SUPABASE_KEY      = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
MISTRAL_API_KEY   = os.environ["MISTRAL_API_KEY"]

HEADERS_SB = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-large-latest"

# ── Helpers Supabase ───────────────────────────────────────────────────────────

def sb_get(table: str, params: dict) -> list:
    """GET depuis Supabase REST."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers={**HEADERS_SB, "Range": "0-999"},
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def sb_patch(table: str, filters: dict, payload: dict) -> None:
    """PATCH une ligne dans Supabase REST."""
    params = {k: f"eq.{v}" for k, v in filters.items()}
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=HEADERS_SB,
        params=params,
        json=payload,
        timeout=30,
    )
    r.raise_for_status()


# ── Extraction Mistral ─────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """Tu es un analyste financier expert des marchés africains.

Voici une analyse fondamentale d'une société cotée sur la BRVM :

---
{analyse_text}
---

Extrais les données financières suivantes en JSON strict (pas de markdown, pas de commentaires) :

{{
  "roe": <float ou null>,           // Return on Equity en % (ex: 15.3)
  "eps": <float ou null>,           // Bénéfice Par Action (BPA) en FCFA (ex: 1250.0) — chercher aussi "BPA", "bénéfice par action", "résultat par action"
  "dps_fy": <float ou null>,        // Dividende Par Action FY2025 en FCFA (ex: 400.0)
  "revenue_growth_pct": <float ou null>, // Croissance CA/PNB/chiffre d'affaires en % (ex: 8.5) — chercher "hausse de X%", "progression de X%", "en hausse de X%"
  "net_margin_pct": <float ou null>,     // Marge nette en % (ex: 12.1)
  "confidence": "high" | "medium" | "low"  // Ta confiance dans l'extraction
}}

Règles strictes :
- Retourne UNIQUEMENT le JSON, sans aucun texte avant ou après
- Si une valeur n'est pas mentionnée dans le texte, retourne null
- Ne jamais inventer une valeur — null vaut mieux qu'une valeur fausse
- Les % sont des nombres (ex: 15.3, pas "15.3%")
- Les montants sont en FCFA (pas en millions sauf si l'analyse est en millions, auquel cas convertis)
"""


def extract_with_mistral(analyse_text: str, symbol: str) -> dict | None:
    """Envoie l'analyse Mistral à Mistral pour extraction structurée."""
    prompt = EXTRACTION_PROMPT.format(analyse_text=analyse_text[:2000])  # réduit pour free tier

    payload = {
        "model": MISTRAL_MODEL,
        "temperature": 0.0,
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        r = requests.post(
            MISTRAL_URL,
            headers={
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=45,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()

        # Nettoyage JSON si Mistral ajoute des backticks malgré la consigne
        content = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)
        return data

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print(f"  ⏳ Rate limit Mistral pour {symbol} — attente 60s...")
            time.sleep(60)
            # 1 retry
            try:
                r2 = requests.post(
                    MISTRAL_URL,
                    headers={"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"},
                    json=payload, timeout=45,
                )
                r2.raise_for_status()
                content2 = r2.json()["choices"][0]["message"]["content"].strip()
                content2 = content2.replace("```json", "").replace("```", "").strip()
                return json.loads(content2)
            except Exception as e2:
                print(f"  ⚠️  Retry échoué pour {symbol}: {e2}")
                return None
        print(f"  ⚠️  Erreur HTTP Mistral pour {symbol}: {e}")
        return None
    except (json.JSONDecodeError, KeyError, requests.RequestException) as e:
        print(f"  ⚠️  Erreur extraction Mistral pour {symbol}: {e}")
        return None


# ── Pipeline principal ─────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("extract_roe_eps.py — Extraction ROE/EPS depuis Mistral")
    print("=" * 60)

    # 1. Inspecter les colonnes disponibles puis récupérer toutes les analyses
    print("\n📥 Inspection + récupération fundamental_analysis...")
    sample = sb_get("fundamental_analysis", {"select": "*", "limit": "1"})
    if not sample:
        print("   Table vide ou inaccessible"); return
    cols = list(sample[0].keys())
    print(f"   Colonnes : {cols}")

    analyses = sb_get("fundamental_analysis", {"select": "company_id,analysis_summary,updated_at", "order": "updated_at.desc"})
    print(f"   → {len(analyses)} analyses trouvées")

    # 2. Récupérer le mapping company_id → symbol
    companies = sb_get("companies", {"select": "id,symbol,name"})
    id_to_symbol = {c["id"]: c["symbol"] for c in companies}
    print(f"   → {len(companies)} sociétés mappées")

    # 3. Récupérer l'état actuel de company_fundamentals (FY2025)
    existing = sb_get("company_fundamentals", {
        "select": "company_id,fiscal_year,roe,eps,revenue_growth",
        "fiscal_year": "eq.FY2025",
    })
    existing_ids = {e["company_id"] for e in existing if e.get("roe") is not None}
    print(f"   → {len(existing_ids)} tickers ont déjà un ROE en FY2025")

    # 4. Traitement ticker par ticker
    results = {
        "success": 0,
        "skipped": 0,
        "errors":  0,
        "no_data": 0,
    }

    for analyse in analyses:
        company_id = analyse["company_id"]
        symbol = id_to_symbol.get(company_id, f"ID:{company_id}")

        # Le contenu est dans analysis_summary
        texte = analyse.get("analysis_summary") or ""

        # Skip seulement si ROE ET EPS déjà présents
        existing_row = next((e for e in existing if e["company_id"] == company_id), None)
        if existing_row and existing_row.get("roe") is not None and existing_row.get("eps") is not None:
            print(f"  ⏭  {symbol:<8} — ROE+EPS déjà présents, ignoré")
            results["skipped"] += 1
            continue

        if len(texte) < 50:
            print(f"  ⏭  {symbol:<8} — texte trop court, ignoré")
            results["no_data"] += 1
            continue

        print(f"  🔍 {symbol:<8} — extraction en cours...", end=" ")

        # Extraction Mistral
        extracted = extract_with_mistral(texte, symbol)

        if not extracted:
            print("ERREUR")
            results["errors"] += 1
            continue

        # Construire le payload de mise à jour
        payload = {}
        if extracted.get("roe") is not None:
            payload["roe"] = extracted["roe"]
        if extracted.get("eps") is not None:
            payload["eps"] = extracted["eps"]
        if extracted.get("revenue_growth_pct") is not None:
            payload["revenue_growth"] = extracted["revenue_growth_pct"]
        # net_margin non présent dans company_fundamentals — ignoré
        # if extracted.get("net_margin_pct") is not None:
        #     payload["net_margin"] = extracted["net_margin_pct"]

        if not payload:
            print(f"null (confiance: {extracted.get('confidence', '?')})")
            results["no_data"] += 1
            continue

        confidence = extracted.get("confidence", "?")
        roe_val = extracted.get("roe", "null")
        eps_val = extracted.get("eps", "null")
        print(f"ROE={roe_val}% | EPS={eps_val} FCFA | confiance={confidence}")

        # PATCH dans company_fundamentals (FY2025)
        try:
            sb_patch(
                "company_fundamentals",
                {"company_id": company_id, "fiscal_year": "FY2025"},
                payload,
            )
            results["success"] += 1
        except requests.HTTPError as e:
            print(f"    ❌ PATCH échoué: {e.response.text[:200]}")
            results["errors"] += 1

        # Délai pour respecter rate limit Mistral (free tier = ~1 req/sec)
        time.sleep(3.0)

    # 5. Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ")
    print(f"   ✅ Mis à jour  : {results['success']}")
    print(f"   ⏭  Ignorés     : {results['skipped']}")
    print(f"   ⚠️  Null/vide   : {results['no_data']}")
    print(f"   ❌ Erreurs     : {results['errors']}")
    print("=" * 60)

    # 6. Vérification post-run
    print("\n🔎 Vérification post-run...")
    updated = sb_get("company_fundamentals", {
        "select": "company_id,fiscal_year,roe,eps",
        "fiscal_year": "eq.FY2025",
        "roe":         "not.is.null",
    })
    symbols_updated = [id_to_symbol.get(u["company_id"], "?") for u in updated]
    print(f"   → {len(updated)} tickers avec ROE non-null en FY2025")
    print(f"   → {', '.join(sorted(symbols_updated))}")


if __name__ == "__main__":
    main()
