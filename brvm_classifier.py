"""
Classification officielle des societes BRVM
Source: Avis officiels BRVM/DG
Mise a jour: janvier 2026
"""

# ── Compositions officielles ──────────────────────────────────────────────────

# Format: 'YYYY-MM-DD': {'prestige': [...], 'brvm30': [...]}
# Date = date d'entree en vigueur

CLASSIFICATIONS = {
    '2026-01-02': {
        'prestige': [
            'ECOC', 'NTLC', 'ONTBF', 'ORAC', 'PALC', 'SGBC',
            'SIBC', 'SMBC', 'SNTS', 'SPHC', 'TTLC', 'TTLS',
        ],
        'brvm30': [
            'SDSC', 'SIVC', 'BOABF', 'BOAB', 'BOAC', 'BOAM', 'BOAN', 'BOAS',
            'BICB', 'CFAC', 'CIEC', 'ECOC', 'ETIT', 'FTSC', 'ONTBF', 'ORGT',
            'ORAC', 'PALC', 'SAFC', 'SPHC', 'SGBC', 'STBC', 'SIBC', 'SOGC',
            'SLBC', 'SNTS', 'SCRC', 'TTLC', 'UNXC', 'SHEC',
        ],
    },
    # A completer avec les compositions historiques
    # '2025-01-02': { 'prestige': [...], 'brvm30': [...] },
    # '2024-01-02': { 'prestige': [...], 'brvm30': [...] },
    # '2023-01-02': { 'prestige': [...], 'brvm30': [...] },
}

# Seuils ACHAT par tier
SEUILS = {
    'prestige':  60,
    'liquid':    65,
    'illiquid':  72,
}


class BRVMClassifier:
    """Classification officielle des societes BRVM (Prestige / BRVM 30 / Illiquid)"""

    def __init__(self):
        self.classifications = CLASSIFICATIONS
        self.seuils = SEUILS
        self.dates_disponibles = sorted(self.classifications.keys())

    def get_tier(self, ticker, date=None):
        """Retourne le tier d'un ticker a une date donnee."""
        if date is None:
            date = '9999-12-31'
        date_str = str(date)[:10]

        # Trouver la classification la plus recente <= date
        date_classe = None
        for d in self.dates_disponibles:
            if d <= date_str:
                date_classe = d
            else:
                break

        if date_classe is None:
            # Avant toute classification officielle — utiliser la plus ancienne
            date_classe = self.dates_disponibles[0]

        c = self.classifications[date_classe]
        if ticker in c['prestige']:
            return 'prestige'
        elif ticker in c['brvm30']:
            return 'liquid'
        else:
            return 'illiquid'

    def get_seuil_achat(self, ticker, date=None):
        """Retourne le seuil d'ACHAT pour un ticker."""
        tier = self.get_tier(ticker, date)
        return self.seuils[tier]

    def is_liquid(self, ticker, date=None):
        """Compatibilite avec l'ancien systeme is_liquid."""
        return self.get_tier(ticker, date) != 'illiquid'


# ── Test rapide ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    c = BRVMClassifier()
    tests = [
        ('SGBC',  '2026-04-06'),
        ('SIVC',  '2026-04-06'),
        ('BICC',  '2026-04-06'),
        ('NTLC',  '2026-04-06'),
        ('BOAC',  '2026-04-06'),
    ]
    print(f"{'Ticker':<8} {'Tier':<10} {'Seuil ACHAT':>12}")
    print('-' * 32)
    for ticker, date in tests:
        tier  = c.get_tier(ticker, date)
        seuil = c.get_seuil_achat(ticker, date)
        print(f"{ticker:<8} {tier:<10} {seuil:>12}")
