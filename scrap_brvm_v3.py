import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

url = "https://www.brvm.org/fr/marche/avis-et-publications/avis"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.content, 'html.parser')

# On cherche dans les lignes du tableau (tr) ou les divs
for ligne in soup.find_all(['tr', 'div', 'li']):
    texte = ligne.get_text()
    # On cherche la ligne qui contient exactement "BRVM : Composition de l'indice BRVM 30"
    if 'BRVM : Composition de l'indice BRVM 30' in texte:
        lien = ligne.find('a', href=True)
        if lien and lien['href'].endswith('.pdf'):
            url_pdf = urljoin(url, lien['href'])
            print(f"PDF trouvé : {url_pdf}")
            pdf_response = requests.get(url_pdf, headers=headers)
            with open('BRVM_30_composition_avril2026.pdf', 'wb') as f:
                f.write(pdf_response.content)
            print("Fichier sauvegardé : BRVM_30_composition_avril2026.pdf")
            break
else:
    print("Avis non trouvé. Télécharge manuellement depuis la page.")
