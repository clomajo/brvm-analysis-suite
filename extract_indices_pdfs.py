import os
import re
import pandas as pd
from PyPDF2 import PdfReader

# Dossier contenant les PDF (à modifier selon ton chemin)
dossier_pdfs = "/Users/kaylam/Downloads/Historique_Indices_BRVM"

# Vérifier que le dossier existe
if not os.path.exists(dossier_pdfs):
    print(f"❌ Le dossier n'existe pas : {dossier_pdfs}")
    print("   Vérifie le chemin et réessaie.")
    exit(1)

# Dictionnaire pour stocker les résultats
resultats = []

# Parcourir tous les fichiers PDF dans le dossier
fichiers = sorted([f for f in os.listdir(dossier_pdfs) if f.endswith('.pdf')])

print(f"📁 Dossier : {dossier_pdfs}")
print(f"📄 {len(fichiers)} fichiers PDF trouvés.\n")

for fichier in fichiers:
    print(f"Traitement : {fichier}")
    
    try:
        chemin_complet = os.path.join(dossier_pdfs, fichier)
        reader = PdfReader(chemin_complet)
        texte_complet = ""
        
        # Extraire le texte de toutes les pages
        for page in reader.pages:
            texte_complet += page.extract_text()
        
        # Extraire la date à partir du nom de fichier
        date_match = re.search(r'(\d{4})', fichier)
        annee = date_match.group(1) if date_match else "inconnue"
        
        # Déterminer le type d'indice
        if 'Prestige' in fichier:
            type_indice = 'prestige'
        elif 'BRVM_10' in fichier:
            type_indice = 'brvm10'
        elif 'BRVM_30' in fichier:
            type_indice = 'brvm30'
        else:
            type_indice = 'autre'
        
        # Extraire les tickers (codes à 3-5 lettres majuscules)
        # Cherche les lignes qui ressemblent à des listes de sociétés
        tickers_trouves = re.findall(r'\b([A-Z]{3,5})\b', texte_complet)
        
        # Filtrer les faux positifs
        mots_exclus = {
            'BRVM', 'AVIS', 'TOTAL', 'SOCIETE', 'BANQUE', 'CI', 'BF', 'SN', 'TG', 
            'ML', 'BN', 'NG', 'BENIN', 'TOGO', 'MALI', 'NIGER', 'SENEGAL', 'COTE', 
            'IVOIRE', 'COMPOSITION', 'NOUVELLE', 'INDICE', 'PRESTIGE', 'ANNEXE',
            'DIRECTEUR', 'GENERAL', 'FINANCES', 'ADMINISTRATION', 'RESSOURCES', 
            'HUMAINES', 'MAXIME', 'DESSOU', 'PAGE', 'SA', 'DG', 'SUR', 'LES',
            'QUI', 'SONT', 'ET', 'DES', 'POUR', 'UNE', 'DANS', 'PAR', 'AVEC'
        }
        
        # Garder les tickers potentiels (minimum 3 lettres, pas dans exclus)
        tickers_filtres = [t for t in tickers_trouves if t not in mots_exclus and len(t) >= 3]
        
        # Supprimer les doublons tout en gardant l'ordre
        tickers_uniques = []
        for t in tickers_filtres:
            if t not in tickers_uniques:
                tickers_uniques.append(t)
        
        # Pour BRVM 10, on s'attend à environ 10 tickers
        # Pour BRVM 30, environ 30
        # Pour Prestige, environ 12
        if type_indice == 'brvm10' and len(tickers_uniques) != 10:
            print(f"   ⚠️ Attention : {len(tickers_uniques)} tickers trouvés (attendu : 10)")
        elif type_indice == 'brvm30' and len(tickers_uniques) != 30:
            print(f"   ⚠️ Attention : {len(tickers_uniques)} tickers trouvés (attendu : 30)")
        elif type_indice == 'prestige' and len(tickers_uniques) != 12:
            print(f"   ⚠️ Attention : {len(tickers_uniques)} tickers trouvés (attendu : 12)")
        
        print(f"   → {len(tickers_uniques)} tickers extraits : {', '.join(tickers_uniques[:8])}{'...' if len(tickers_uniques) > 8 else ''}")
        
        # Stocker les résultats
        resultats.append({
            'fichier': fichier,
            'annee': annee,
            'type_indice': type_indice,
            'tickers': ', '.join(tickers_uniques),
            'nombre_tickers': len(tickers_uniques)
        })
        
    except Exception as e:
        print(f"   ❌ Erreur : {e}")
        resultats.append({
            'fichier': fichier,
            'annee': annee if 'annee' in locals() else 'inconnue',
            'type_indice': type_indice if 'type_indice' in locals() else 'inconnu',
            'tickers': f"ERREUR: {e}",
            'nombre_tickers': 0
        })

# Créer un DataFrame et sauvegarder en CSV
df = pd.DataFrame(resultats)
csv_path = os.path.join(dossier_pdfs, 'indices_brvm_compositions.csv')
df.to_csv(csv_path, index=False, encoding='utf-8')

print(f"\n✅ Extraction terminée !")
print(f"📊 {len(resultats)} fichiers traités")
print(f"💾 Résultats sauvegardés dans : {csv_path}")

# Afficher un résumé
print("\n📋 Résumé par type d'indice :")
resume = df[df['type_indice'] != 'inconnu'].groupby('type_indice').agg({
    'fichier': 'count',
    'nombre_tickers': 'mean'
}).round(1)
print(resume)

# Afficher les fichiers qui ont des nombres anormaux
print("\n⚠️ Fichiers avec nombre de tickers anormal :")
anormaux = df[(df['type_indice'] == 'brvm10') & (df['nombre_tickers'] != 10)]
anormaux = pd.concat([anormaux, df[(df['type_indice'] == 'brvm30') & (df['nombre_tickers'] != 30)]])
anormaux = pd.concat([anormaux, df[(df['type_indice'] == 'prestige') & (df['nombre_tickers'] != 12)]])
if len(anormaux) > 0:
    print(anormaux[['fichier', 'nombre_tickers']].to_string(index=False))
else:
    print("   Aucun !")
