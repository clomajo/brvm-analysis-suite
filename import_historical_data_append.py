#!/usr/bin/env python3
"""
import_historical_data_append.py
Import 10 years of historical data - only appends new dates (older than existing data)
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

FILENAME_TO_SYMBOL = {
    'SGBCI': 'SGBC',
    'BICICI': 'BICC',
    'ECOBANK COTE D\'IVOIRE': 'ECOC',
    'ECOBANK': 'ECOC',
    'NSIA BANQUE': 'NSBC',
    'BANK OF AFRICA - CI': 'BOAC',
    'BANK OF AFRICA - BENIN': 'BOAB',
    'BANK OF AFRICA - BURKINA FASO': 'BOABF',
    'BANK OF AFRICA - MALI': 'BOAM',
    'BANK OF AFRICA - NIGER': 'BOAN',
    'BANK OF AFRICA - SENEGAL': 'BOAS',
    'ORANGE CI': 'ORGT',
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
    'CFAO MOTORS CI': 'CFAC',
    'BERNABE CI': 'BNBC',
    'FILTISAC': 'FTSC',
    'NEI-CEDA': 'NEIC',
    'ONATEL': 'ONTBF',
    'SIB CI': 'SIBC',
    'SMB': 'SMBC',
    'SOGB': 'SOGC',
    'UNILEVER CI': 'UNLC',
    'UNIWAX': 'UNXC',
    'NESTLE CI': 'NTLC',
    'ORAGROUP': 'ORGT',
    'SOLIBRA': 'SLBC',
    'SONATEL': 'SNTS',
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
        print(f"    Error getting existing dates: {e}")
        return set()

def find_symbol_from_filename(filename):
    for key, symbol in FILENAME_TO_SYMBOL.items():
        if key in filename:
            return symbol
    return None

def import_file(filepath, symbol, company_id):
    """Import only new dates (not already in database)"""
    print(f"  Importing {symbol}...")
    
    # Get existing dates to avoid duplicates
    existing_dates = get_existing_dates(company_id)
    print(f"    Found {len(existing_dates)} existing records")
    
    try:
        df = pd.read_excel(filepath)
        
        if df.empty:
            return 0
        
        # Filter out dates that already exist
        new_records = []
        skipped = 0
        
        for _, row in df.iterrows():
            if pd.notna(row['Date']):
                if isinstance(row['Date'], datetime):
                    date_str = row['Date'].strftime('%Y-%m-%d')
                else:
                    date_str = str(row['Date'])
                
                # Skip if date already exists
                if date_str in existing_dates:
                    skipped += 1
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
        
        print(f"    New records to insert: {len(new_records)} (skipped {skipped} existing)")
        
        if not new_records:
            print(f"  ✓ No new data for {symbol}")
            return 0
        
        # Insert in batches
        batch_size = 500
        total_inserted = 0
        
        for i in range(0, len(new_records), batch_size):
            batch = new_records[i:i+batch_size]
            try:
                supabase.table('historical_data').insert(batch).execute()
                total_inserted += len(batch)
                print(f"    Inserted {total_inserted}/{len(new_records)} rows")
            except Exception as e:
                print(f"    Error inserting batch: {e}")
        
        print(f"  ✓ Imported {total_inserted} new rows for {symbol}")
        return total_inserted
        
    except Exception as e:
        print(f"  ✗ Error importing {symbol}: {e}")
        return 0

def main():
    print("=" * 60)
    print("Importing 10 Years of Historical Data (Append Mode)")
    print("=" * 60)
    
    # Get company mapping
    res = supabase.table('companies').select('id, symbol').execute()
    company_map = {row['symbol']: row['id'] for row in res.data}
    print(f"Found {len(company_map)} companies in database")
    
    # Get all Excel files
    files = [f for f in os.listdir(FOLDER) if f.endswith('.xlsx')]
    print(f"Found {len(files)} Excel files")
    
    # Process each file
    total_rows = 0
    imported_count = 0
    
    for filename in sorted(files):
        symbol = find_symbol_from_filename(filename)
        
        if not symbol:
            continue
        
        if symbol not in company_map:
            print(f"Skipping {filename}: symbol '{symbol}' not in database")
            continue
        
        company_id = company_map[symbol]
        filepath = os.path.join(FOLDER, filename)
        rows = import_file(filepath, symbol, company_id)
        if rows > 0:
            total_rows += rows
            imported_count += 1
    
    print("\n" + "=" * 60)
    print(f"Import complete!")
    print(f"  Files with new data: {imported_count}")
    print(f"  Total new rows inserted: {total_rows}")
    print("=" * 60)

if __name__ == "__main__":
    main()
