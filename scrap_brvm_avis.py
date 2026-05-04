import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import time

# Configuration
url_avis = "https://www.brvm.org/fr/marche/avis-et-publications/avis"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def telecharger_pdf(url, nom_fichier):
    """Télécharge un PDF à partir de son URL."""
    try:
        response = requests.get(url, headers=headers, stream=True)
        if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
            with open(nom_fichier, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"  -> Téléchargé : {nom_fichier}")
            return True
        else:
            print(f"  -> Échec du téléchargement : {url} (Code: {response.status_code})")
            return False
    except Exception as e:
        print(f"  -> Erreur lors du téléchargement : {e}")
        return False

print(f"Analyse de la page : {url_avis}")
try:
    reponse_page = requests.get(url_avis, headers=headers)
    reponse_page.raise_for_status()
    soup = BeautifulSoup(reponse_page.content, 'html.parser')

    # On cherche tous les liens qui pointent vers des fichiers PDF
    tous_liens = soup.find_all('a', href=True)
    liens_pdf = [lien for lien in tous_liens if lien['href'].endswith('.pdf')]

    print(f"Nombre total de PDFs trouvés sur la page : {len(liens_pdf)}")

    # On filtre pour ne garder que ceux qui parlent d'indices (BRVM 30, Prestige, etc.)
    pattern_indices = re.compile(r"(BRVM 30|BRVM Prestige|indice)", re.IGNORECASE)
    
    for lien in liens_pdf:
        texte_lien = lien.get_text().strip()
        if pattern_indices.search(texte_lien):
            url_pdf_complet = urljoin(url_avis, lien['href'])
            # Créer un nom de fichier propre à partir du texte du lien
            nom_fichier = re.sub(r'[\\/*?:"<>|]', "", texte_lien).replace(' ', '_') + ".pdf"
            print(f"\nDocument trouvé : {texte_lien}")
            telecharger_pdf(url_pdf_complet, nom_fichier)
            # On attend un peu pour ne pas surcharger le serveur
            time.sleep(1)

except requests.exceptions.RequestException as e:
    print(f"Erreur lors de l'accès à la page : {e}")
