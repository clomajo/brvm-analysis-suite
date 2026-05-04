import re

path = "/Users/kaylam/Desktop/brvm-analytics/src/App.jsx"
with open(path, "r") as f:
    content = f.read()

old = '              <span style={badgeStyle(d.signal)}>{sigLabel[d.signal]}</span>'

new = '''              <div style={{ display:"flex", flexDirection:"column", alignItems:"flex-end", gap:4 }}>
                <span style={badgeStyle(d.signal)}>{sigLabel[d.signal]}</span>
                {d.signal_combine && d.signal_combine !== d.signal && (
                  <span style={{ fontSize:10, fontWeight:700, color:"#2B6CB0", background:"#2B6CB011", borderRadius:8, padding:"2px 8px" }}>
                    {d.signal_combine}
                  </span>
                )}
                {d.data_completeness && d.data_completeness !== "High" && (
                  <span style={{ fontSize:9, fontWeight:600, color: d.data_completeness === "Medium" ? "#f59e0b" : "#6b7280", background: d.data_completeness === "Medium" ? "#f59e0b11" : "#6b728011", borderRadius:8, padding:"2px 8px" }}>
                    {d.data_completeness === "Medium" ? "📊 Données partielles" : "📊 Données limitées"}
                  </span>
                )}
              </div>'''

if old in content:
    content = content.replace(old, new)
    with open(path, "w") as f:
        f.write(content)
    print("✅ Badge data_completeness + signal_combine ajoutés")
else:
    print("❌ Cible non trouvée")
