#!/usr/bin/env python3
"""
import_historical_data_mapped.py
Import 10 years of historical data from Excel files to Supabase with filename mapping
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

# Manual mapping from filename pattern to company symbol in database
# Format: 'filename_keyword': 'DB_SYMBOL'
FILENAME_TO_SYMBOL = {
    'SGBCI': 'SGBC',           # Société Générale
    'BICICI': 'BICC',          # BICI CI
    'ECOBANK COTE D\'IVOIRE': 'ECOC',
    'ECOBANK': 'ECOC',         # Some files just say ECOBANK
    'NSIA BANQUE': 'NSBC',
    'BANK OF AFRICA - CI': 'BOAC',
    'BANK OF AFRICA - BENIN': 'BOAB',
    'BANK OF AFRICA - BURKINA FASO': 'BOABF',
    'BANK OF AFRICA - MALI': 'BOAM',
    'BANK OF AFRICA - NIGER': 'BOAN',
    'BANK OF AFRICA - SENEGAL': 'BOAS',
    'ORANGE CI': 'ORGT',
    'ORAGROUP': 'ORGT',        # Might be the same
    'SONATEL': 'SNTS',
    'SOLIBRA': 'SLBC',
    'UNILEVER CI': 'UNLC',
    'NESTLE CI': 'NTLC',
    'PALMCI': 'PALC',
    'SAPH': 'SPHC',
    'SITAB': 'STBC',
    'SICABLE': 'SICC',
    'SICOR': 'SCRC',
    'SODECI': 'SDSC',
    'CIE': 'CIEC',
    'SUCRIVOIRE': 'SIVC',
    'TOTALENERGIES MARKETING CI': 'TTLC',
    'TOTALENERGIES MARKETING SENEGAL': 'TTLS',
    'TRACTAFRIC MOTORS CI': 'TTLC',  # Might be same as Total?
    'CFAO MOTORS CI': 'CFAC',
    'BERNABE CI': 'BNBC',
    'CROWN SIEM': 'CRSI',
    'ERIUM CI': 'ERIU',
    'FILTISAC': 'FTSC',
    'MOVIS CI': 'MOVI',
    'NEI-CEDA': 'NEIC',
    'ONATEL': 'ONTBF',
    'SERVAIR ABIDJAN': 'SERC',
    'SETAO': 'SETA',
    'SIB CI': 'SIBC',
    'SMB': 'SMBC',
    'SOGB': 'SOGC',
    'UNIWAX': 'UNXC',
    'VIVO ENERGY CI': 'VIVO',
    'ALIOS FINANCE CI - SAFCA': 'ALIO',
    'AFRICA GLOBAL LOGISTICS': 'AGL',
    'LOTERIE NATIONALE DU BENIN': 'LNB',
    'CORIS BANK': 'CORIS',
    'BRVM-COMPOSITE INDEX': None,  # Skip index file
}

def get_company_mapping():
    """Get mapping from symbol to company_id"""
    res = supabase.table('companies').select('id, symbol').execute()
    return {row['symbol']: row['id'] for row in res.data}

def find_symbol_from_filename(filename):
    """Extract and map filename to database symbol"""
    # Remove .xlsx and split
    name = filename.replace('.xlsx', '')
    
    # Try to find a match in the mapping
    for key, symbol in FILENAME_TO_SYMBOL.items():
        if key in name:
            return symbol
    
    # If no match, try to extract the last part after last underscore
    parts = name.split('_')
    if len(parts) >= 3:
        potential = parts[-1]
        # Check if this potential symbol exists in mapping values
        if potential in FILENAME_TO_SYMBOL.values():
            return potential
    
    return None

def import_file(filepath, symbol, company_id):
    """Import a single Excel file to Supabase"""
    print(f"  Importing {symbol}...")
    
    try:
        df = pd.read_excel(filepath)
        
        # Check if data exists
        if df.empty:
            print(f"    No data in file")
            return 0
        
        # Map columns
        df_import = pd.DataFrame()
        df_import['company_id'] = company_id
        df_import['trade_date'] = pd.to_datetime(df['Date']).dt.date
        df_import['open_price'] = df['Open']
        df_import['high_price'] = df['High']
        df_import['low_price'] = df['Low']
        df_import['price'] = df['Close']
        df_import['volume'] = df['Volume']
        
        # Remove any rows with null dates or prices
        df_import = df_import.dropna(subset=['trade_date', 'price'])
        
        records = df_import.to_dict('records')
        
        # Insert in batches
        batch_size = 500
        total_inserted = 0
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            try:
                supabase.table('historical_data').insert(batch).execute()
                total_inserted += len(batch)
                print(f"    Inserted {total_inserted}/{len(records)} rows")
            except Exception as e:
                print(f"    Error inserting batch: {e}")
        
        print(f"  ✓ Imported {total_inserted} rows for {symbol}")
        return total_inserted
        
    except Exception as e:
        print(f"  ✗ Error importing {symbol}: {e}")
        return 0

def main():
    print("=" * 60)
    print("Importing 10 Years of Historical Data to Supabase")
    print("=" * 60)
    
    # Get company mapping
    company_map = get_company_mapping()
    print(f"Found {len(company_map)} companies in database")
    
    # Get all Excel files
    files = [f for f in os.listdir(FOLDER) if f.endswith('.xlsx')]
    print(f"Found {len(files)} Excel files to import")
    
    # Process each file
    total_rows = 0
    imported_count = 0
    skipped_count = 0
    
    for filename in sorted(files):
        symbol = find_symbol_from_filename(filename)
        
        if not symbol:
            print(f"Skipping {filename}: could not map to database symbol")
            skipped_count += 1
            continue
        
        if symbol not in company_map:
            print(f"Skipping {filename}: symbol {symbol} not found in companies table")
            skipped_count += 1
            continue
        
        company_id = company_map[symbol]
        filepath = os.path.join(FOLDER, filename)
        rows = import_file(filepath, symbol, company_id)
        if rows > 0:
            total_rows += rows
            imported_count += 1
    
    print("\n" + "=" * 60)
    print(f"Import complete!")
    print(f"  Files imported: {imported_count}")
    print(f"  Files skipped: {skipped_count}")
    print(f"  Total rows inserted: {total_rows}")
    print("=" * 60)

if __name__ == "__main__":
    main()
