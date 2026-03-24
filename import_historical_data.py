#!/usr/bin/env python3
"""
import_historical_data.py
Import 10 years of historical data from Excel files to Supabase
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

# Folder with Excel files
FOLDER = '/Users/kaylam/Downloads/Historical Data BRVM 10Y/'

# Map filenames to company symbols
# The mapping from filename to company symbol
def get_company_mapping():
    """Get mapping from company name to company_id"""
    res = supabase.table('companies').select('id, symbol').execute()
    return {row['symbol']: row['id'] for row in res.data}

def parse_filename_to_symbol(filename):
    """Extract company symbol from filename"""
    # Files are like: "32_market-data_SGBCI.xlsx"
    parts = filename.replace('.xlsx', '').split('_')
    if len(parts) >= 3:
        return parts[-1]  # Returns "SGBCI"
    return None

def import_file(filepath, symbol, company_id):
    """Import a single Excel file to Supabase"""
    print(f"  Importing {symbol}...")
    
    try:
        df = pd.read_excel(filepath)
        
        # Map columns to match your database schema
        df_import = pd.DataFrame()
        df_import['company_id'] = company_id
        df_import['trade_date'] = pd.to_datetime(df['Date']).dt.date
        df_import['open_price'] = df['Open']
        df_import['high_price'] = df['High']
        df_import['low_price'] = df['Low']
        df_import['price'] = df['Close']  # Close price
        df_import['volume'] = df['Volume']
        
        # Convert to records
        records = df_import.to_dict('records')
        
        # Insert in batches of 500 to avoid timeouts
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
                        print(f"      Failed to insert {record['trade_date']}: {e2}")
        
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
    for filename in sorted(files):
        symbol = parse_filename_to_symbol(filename)
        
        if not symbol:
            print(f"Skipping {filename}: could not parse symbol")
            continue
        
        if symbol not in company_map:
            print(f"Skipping {filename}: symbol {symbol} not found in companies table")
            continue
        
        company_id = company_map[symbol]
        filepath = os.path.join(FOLDER, filename)
        rows = import_file(filepath, symbol, company_id)
        total_rows += rows
    
    print("\n" + "=" * 60)
    print(f"Import complete! Total rows inserted: {total_rows}")
    print("=" * 60)

if __name__ == "__main__":
    main()
