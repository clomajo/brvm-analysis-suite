import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

base_url = "https://www.brvm.org/fr/marche/avis-et-publications/avis"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Mots-clés à rechercher
mots_cles = [
    "BRVM 30",
    "BRVM Prestige",
    "BRVM 10"
]

# Ensemble pour stocker les URLs uniques
urls_a_telecharger = set()

page = 1
max_pages = 60  # Au cas où

print("🔍 Recherche des avis sur toutes les pages...")

while page <= max_pages:
    url_page = f"{base_url}?page={page}" if page > 1 else base_url
    print(f"📄 Page {page}...")
    
    try:
        response = requests.get(url_page, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"  ⚠️ Fin atteinte (code {response.status_code})")
            break
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Vérifier si la page contient des avis
        if "Aucun résultat" in soup.get_text() or len(soup.find_all('a', href=True)) < 5:
            print("  📭 Plus d'avis trouvés.")
            break
        
        # Chercher dans tous les liens
        trouves_sur_page = 0
        for lien in soup.find_all('a', href=True):
            texte = lien.get_text().strip()
            href = lien['href']
            
            # Si c'est un PDF et que le texte contient un mot-clé
            if href.endswith('.pdf') and any(mot in texte for mot in mots_cles):
                url_complet = urljoin(base_url, href)
                if url_complet not in urls_a_telecharger:
                    urls_a_telecharger.add(url_complet)
                    trouves_sur_page += 1
                    print(f"  📄 {texte[:80]}...")
        
        if trouves_sur_page == 0:
            print("  (rien trouvé sur cette page)")
            
        page += 1
        time.sleep(0.5)  # Politesse
        
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        break

print(f"\n📊 Total trouvé : {len(urls_a_telecharger)} documents")

if urls_a_telecharger:
    print("\n⬇️ Téléchargement...")
    for url in urls_a_telecharger:
        try:
            # Extraire un nom de fichier propre
            nom_fichier = url.split('/')[-1]
            if not nom_fichier.endswith('.pdf'):
                nom_fichier = f"avis_{int(time.time())}.pdf"
            
            print(f"  Téléchargement : {nom_fichier[:60]}...")
            pdf_response = requests.get(url, headers=headers, timeout=30)
            
            if pdf_response.status_code == 200:
                with open(nom_fichier, 'wb') as f:
                    f.write(pdf_response.content)
                print(f"    ✅ Sauvegardé")
            else:
                print(f"    ❌ Échec")
        except Exception as e:
            print(f"    ❌ Erreur: {e}")
else:
    print("\n💡 Aucun document trouvé automatiquement.")
    print("   Peut-être que la structure du site a changé.")
    print("   Télécharge les PDFs manuellement depuis :")
    print("   https://www.brvm.org/fr/marche/avis-et-publications/avis")
