"""
Classification officielle des societes BRVM
Source: Avis officiels BRVM/DG
Mise a jour: avril 2026
"""

CLASSIFICATIONS = {

    # ── Jan 2023 — Creation des indices BRVM 30 et Prestige ──────────────────
    '2023-01-02': {
        'prestige': [
            'ETIT', 'NTLC', 'ONTBF', 'PALC', 'SGBC',
            'SMBC', 'SNTS', 'SPHC', 'TTLC', 'TTLS',
        ],
        'brvm30': [
            'BOAB', 'BOABF', 'BOAC', 'BOAN', 'BOAS', 'SDSC', 'CBIBF',
            'CFAC', 'CIEC', 'ECOC', 'ETIT', 'FTSC', 'NEIC', 'NTLC',
            'NSBC', 'ONTBF', 'ORGT', 'PALC', 'SPHC', 'SIBC', 'CABC',
            'SGBC', 'SDCC', 'SOGC', 'SNTS', 'SCRC', 'TTLC', 'TTLS',
            'UNXC', 'SHEC',
        ],
    },

    # ── Jan 2024 ──────────────────────────────────────────────────────────────
    '2024-01-02': {
        'prestige': [
            'NTLC', 'ONTBF', 'ORGT', 'PALC', 'SPHC',
            'SMBC', 'SGBC', 'SNTS', 'TTLC', 'TTLS',
        ],
        'brvm30': [
            'SIVC', 'BOABF', 'BOAB', 'BOAC', 'BOAM', 'BOAN', 'BOAS',
            'SDSC', 'CFAC', 'CIEC', 'CBIBF', 'SEMC', 'ECOC', 'ETIT',
            'FTSC', 'NTLC', 'NSBC', 'ONTBF', 'ORGT', 'ORAC', 'PALC',
            'SAFC', 'SIBC', 'SMBC', 'SGBC', 'SOGC', 'SNTS', 'SCRC',
            'TTLC', 'UNXC',
        ],
    },

    # ── Jan 2025 ──────────────────────────────────────────────────────────────
    '2025-01-02': {
        'prestige': [
            'ECOC', 'NTLC', 'NSBC', 'ONTBF', 'ORAC',
            'PALC', 'SGBC', 'SNTS', 'TTLC', 'TTLS',
        ],
        'brvm30': [
            'SDSC', 'BOABF', 'BOAB', 'BOAC', 'BOAM', 'BOAS', 'BICC',
            'CFAC', 'CIEC', 'CBIBF', 'ECOC', 'ETIT', 'FTSC', 'NTLC',
            'ONTBF', 'ORGT', 'ORAC', 'PALC', 'SPHC', 'STBC', 'SIBC',
            'SGBC', 'SOGC', 'SLBC', 'SNTS', 'SCRC', 'TTLC', 'UNXC',
            'SHEC',
        ],
    },

    # ── Jan 2026 ──────────────────────────────────────────────────────────────
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

    # ── Avr 2026 — Avis N°081-2026/BRVM/DG — en vigueur depuis 01 Avr 2026 ──
    # Entrants: CBIBF, NEIC, SEMC, STAC
    # Sortants: PALC, SAFC, SLBC, SOGC
    # Note: SIVC renommee ERIUM CI (ticker inchange)
    '2026-04-01': {
        'prestige': [
            'ECOC', 'NTLC', 'ONTBF', 'ORAC', 'PALC', 'SGBC',
            'SIBC', 'SMBC', 'SNTS', 'SPHC', 'TTLC', 'TTLS',
        ],
        'brvm30': [
            'SDSC', 'SIVC', 'BOABF', 'BOAB', 'BOAC', 'BOAM', 'BOAN', 'BOAS',
            'BICB', 'CFAC', 'CIEC', 'CBIBF', 'ECOC', 'ETIT', 'FTSC', 'NEIC',
            'ONTBF', 'ORGT', 'ORAC', 'SPHC', 'SGBC', 'STAC', 'STBC', 'SIBC',
            'SEMC', 'SNTS', 'SCRC', 'TTLC', 'UNXC', 'SHEC',
        ],
    },
}

SEUILS = {
    'prestige': 60,
    'liquid':   65,
    'illiquid': 72,
}


class BRVMClassifier:
    """Classification officielle des societes BRVM (Prestige / BRVM 30 / Illiquid)"""

    def __init__(self):
        self.classifications = CLASSIFICATIONS
        self.seuils = SEUILS
        self.dates_disponibles = sorted(self.classifications.keys())

    def get_tier(self, ticker, date=None):
        if date is None:
            date = '9999-12-31'
        date_str = str(date)[:10]

        date_classe = None
        for d in self.dates_disponibles:
            if d <= date_str:
                date_classe = d
            else:
                break

        if date_classe is None:
            date_classe = self.dates_disponibles[0]

        c = self.classifications[date_classe]
        if ticker in c['prestige']:
            return 'prestige'
        elif ticker in c['brvm30']:
            return 'liquid'
        else:
            return 'illiquid'

    def get_seuil_achat(self, ticker, date=None):
        return self.seuils[self.get_tier(ticker, date)]

    def is_liquid(self, ticker, date=None):
        return self.get_tier(ticker, date) != 'illiquid'


if __name__ == "__main__":
    c = BRVMClassifier()
    print("=== TEST PAR DATE ===")
    tests = [
        ('SGBC',  '2023-06-01'),
        ('SGBC',  '2024-06-01'),
        ('SGBC',  '2025-06-01'),
        ('SGBC',  '2026-04-06'),
        ('ETIT',  '2023-06-01'),
        ('ETIT',  '2024-06-01'),
        ('ORGT',  '2023-06-01'),
        ('ORGT',  '2024-06-01'),
        ('ECOC',  '2024-06-01'),
        ('ECOC',  '2025-06-01'),
        ('BICC',  '2026-04-06'),
        ('BNBC',  '2026-04-06'),
    ]
    print(f"{'Ticker':<8} {'Date':<12} {'Tier':<10} {'Seuil':>6}")
    print('-'*38)
    for ticker, date in tests:
        tier  = c.get_tier(ticker, date)
        seuil = c.get_seuil_achat(ticker, date)
        print(f"{ticker:<8} {date:<12} {tier:<10} {seuil:>6}")
