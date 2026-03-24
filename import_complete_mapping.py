#!/usr/bin/env python3
"""
Complete import with accurate filename to database symbol mapping
"""

import os
import sys
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

FOLDER = '/Users/kaylam/Downloads/Historical Data BRVM 10Y/'

# Complete mapping based on actual files and database symbols
FILENAME_TO_SYMBOL = {
    # Banks (from your list)
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
    
    # Industry
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
    
    # Telecom & Others
    'NEI-CEDA': 'NEIC',
    'ONATEL': 'ONTBF',
    'ORANGE CI': 'ORGT',
    'ORAGROUP': 'ORGT',  # Might map to ORGT
    'SONATEL': 'SNTS',
    'LOTERIE NATIONALE DU BENIN': 'LNBB',
    
    # These may not be in your DB - will be skipped
    # 'CROWN SIEM': 'CRSI',  # Not in DB
    # 'ERIUM CI': 'ERIU',    # Not in DB
    # 'MOVIS CI': 'MOVI',    # Not in DB
    # 'SERVAIR ABIDJAN': 'SERC',  # Not in DB
    # 'SETAO': 'SETA',       # Not in DB
    # 'VIVO ENERGY CI': 'VIVO',  # Not in DB
    # 'ALIOS FINANCE CI - SAFCA': 'ALIO',  # Not in DB
    # 'AFRICA GLOBAL LOGISTICS': 'AGL',  # Not in DB
}

def get_existing_dates(company_id):
    """Get all existing trade dates for a company"""
    try:
        res = supabase.table('historical_data') \
            .select('trade_date') \
            .eq('company_id', company_id) \
            .execute()
        return {row['trade_date'] for row in res.data}
    except Exception as e:
        return set()

def import_file(filepath, symbol, company_id):
    """Import data for a company"""
    print(f"\n  Importing {symbol}...")
    
    existing_dates = get_existing_dates(company_id)
    print(f"    Existing records: {len(existing_dates)}")
    
    try:
        df = pd.read_excel(filepath)
        if df.empty:
            return 0
        
        # Filter new records
        new_records = []
        for _, row in df.iterrows():
            if pd.notna(row['Date']):
                if isinstance(row['Date'], datetime):
                    date_str = row['Date'].strftime('%Y-%m-%d')
                else:
                    date_str = str(row['Date'])
                
                if date_str in existing_dates:
                    continue
                
                record = {
                    'company_id': company_id,
                    'trade_date': date_str,
                    'open_price': float(row['Open']) if pd.notna(row['Open']) else None,
                    'high_price': float(row['High']) if pd.notna(row['High']) else None,
                    'low_price': float(row['Low']) if pd.notna(row['Low']) else None,
                    'price': float(row['Close']) if pd.notna(row['Close']) else None,
                    'volume': int(row['Volume']) if pd.notna(row['Volume']) else None
                }
                new_records.append(record)
        
        print(f"    New records to insert: {len(new_records)}")
        
        if not new_records:
            return 0
        
        # Insert in batches
        batch_size = 500
        inserted = 0
        for i in range(0, len(new_records), batch_size):
            batch = new_records[i:i+batch_size]
            try:
                supabase.table('historical_data').insert(batch).execute()
                inserted += len(batch)
                print(f"    Inserted {inserted}/{len(new_records)} rows")
            except Exception as e:
                print(f"    Error in batch: {e}")
                # Try one by one for errors
                for record in batch:
                    try:
                        supabase.table('historical_data').insert(record).execute()
                        inserted += 1
                    except Exception as e2:
                        print(f"      Failed: {record['trade_date']}")
        
        return inserted
        
    except Exception as e:
        print(f"    Error: {e}")
        return 0

def main():
    print("=" * 60)
    print("Importing ALL Historical Data with Complete Mapping")
    print("=" * 60)
    
    # Get company mapping
    res = supabase.table('companies').select('id, symbol').execute()
    company_map = {row['symbol']: row['id'] for row in res.data}
    print(f"Found {len(company_map)} companies in database")
    
    # Get all Excel files
    files = [f for f in os.listdir(FOLDER) if f.endswith('.xlsx')]
    print(f"Found {len(files)} Excel files\n")
    
    total_rows = 0
    imported_count = 0
    skipped_count = 0
    
    for filename in sorted(files):
        # Skip index file
        if 'COMPOSITE INDEX' in filename:
            print(f"Skipping {filename}: index file")
            skipped_count += 1
            continue
        
        # Try to find symbol
        symbol = None
        for key, sym in FILENAME_TO_SYMBOL.items():
            if key in filename:
                symbol = sym
                break
        
        if not symbol:
            print(f"Skipping {filename}: no mapping found")
            skipped_count += 1
            continue
        
        if symbol not in company_map:
            print(f"Skipping {filename}: symbol '{symbol}' not in database")
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
    print(f"  Total new rows: {total_rows}")
    print("=" * 60)

if __name__ == "__main__":
    main()
