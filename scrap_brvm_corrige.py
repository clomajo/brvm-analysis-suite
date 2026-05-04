import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

base_url = "https://www.brvm.org/fr/marche/avis-et-publications/avis"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Les titres exacts qu'on recherche (d'après ta capture)
titres_recherches = [
    "BRVM : Nouvelle Composition de l'indice BRVM Prestige",
    "BRVM : Nouvelle Composition de l'indice BRVM 30",
    "BRVM : Composition de l'indice BRVM 30",  # variante
    "BRVM : Composition de l'indice BRVM Prestige"  # variante
]

print("🔍 Recherche des avis sur la première page...")

response = requests.get(base_url, headers=headers)
soup = BeautifulSoup(response.content, 'html.parser')

# On cherche dans toutes les lignes du tableau (tr) ou les divs
trouves = []
for ligne in soup.find_all(['tr', 'div', 'li']):
    texte_ligne = ligne.get_text()
    for titre in titres_recherches:
        if titre in texte_ligne:
            # On trouve le lien de téléchargement dans cette ligne
            lien = ligne.find('a', href=True)
            if lien and lien['href'].endswith('.pdf'):
                url_pdf = urljoin(base_url, lien['href'])
                trouves.append((titre, url_pdf))
                print(f"📄 Trouvé : {titre}")
                break

if not trouves:
    print("\n❌ Aucun avis trouvé sur la première page.")
    print("   Voici les titres disponibles sur la page :")
    # Afficher tous les titres pour aider à diagnostiquer
    for ligne in soup.find_all(['tr', 'div', 'li']):
        texte = ligne.get_text().strip()
        if 'BRVM' in texte and len(texte) > 10 and len(texte) < 200:
            print(f"   - {texte[:100]}")
else:
    print(f"\n📊 Total trouvé : {len(trouves)} documents")
    print("\n⬇️ Téléchargement...")
    
    for titre, url in trouves:
        try:
            # Créer un nom de fichier propre
            nom_fichier = titre.replace(' ', '_').replace(':', '').replace('BRVM', '').strip()
            nom_fichier = f"BRVM_{nom_fichier}.pdf"
            nom_fichier = nom_fichier.replace('/', '_')
            
            print(f"  Téléchargement : {nom_fichier}")
            pdf_response = requests.get(url, headers=headers)
            
            if pdf_response.status_code == 200:
                with open(nom_fichier, 'wb') as f:
                    f.write(pdf_response.content)
                print(f"    ✅ Sauvegardé")
            else:
                print(f"    ❌ Échec (code {pdf_response.status_code})")
        except Exception as e:
            print(f"    ❌ Erreur : {e}")
