#!/usr/bin/env python3
"""
Import all 38 companies that have matching symbols
Force import all data (overwrite or skip duplicates)
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

def import_file(filepath, symbol, company_id):
    """Import all data for a company"""
    print(f"\n  📥 Importing {symbol}...")
    
    try:
        df = pd.read_excel(filepath)
        if df.empty:
            print(f"    ⚠️  File empty")
            return 0
        
        print(f"    📊 File has {len(df)} rows")
        
        # Prepare all records
        records = []
        for _, row in df.iterrows():
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
        
        print(f"    📝 Prepared {len(records)} records")
        
        # Delete existing data for this company first (to avoid duplicates)
        print(f"    🗑️  Removing existing data for {symbol}...")
        supabase.table('historical_data').delete().eq('company_id', company_id).execute()
        
        # Insert in batches
        batch_size = 500
        inserted = 0
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            try:
                supabase.table('historical_data').insert(batch).execute()
                inserted += len(batch)
                print(f"    ✅ Inserted {inserted}/{len(records)} rows")
            except Exception as e:
                print(f"    ❌ Error in batch: {e}")
                # Try one by one
                for record in batch:
                    try:
                        supabase.table('historical_data').insert(record).execute()
                        inserted += 1
                    except Exception as e2:
                        print(f"      Failed: {record['trade_date']}")
        
        print(f"  ✅ {symbol} complete: {inserted} rows inserted")
        return inserted
        
    except Exception as e:
        print(f"  ❌ Error importing {symbol}: {e}")
        return 0

def main():
    print("=" * 60)
    print("Importing ALL 38 Companies")
    print("⚠️  This will REPLACE existing data for these companies")
    print("=" * 60)
    
    # Get company mapping
    res = supabase.table('companies').select('id, symbol').execute()
    company_map = {row['symbol']: row['id'] for row in res.data}
    print(f"Found {len(company_map)} companies in database")
    
    # Get files to import
    files = [f for f in os.listdir(FOLDER) if f.endswith('.xlsx')]
    
    total_rows = 0
    imported_count = 0
    
    for filename in sorted(files):
        if 'COMPOSITE INDEX' in filename:
            continue
        
        symbol = None
        for key, sym in FILENAME_TO_SYMBOL.items():
            if key in filename:
                symbol = sym
                break
        
        if not symbol:
            continue
        
        if symbol not in company_map:
            continue
        
        company_id = company_map[symbol]
        filepath = os.path.join(FOLDER, filename)
        rows = import_file(filepath, symbol, company_id)
        if rows > 0:
            total_rows += rows
            imported_count += 1
    
    print("\n" + "=" * 60)
    print(f"✅ Import complete!")
    print(f"  Companies imported: {imported_count}")
    print(f"  Total rows inserted: {total_rows}")
    print("=" * 60)

if __name__ == "__main__":
    # Confirm before proceeding
    response = input("This will REPLACE existing data for 38 companies. Continue? (y/n): ")
    if response.lower() == 'y':
        main()
    else:
        print("Cancelled.")
