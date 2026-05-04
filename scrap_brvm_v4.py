import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

base_url = "https://www.brvm.org/fr/marche/avis-et-publications/avis"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Les titres qu'on recherche
titres_recherches = [
    "BRVM : Nouvelle Composition de l'indice BRVM Prestige",
    "BRVM : Composition de l'indice BRVM Prestige",
    "BRVM : Nouvelle Composition de l'indice BRVM 30",
    "BRVM : Composition de l'indice BRVM 30"
]

print("🔍 Recherche des avis...")

response = requests.get(base_url, headers=headers)
soup = BeautifulSoup(response.content, 'html.parser')

# Dictionnaire pour stocker {titre: url}
docs_trouves = {}

# Parcourir toutes les lignes du tableau
for ligne in soup.find_all('tr'):
    texte_ligne = ligne.get_text()
    
    for titre in titres_recherches:
        if titre in texte_ligne:
            # Trouver le lien de téléchargement dans cette ligne
            lien = ligne.find('a', href=True)
            if lien and lien['href'].endswith('.pdf'):
                url_pdf = urljoin(base_url, lien['href'])
                docs_trouves[titre] = url_pdf
                print(f"📄 {titre} -> {url_pdf.split('/')[-1]}")
                break

if not docs_trouves:
    print("\n❌ Aucun avis trouvé.")
    print("   Affichage de tous les avis BRVM sur la page :")
    for ligne in soup.find_all('tr'):
        texte = ligne.get_text().strip()
        if 'BRVM' in texte and len(texte) < 200:
            print(f"   - {texte[:100]}")
else:
    print(f"\n📊 Total trouvé : {len(docs_trouves)} documents uniques")
    print("\n⬇️ Téléchargement...")
    
    for titre, url in docs_trouves.items():
        # Créer un nom de fichier propre
        nom_fichier = titre.replace(' ', '_').replace(':', '').replace('/', '_')
        nom_fichier = f"{nom_fichier}.pdf"
        
        print(f"  {nom_fichier[:60]}...")
        try:
            pdf_response = requests.get(url, headers=headers, timeout=30)
            if pdf_response.status_code == 200:
                with open(nom_fichier, 'wb') as f:
                    f.write(pdf_response.content)
                print(f"    ✅ Sauvegardé")
            else:
                print(f"    ❌ Échec (code {pdf_response.status_code})")
        except Exception as e:
            print(f"    ❌ Erreur : {e}")
