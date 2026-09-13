import os, csv, requests, datetime
from dotenv import load_dotenv
load_dotenv()
URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

STAMP = datetime.date.today().isoformat().replace("-", "")
os.makedirs("backups", exist_ok=True)

for t in ["brvm_decisions_results", "brvm_decisions_results_v2"]:
    rows, off = [], 0
    while True:
        r = requests.get(f"{URL}/rest/v1/{t}", headers=H,
            params={"select": "*", "order": "id.asc", "limit": 1000, "offset": off})
        if r.status_code != 200:
            print("ERR", t, r.text[:300]); rows = None; break
        b = r.json(); rows += b
        if len(b) < 1000: break
        off += 1000
    if not rows:
        print(f"{t}: ECHEC — on s'arrete"); continue
    path = f"backups/{t}_{STAMP}.csv"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"{t}: {len(rows)} lignes -> {path}")
