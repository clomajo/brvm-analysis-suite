import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

base_url = "https://www.brvm.org/fr/marche/avis-et-publications/avis"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

titres_recherches = [
    "BRVM Prestige",
    "BRVM 30",
    "BRVM 10"
]

docs_trouves = {}
page = 1
max_pages = 20

print("🔍 Parcours de toutes les pages...")

while page <= max_pages:
    url_page = f"{base_url}?page={page}" if page > 1 else base_url
    print(f"\n📄 Page {page}...")
    
    try:
        response = requests.get(url_page, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"  ⚠️ Fin atteinte (code {response.status_code})")
            break
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Vérifier si la page contient des avis
        if "Aucun résultat" in soup.get_text():
            print("  📭 Plus d'avis trouvés.")
            break
        
        trouves_page = 0
        for ligne in soup.find_all('tr'):
            texte_ligne = ligne.get_text()
            
            for titre in titres_recherches:
                if titre in texte_ligne and ('Composition' in texte_ligne or 'Nouvelle' in texte_ligne):
                    lien = ligne.find('a', href=True)
                    if lien and lien['href'].endswith('.pdf'):
                        url_pdf = urljoin(base_url, lien['href'])
                        # Nettoyer le titre pour l'utiliser comme clé
                        titre_propre = texte_ligne.strip()[:80]
                        if url_pdf not in docs_trouves.values():
                            docs_trouves[titre_propre] = url_pdf
                            trouves_page += 1
                            print(f"  📄 {titre_propre[:60]}...")
                    break
        
        if trouves_page == 0:
            print("  (rien trouvé)")
            
        page += 1
        time.sleep(0.5)
        
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        break

print(f"\n📊 Total trouvé : {len(docs_trouves)} documents uniques")

if docs_trouves:
    print("\n⬇️ Téléchargement...")
    for titre, url in docs_trouves.items():
        nom_fichier = titre.replace(' ', '_').replace(':', '').replace('/', '_')[:50] + ".pdf"
        print(f"  {nom_fichier}...")
        try:
            pdf_response = requests.get(url, headers=headers, timeout=30)
            if pdf_response.status_code == 200:
                with open(nom_fichier, 'wb') as f:
                    f.write(pdf_response.content)
                print(f"    ✅ Sauvegardé")
            else:
                print(f"    ❌ Échec")
        except Exception as e:
            print(f"    ❌ Erreur")
