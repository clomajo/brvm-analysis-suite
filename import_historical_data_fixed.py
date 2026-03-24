#!/usr/bin/env python3
"""
import_historical_data_fixed.py
Import 10 years of historical data from Excel files to Supabase
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

# Mapping from filename to company symbol in database
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

def find_symbol_from_filename(filename):
    """Extract and map filename to database symbol"""
    for key, symbol in FILENAME_TO_SYMBOL.items():
        if key in filename:
            return symbol
    return None

def import_file(filepath, symbol, company_id):
    """Import a single Excel file to Supabase"""
    print(f"  Importing {symbol}...")
    
    try:
        df = pd.read_excel(filepath)
        
        if df.empty:
            print(f"    No data in file")
            return 0
        
        # Prepare data - convert dates to string format that Supabase accepts
        records = []
        for _, row in df.iterrows():
            # Convert date to ISO format string
            if pd.notna(row['Date']):
                if isinstance(row['Date'], datetime):
                    date_str = row['Date'].strftime('%Y-%m-%d')
                else:
                    date_str = str(row['Date'])
                
                record = {
                    'company_id': company_id,
                    'trade_date': date_str,
                    'open_price': float(row['Open']) if pd.notna(row['Open']) else None,
                    'high_price': float(row['High']) if pd.notna(row['High']) else None,
                    'low_price': float(row['Low']) if pd.notna(row['Low']) else None,
                    'price': float(row['Close']) if pd.notna(row['Close']) else None,
                    'volume': int(row['Volume']) if pd.notna(row['Volume']) else None
                }
                records.append(record)
        
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
                # Try one by one for problematic rows
                for record in batch:
                    try:
                        supabase.table('historical_data').insert(record).execute()
                        total_inserted += 1
                    except Exception as e2:
                        print(f"      Failed: {record['trade_date']} - {e2}")
        
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
            print(f"Skipping {filename}: no mapping found")
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
    print(f"  Files imported: {imported_count}")
    print(f"  Total rows inserted: {total_rows}")
    print("=" * 60)

if __name__ == "__main__":
    main()
