path = '/Users/kaylam/Desktop/brvm-analysis-suite/.github/workflows/brvm-analysis.yml'
with open(path, 'r') as f:
    content = f.read()

NEW_STEP = '''
      - name: 📈 ÉTAPE 0 - Update Index Values
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: |
          echo "🚀 Updating BRVMC and BRVM30 index values..."
          python update_index.py
          echo "✅ Index updated"

'''

OLD = '      - name: 📊 ÉTAPE 1 - Collecte Données (Supabase)'
NEW = NEW_STEP + OLD

if OLD in content:
    content = content.replace(OLD, NEW)
    print("✅ Added index update step")
else:
    print("❌ Could not find insertion point")
    import sys; sys.exit(1)

with open(path, 'w') as f:
    f.write(content)
print("✅ Done")
