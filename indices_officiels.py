# ── Compositions officielles BRVM 2026 ────────────────────────────────────────

# BRVM PRESTIGE 2026 (Avis N°001-2026 — en vigueur depuis 02 Jan 2026)
BRVM_PRESTIGE_2026 = [
    'ECOC', 'NTLC', 'ONTBF', 'ORAC', 'PALC', 'SGBC',
    'SIBC', 'SMBC', 'SNTS', 'SPHC', 'TTLC', 'TTLS',
]

# BRVM 30 (Avis N°002-2026 — en vigueur depuis 02 Jan 2026)
BRVM_30_2026 = [
    'SDSC',  # AFRICA GLOBAL LOGISTICS CI
    'SIVC',  # AIR LIQUIDE CI
    'BOABF', # BANK OF AFRICA BF
    'BOAB',  # BANK OF AFRICA BN
    'BOAC',  # BANK OF AFRICA CI
    'BOAM',  # BANK OF AFRICA ML
    'BOAN',  # BANK OF AFRICA NG
    'BOAS',  # BANK OF AFRICA SN
    'BICB',  # BIIC BENIN
    'CFAC',  # CFAO CI
    'CIEC',  # CIE CI
    'ECOC',  # ECOBANK CI
    'ETIT',  # ECOBANK TRANS. INCORP. TG
    'FTSC',  # FILTISAC CI
    'ONTBF', # ONATEL BF
    'ORGT',  # ORAGROUP TOGO
    'ORAC',  # ORANGE CI
    'PALC',  # PALM CI
    'SAFC',  # SAFCA CI
    'SPHC',  # SAPH CI
    'SGBC',  # SGB CI
    'STBC',  # SITAB CI
    'SIBC',  # SOCIETE IVOIRIENNE DE BANQUE
    'SOGC',  # SOGB CI
    'SLBC',  # SOLIBRA CI
    'SNTS',  # SONATEL SN
    'SCRC',  # SUCRIVOIRE
    'TTLC',  # TOTALENERGIES MARKETING CI
    'UNXC',  # UNIWAX CI
    'SHEC',  # VIVO ENERGY CI
]

# Analyse croisee
prestige_set = set(BRVM_PRESTIGE_2026)
brvm30_set   = set(BRVM_30_2026)

overlap      = prestige_set & brvm30_set
prestige_only = prestige_set - brvm30_set
brvm30_only  = brvm30_set - prestige_set

print(f"BRVM Prestige 2026 : {len(BRVM_PRESTIGE_2026)} societes")
print(f"BRVM 30 2026       : {len(BRVM_30_2026)} societes")
print()
print(f"Dans les DEUX (Prestige + BRVM 30) : {len(overlap)} societes")
print(sorted(overlap))
print()
print(f"Prestige UNIQUEMENT (pas dans BRVM 30) : {len(prestige_only)} societes")
print(sorted(prestige_only))
print()
print(f"BRVM 30 UNIQUEMENT (pas dans Prestige) : {len(brvm30_only)} societes")
print(sorted(brvm30_only))
print()

# Hierarchie a 3 niveaux pour le modele
print("=== HIERARCHIE 3 NIVEAUX POUR LE MODELE ===")
print(f"TIER 1 - PRESTIGE ({len(BRVM_PRESTIGE_2026)} tickers) : seuil ACHAT >= 60")
print(f"TIER 2 - LIQUID   ({len(brvm30_only)} tickers)  : seuil ACHAT >= 65")
print(f"TIER 3 - ILLIQUID (reste)        : seuil ACHAT >= 72")

# Tickers hors BRVM 30 = illiquides
tous_tickers = [
    'BICC','BNBC','BOAB','BOABF','BOAC','BOAM','BOAN','BOAS','CBIBF','CFAC',
    'CIEC','ECOC','ETIT','FTSC','LNBB','NEIC','NSBC','NTLC','ONTBF','ORAC',
    'ORGT','PALC','SAFC','SCRC','SDSC','SGBC','SHEC','SIBC','SICC','SIVC',
    'SLBC','SMBC','SNTS','SOGC','SPHC','STBC','TTLC','TTLS','UNXC','UNLC',
    'BICB','BOABF','SDSC','STBC'
]
illiquides = [t for t in tous_tickers if t not in brvm30_set and t not in prestige_set]
print(f"\nTICKERS ILLIQUIDES (hors BRVM 30 et Prestige) :")
print(sorted(set(illiquides)))

