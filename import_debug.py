#!/usr/bin/env python3
"""
Debug import to see why files are being skipped
"""

import os
import sys
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

FOLDER = '/Users/kaylam/Downloads/Historical Data BRVM 10Y/'

FILENAME_TO_SYMBOL = {
    'BICICI': 'BICC',
    'BANK OF AFRICA - CI': 'BOAC',
    'BANK OF AFRICA - BENIN': 'BOAB',
    'BANK OF AFRICA - BURKINA FASO': 'BOABF',
    'BANK OF AFRICA - MALI': 'BOAM',
    'BANK OF AFRICA - NIGER': 'BOAN',
    'BANK OF AFRICA - SENEGAL': 'BOAS',
    'BERNABE CI': 'BNBC',
    'CORIS BANK': 'CBIBF',
    'ECOBANK': 'ECOC',
    'ECOBANK COTE D\'IVOIRE': 'ECOC',
    'NSIA BANQUE': 'NSBC',
    'SGBCI': 'SGBC',
    'SIB CI': 'SIBC',
    'CFAO MOTORS CI': 'CFAC',
    'CIE': 'CIEC',
    'FILTISAC': 'FTSC',
    'NESTLE CI': 'NTLC',
    'PALMCI': 'PALC',
    'SAPH': 'SPHC',
    'SICABLE': 'SICC',
    'SICOR': 'SCRC',
    'SITAB': 'STBC',
    'SMB': 'SMBC',
    'SODECI': 'SDSC',
    'SOGB': 'SOGC',
    'SUCRIVOIRE': 'SIVC',
    'SOLIBRA': 'SLBC',
    'TOTALENERGIES MARKETING CI': 'TTLC',
    'TOTALENERGIES MARKETING SENEGAL': 'TTLS',
    'UNILEVER CI': 'UNLC',
    'UNIWAX': 'UNXC',
    'NEI-CEDA': 'NEIC',
    'ONATEL': 'ONTBF',
    'ORANGE CI': 'ORGT',
    'ORAGROUP': 'ORGT',
    'SONATEL': 'SNTS',
    'LOTERIE NATIONALE DU BENIN': 'LNBB',
}

def main():
    print("=" * 60)
    print("DEBUG: Checking which files will be imported")
    print("=" * 60)
    
    # Get company mapping
    res = supabase.table('companies').select('id, symbol').execute()
    company_map = {row['symbol']: row['id'] for row in res.data}
    print(f"Companies in DB: {len(company_map)}")
    
    # Get all Excel files
    files = [f for f in os.listdir(FOLDER) if f.endswith('.xlsx')]
    
    mapped_count = 0
    not_mapped = []
    not_in_db = []
    will_import = []
    
    for filename in sorted(files):
        if 'COMPOSITE INDEX' in filename:
            continue
            
        symbol = None
        for key, sym in FILENAME_TO_SYMBOL.items():
            if key in filename:
                symbol = sym
                break
        
        if not symbol:
            not_mapped.append(filename)
            continue
        
        if symbol not in company_map:
            not_in_db.append(f"{filename} -> {symbol}")
            continue
        
        will_import.append(f"{filename} -> {symbol}")
        mapped_count += 1
    
    print(f"\nFiles that WILL be imported: {len(will_import)}")
    for f in will_import[:10]:
        print(f"  {f}")
    if len(will_import) > 10:
        print(f"  ... and {len(will_import)-10} more")
    
    print(f"\nFiles with symbol not in database: {len(not_in_db)}")
    for f in not_in_db[:10]:
        print(f"  {f}")
    
    print(f"\nFiles with no mapping: {len(not_mapped)}")
    for f in not_mapped[:5]:
        print(f"  {f}")
    
    print("\n" + "=" * 60)
    print(f"Total files that should be imported: {mapped_count}")
    print("=" * 60)

if __name__ == "__main__":
    main()
