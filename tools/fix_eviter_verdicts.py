"""Corrige signal_correct pour les lignes EVITER (bug accent ÉVITER).
Ne touche QUE signal_correct. Aucun autre champ modifie."""
import os, sys, requests, argparse
from dotenv import load_dotenv
load_dotenv()

URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

a = argparse.ArgumentParser()
a.add_argument("--table", required=True)
a.add_argument("--apply", action="store_true")
a = a.parse_args()

rows, off = [], 0
while True:
    r = requests.get(f"{URL}/rest/v1/{a.table}", headers=H,
        params={"select": "id,signal,signal_correct,variation_pct",
                "signal": "eq.EVITER", "order": "id.asc",
                "limit": 1000, "offset": off})
    if r.status_code != 200: print("ERR", r.text[:300]); sys.exit(1)
    b = r.json(); rows += b
    if len(b) < 1000: break
    off += 1000

print(f"{a.table}: {len(rows)} lignes EVITER")
bad = [r for r in rows if r["signal_correct"] != ((r["variation_pct"] or 0) < 0)]
print(f"  verdicts a corriger: {len(bad)}")
print(f"  hit rate  avant: {sum(1 for r in rows if r['signal_correct'])}/{len(rows)}")
print(f"  hit rate  apres: {sum(1 for r in rows if (r['variation_pct'] or 0) < 0)}/{len(rows)}")

if not a.apply:
    print("\nDRY RUN — aucune ecriture. Relancer avec --apply")
    sys.exit(0)

n = 0
for r in bad:
    new = (r["variation_pct"] or 0) < 0
    p = requests.patch(f"{URL}/rest/v1/{a.table}", headers={**H,
        "Content-Type": "application/json", "Prefer": "return=minimal"},
        params={"id": f"eq.{r['id']}"}, json={"signal_correct": new}, timeout=30)
    if p.status_code >= 400:
        print("ECHEC id", r["id"], p.text[:200]); sys.exit(1)
    n += 1
    if n % 50 == 0: print(f"  {n}/{len(bad)}")
print(f"TERMINE — {n} lignes corrigees dans {a.table}")
