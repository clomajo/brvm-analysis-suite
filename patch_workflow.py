path = '/Users/kaylam/Desktop/brvm-analysis-suite/.github/workflows/brvm-analysis.yml'
with open(path, 'r') as f:
    content = f.read()

NEW_STEPS = '''
      - name: 🎯 ÉTAPE 3b - Generate Decisions
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: |
          echo "🚀 Generating daily decisions..."
          python generate_decisions.py
          echo "✅ Decisions generated"

      - name: ✅ ÉTAPE 3c - Verify Decisions (90-day lookback)
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          MISTRAL_API_KEY: ${{ secrets.MISTRAL_API_KEY }}
        run: |
          echo "🚀 Verifying signals from 90 days ago..."
          python verify_decisions.py
          echo "✅ Verification complete"

'''

OLD = '''      - name: 🔮 ÉTAPE 4 - Prédictions'''
NEW = NEW_STEPS + '''      - name: 🔮 ÉTAPE 4 - Prédictions'''

if OLD in content:
    content = content.replace(OLD, NEW)
    print("✅ Added generate_decisions and verify_decisions steps")
else:
    print("❌ Could not find insertion point")
    import sys; sys.exit(1)

with open(path, 'w') as f:
    f.write(content)
print("✅ Workflow updated")
