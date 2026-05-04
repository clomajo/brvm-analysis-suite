import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

url = "https://www.brvm.org/fr/marche/avis-et-publications/avis"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

print("Connexion à la page des avis...")
response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.content, 'html.parser')

print("Recherche de l'avis 'BRVM : Composition de l'indice BRVM 30'...")

# On cherche tous les blocs qui contiennent "BRVM 30"
trouve = False
for bloc in soup.find_all(['div', 'tr', 'li', 'td']):
    texte_bloc = bloc.get_text()
    if 'BRVM 30' in texte_bloc and 'Composition' in texte_bloc:
        # On trouve le lien de téléchargement dans ce bloc
        lien = bloc.find('a', href=True)
        if lien and lien['href'].endswith('.pdf'):
            url_pdf = urljoin(url, lien['href'])
            print(f"PDF trouvé : {url_pdf}")
            
            print("Téléchargement en cours...")
            pdf_response = requests.get(url_pdf, headers=headers)
            
            nom_fichier = 'BRVM_30_composition_avril2026.pdf'
            with open(nom_fichier, 'wb') as f:
                f.write(pdf_response.content)
            
            print(f"Fichier sauvegardé : {nom_fichier}")
            trouve = True
            break

if not trouve:
    print("Avis non trouvé. Vérifie que la page contient bien 'BRVM : Composition de l'indice BRVM 30'")
