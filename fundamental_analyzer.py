# ==============================================================================
# MODULE: FUNDAMENTAL ANALYZER V29.0 - MULTI-AI (DeepSeek + Gemini + Mistral)
# CORRECTION: URLs individuelles par société (rapports-societe-cotes)
# ==============================================================================

import requests
from bs4 import BeautifulSoup
import time
import re
import os
from datetime import datetime
import logging
import unicodedata
import urllib3
from collections import defaultdict
import psycopg2
import pypdf
import io
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

# --- Configuration & Secrets ---
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = os.environ.get('DB_PORT')

# ✅ CONFIGURATION MULTI-AI (Rotation: DeepSeek → Gemini → Mistral)
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY')
MISTRAL_MODEL = "mistral-large-latest"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"


class BRVMAnalyzer:
    def __init__(self):
        # Mapping complet des symboles vers les slugs d'URL (basé sur les URLs fournies)
        self.symbol_to_slug = {
            'CBIBF': 'coris-bank-international',
            'FTSC': 'filtisac-ci',
            'SIVC': 'air-liquide-ci',
            'BOABF': 'bank-africa-bf',
            'BOAB': 'bank-africa-bn',
            'BOAC': 'bank-africa-ci',
            'BOAM': 'bank-africa-ml',
            'BOAN': 'bank-africa-ng',
            'BOAS': 'bank-africa-sn',
            'BNBC': 'bernabe-ci',
            'BICC': 'bici-ci',
            'BICB': 'biic',
            'SDSC': 'bollore-transport-logistics',
            'CFAC': 'cfao-motors-ci',
            'CIEC': 'cie-ci',
            'SEMC': 'crown-siem-ci',
            'ECOC': 'ecobank-ci',
            'ETIT': 'ecobank-tg',
            'LNBB': 'lnb',
            'NTLC': 'nestle-ci',
            'NEIC': 'nei-ceda-ci',
            'NSBC': 'nsbc',
            'ONTBF': 'onatel-bf',
            'ORGT': 'oragroup',
            'ORAC': 'orange-ci',
            'PALC': 'palm-ci',
            'SAFC': 'safca-ci',
            'SPHC': 'saph-ci',
            'ABJC': 'servair-abidjan-ci',
            'STAC': 'setao-ci',
            'SGBC': 'sgb-ci',
            'SIBC': 'sib',
            'CABC': 'sicable',
            'SICC': 'sicor',
            'STBC': 'sitab',
            'SMBC': 'smb',
            'SDCC': 'sodeci',
            'SOGC': 'sogb',
            'SLBC': 'solibra',
            'SCRC': 'sucrivoire',
            'SNTS': 'sonatel',
            'TTLC': 'total',
            'TTLS': 'total-senegal-sa',
            'PRSC': 'tractafric-ci',
            'UNLC': 'unilever-ci',
            'UNXC': 'uniwax-ci',
            'SHEC': 'vivo-energy-ci'
        }
        
        # Mapping inversé pour les noms de sociétés (pour compatibilité)
        self.societes_mapping = {}
        for symbol, slug in self.symbol_to_slug.items():
            self.societes_mapping[symbol] = {
                'nom_rapport': slug.replace('-', ' ').upper(),
                'alternatives': [slug.replace('-', ' '), slug]
            }
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3',
            'Connection': 'keep-alive',
        })
        
        self.analysis_memory = set()
        self.company_ids = {}
        self.newly_analyzed_reports = []
        self.request_count = {'deepseek': 0, 'gemini': 0, 'mistral': 0}

    def connect_to_db(self):
        """Connexion à PostgreSQL (Supabase)"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, 
                host=DB_HOST, port=DB_PORT, connect_timeout=10
            )
            return conn
        except Exception as e:
            logging.error(f"❌ Erreur connexion DB: {e}")
            return None

    def _load_analysis_memory_from_db(self):
        """
        Charge toutes les URLs déjà analysées en base.
        La contrainte UNIQUE(report_url) garantit qu'un PDF n'est analysé qu'une seule fois.
        Si l'URL est en base → skip définitif, peu importe la date.
        """
        logging.info("📂 Chargement mémoire depuis PostgreSQL...")
        conn = self.connect_to_db()
        if not conn:
            return

        try:
            with conn.cursor() as cur:
                cur.execute("SELECT report_url FROM fundamental_analysis;")
                rows = cur.fetchall()
                # Mode UPSERT: vider la mémoire pour forcer régénération avec nouveau prompt
                self.analysis_memory = set()
                logging.info(f"   🔄 {len(rows)} PDF(s) en base — Mode UPSERT: tous seront régénérés")

        except Exception as e:
            logging.error(f"❌ Erreur chargement mémoire: {e}")
            self.analysis_memory = set()
        finally:
            if conn:
                conn.close()

    def _save_to_db(self, company_id, report, summary, ai_provider="unknown"):
        """
        Sauvegarde une analyse fondamentale.
        La contrainte UNIQUE(report_url) garantit qu'un PDF n'est enregistré qu'une seule fois.
        ON CONFLICT DO NOTHING : si l'URL existe déjà, on ne touche à rien.
        analysis_timestamp enregistre la date/heure de l'analyse.
        """
        conn = self.connect_to_db()
        if not conn:
            return False

        try:
            with conn.cursor() as cur:
                enhanced_summary = f"[Analysé par {ai_provider.upper()} — {datetime.now().strftime('%Y-%m-%d')}]\n\n{summary}"

                cur.execute("""
                    INSERT INTO fundamental_analysis
                        (company_id, report_url, report_title, report_date,
                         analysis_summary, analysis_timestamp)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (report_url) DO UPDATE SET
                        analysis_summary = EXCLUDED.analysis_summary,
                        analysis_timestamp = CURRENT_TIMESTAMP
                    RETURNING id;
                """, (
                    company_id,
                    report['url'],
                    report['titre'],
                    report['date'],
                    enhanced_summary
                ))

                result = cur.fetchone()
                conn.commit()

            if result:
                self.analysis_memory.add(report['url'])
                logging.info(f"    ✅ Sauvegardé (ID: {result[0]}, Provider: {ai_provider.upper()})")
                return True
            else:
                # L'URL existait déjà — la contrainte unique a joué son rôle
                logging.info(f"    ⏭️  URL déjà en base, skip (contrainte unique)")
                return False

        except Exception as e:
            logging.error(f"❌ Erreur sauvegarde: {e}")
            conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def _find_all_reports(self):
        """
        Collecte tous les rapports disponibles via les URLs individuelles
        Utilise requests au lieu de Selenium pour plus de rapidité
        """
        all_reports = defaultdict(list)
        
        logging.info(f"🔍 Collecte des rapports pour {len(self.symbol_to_slug)} sociétés...")
        
        success_count = 0
        error_count = 0
        total_reports = 0
        
        for symbol, slug in self.symbol_to_slug.items():
            url = f"https://www.brvm.org/fr/rapports-societe-cotes/{slug}"
            
            try:
                # Pause pour éviter de surcharger le serveur
                time.sleep(1)
                
                response = self.session.get(url, timeout=15, verify=False)
                
                if response.status_code != 200:
                    logging.warning(f"   ⚠️ {symbol}: HTTP {response.status_code}")
                    error_count += 1
                    continue
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Recherche des liens PDF
                pdf_links = []
                
                # Stratégie 1: Chercher tous les liens PDF
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    text = link.get_text(strip=True)
                    
                    if '.pdf' in href.lower():
                        # Construire l'URL complète
                        if href.startswith('http'):
                            full_url = href
                        elif href.startswith('/'):
                            full_url = 'https://www.brvm.org' + href
                        else:
                            full_url = 'https://www.brvm.org/' + href
                        
                        # Essayer d'extraire une date
                        date_obj = datetime.now().date()
                        
                        # Chercher une année dans le texte ou l'URL
                        year_match = re.search(r'(20\d{2})', text) or re.search(r'(20\d{2})', href)
                        if year_match:
                            year = int(year_match.group(1))
                            # Chercher aussi un mois si possible
                            month_match = re.search(r'/(\d{4})/(\d{2})/', href) or re.search(r'(\d{2})-(\d{4})', text)
                            if month_match and len(month_match.groups()) >= 2:
                                try:
                                    month = int(month_match.group(1)) if len(month_match.group(1)) == 2 else 12
                                    date_obj = datetime(year, month, 1).date()
                                except:
                                    date_obj = datetime(year, 12, 31).date()
                            else:
                                date_obj = datetime(year, 12, 31).date()
                        
                        pdf_links.append({
                            'url': full_url,
                            'titre': text if text else f"Rapport {symbol}",
                            'date': date_obj
                        })
                
                # Stratégie 2: Chercher dans les zones de téléchargement
                if not pdf_links:
                    download_sections = soup.find_all('div', class_=re.compile(r'download|file|attachment|telechargement|content|field'))
                    for section in download_sections:
                        for link in section.find_all('a', href=True):
                            href = link['href']
                            if '.pdf' in href.lower():
                                full_url = href if href.startswith('http') else 'https://www.brvm.org' + href
                                pdf_links.append({
                                    'url': full_url,
                                    'titre': link.get_text(strip=True) or f"Rapport {symbol}",
                                    'date': datetime.now().date()
                                })
                
                # Filtrer et garder les rapports uniques (par URL)
                unique_links = {}
                for link in pdf_links:
                    if link['url'] not in unique_links:
                        unique_links[link['url']] = link
                
                pdf_links = list(unique_links.values())
                
                # Trier par date (plus récent d'abord) et garder les 5 plus récents
                pdf_links.sort(key=lambda x: x['date'], reverse=True)
                recent_links = pdf_links[:5]
                
                if recent_links:
                    all_reports[symbol] = recent_links
                    success_count += 1
                    total_reports += len(recent_links)
                    logging.info(f"   ✅ {symbol}: {len(recent_links)} rapport(s) trouvé(s)")
                    
                    # Log des titres pour débogage
                    for i, report in enumerate(recent_links, 1):
                        logging.info(f"      {i}. {report['titre'][:60]}... ({report['date']})")
                else:
                    logging.info(f"   ⚠️ {symbol}: Aucun rapport trouvé")
                    
            except requests.exceptions.Timeout:
                logging.error(f"   ❌ {symbol}: Timeout")
                error_count += 1
            except requests.exceptions.ConnectionError:
                logging.error(f"   ❌ {symbol}: Erreur de connexion")
                error_count += 1
            except Exception as e:
                logging.error(f"   ❌ {symbol}: Erreur - {str(e)[:100]}")
                error_count += 1
        
        logging.info(f"✅ Collecte terminée: {total_reports} rapport(s) pour {success_count} société(s), {error_count} erreur(s)")
        
        return all_reports

    def _extract_text_from_pdf(self, pdf_url):
        """Extrait le texte d'un PDF — utilise pypdf (successeur de PyPDF2)"""
        try:
            logging.info(f"      📥 Téléchargement PDF: {pdf_url[:80]}...")
            response = self.session.get(pdf_url, timeout=30, verify=False)
            
            if response.status_code != 200:
                logging.warning(f"      ⚠️ HTTP {response.status_code} pour le PDF")
                return None
            
            content_type = response.headers.get('Content-Type', '')
            if 'html' in content_type.lower():
                logging.warning(f"      ⚠️ Le serveur a renvoyé du HTML au lieu d'un PDF (redirection login?)")
                return None
            
            pdf_file = io.BytesIO(response.content)
            logging.info(f"      📦 PDF téléchargé: {len(response.content)/1024:.0f} Ko")
            
            text = ""
            # ✅ Fix: utiliser pypdf (pas PyPDF2), sans context manager (API de base)
            try:
                reader = pypdf.PdfReader(pdf_file)
                nb_pages = len(reader.pages)
                logging.info(f"      📄 {nb_pages} page(s) détectée(s)")
                
                for page_num, page in enumerate(reader.pages, 1):
                    try:
                        page_text = page.extract_text() or ""
                        text += page_text + "\n"
                        if page_num % 10 == 0:
                            logging.info(f"      📄 Page {page_num}/{nb_pages} traitée...")
                    except Exception as e:
                        logging.warning(f"      ⚠️ Page {page_num} illisible: {e}")
                        continue
                        
            except Exception as e:
                logging.warning(f"      ⚠️ Erreur lecture PDF avec pypdf: {e}")
                # Tentative de fallback avec pdfplumber
                try:
                    import pdfplumber
                    pdf_file.seek(0)
                    with pdfplumber.open(pdf_file) as pdf:
                        for page in pdf.pages:
                            text += (page.extract_text() or "") + "\n"
                    logging.info(f"      ✅ Fallback pdfplumber réussi")
                except Exception as e2:
                    logging.error(f"      ❌ Fallback pdfplumber aussi échoué: {e2}")
                    return None
            
            if not text.strip():
                logging.warning(f"      ⚠️ PDF extrait mais vide (PDF scanné/image?)")
                return None
            
            # Nettoyage
            text = re.sub(r'\s+', ' ', text).strip()
            text = unicodedata.normalize('NFKD', text)
            
            # Limiter à 50000 caractères pour les API
            if len(text) > 50000:
                text = text[:50000] + "... [TRONQUÉ]"
            
            logging.info(f"      ✓ Texte extrait: {len(text)} caractères")
            return text
            
        except Exception as e:
            logging.error(f"      ❌ Erreur extraction PDF: {e}")
            return None


    def _fetch_peers_data(self, symbol):
        """Fetche les données peers depuis Supabase pour le peer comparison"""
        try:
            supabase_url = os.environ.get('SUPABASE_URL', '')
            supabase_key = os.environ.get('SUPABASE_SERVICE_KEY', os.environ.get('SUPABASE_ANON_KEY', ''))
            if not supabase_url or not supabase_key:
                return ""
            
            headers = {'apikey': supabase_key, 'Authorization': f'Bearer {supabase_key}'}
            
            # 1. Trouver l'industry du ticker
            url_industry = f"{supabase_url}/rest/v1/company_management?ticker=eq.{symbol}&select=industry"
            r = requests.get(url_industry, headers=headers, timeout=10)
            if r.status_code != 200 or not r.json():
                return ""
            industry = r.json()[0].get('industry')
            if not industry:
                return ""
            
            # 2. Trouver tous les tickers du même secteur
            url_peers = f"{supabase_url}/rest/v1/company_management?industry=eq.{requests.utils.quote(industry)}&select=ticker"
            r = requests.get(url_peers, headers=headers, timeout=10)
            if r.status_code != 200:
                return ""
            peer_tickers = [p['ticker'] for p in r.json()]
            if len(peer_tickers) <= 1:
                return ""
            
            # 3. Fetcher les fondamentaux FY2025 pour tous les peers
            tickers_filter = ','.join(peer_tickers)
            url_fund = f"{supabase_url}/rest/v1/company_fundamentals?ticker=in.({tickers_filter})&fiscal_year=eq.FY2025&select=ticker,revenue,net_income,profit_margin,roe,pe_ratio,pb_ratio,dividend_yield,ebitda_margin"
            r = requests.get(url_fund, headers=headers, timeout=10)
            if r.status_code != 200 or not r.json():
                return ""
            
            peers = r.json()
            if not peers:
                return ""
            
            # 4. Formater le tableau
            lines = [f"PEER COMPARISON — Secteur: {industry} ({len(peers)} sociétés)"]
            lines.append("Ticker | CA (Mds) | RN (Mds) | Marge nette | ROE | P/E | P/B | Div. yield")
            lines.append("-------|----------|----------|-------------|-----|-----|-----|----------")
            
            for p in sorted(peers, key=lambda x: x.get('revenue') or 0, reverse=True):
                ticker = p.get('ticker', 'N/D')
                ca = f"{round(p['revenue']/1000):,}" if p.get('revenue') else 'N/D'
                rn = f"{round(p['net_income']/1000):,}" if p.get('net_income') else 'N/D'
                mg = f"{p['profit_margin']:.1f}%" if p.get('profit_margin') else 'N/D'
                roe = f"{p['roe']:.1f}%" if p.get('roe') else 'N/D'
                pe = f"{p['pe_ratio']:.1f}x" if p.get('pe_ratio') else 'N/D'
                pb = f"{p['pb_ratio']:.1f}x" if p.get('pb_ratio') else 'N/D'
                dy = f"{p['dividend_yield']:.1f}%" if p.get('dividend_yield') else 'N/D'
                marker = " ← CE TITRE" if ticker == symbol else ""
                lines.append(f"{ticker}{marker} | {ca} | {rn} | {mg} | {roe} | {pe} | {pb} | {dy}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logging.warning(f"   ⚠️ Fetch peers échoué pour {symbol}: {e}")
            return ""

    def _analyze_with_deepseek(self, text_content, symbol, report_title):
        """Analyse avec DeepSeek API"""
        if not DEEPSEEK_API_KEY:
            return None
        
        prompt = f"""Tu es un analyste financier expert spécialisé dans la BRVM (Bourse Régionale des Valeurs Mobilières). Analyse ce rapport financier de la société {symbol} ({report_title}).

RAPPORT:
{text_content}

GÉNÈRE UN RAPPORT D'ANALYSE INSTITUTIONNELLE EN FRANÇAIS AVEC CETTE STRUCTURE EXACTE:

---

## INVESTMENT THESIS

Rédige 3 bullet points résumant la thèse d'investissement:
- Position concurrentielle ou croissance principale
- Valorisation ou rendement attractif
- Principal risque ou catalyseur

---

## RECOMMANDATION

**Signal:** [ACHAT FORT / ACHAT / CONSERVER / VENTE / VENTE FORTE]
**Objectif de cours:** [EPS moyen 3 ans x P/E sectoriel ~10x. Si données absentes: N/D]
**Upside/Downside estimé:** [% entre cours actuel et objectif si disponible]
**Niveau de confiance:** [Élevé / Moyen / Faible]
**Horizon:** [Court terme <3 mois / Moyen terme 3-12 mois / Long terme >12 mois]

Justification en 3-4 lignes synthétisant les points clés du rapport.

---

## 1. CHIFFRE D'AFFAIRES & CROISSANCE

Paragraphe de 4-5 lignes:
- Montant exact du CA avec comparaison YoY
- Taux de croissance en valeur et pourcentage
- Moteurs de croissance identifiés (segments, géographies, produits)
- Tendance sur les années disponibles dans le rapport

---

## 2. RENTABILITÉ & MARGES

Paragraphe de 4-5 lignes:
- Résultat net exact et marge nette calculée
- EBITDA si disponible
- ROE et coefficient d'exploitation si disponibles
- Points de pression ou d'amélioration identifiés

---

## 3. DIVIDENDE & CASH FLOW

Paragraphe de 3-4 lignes:
- DPA proposé et taux de distribution
- Rendement estimé sur cours actuel si disponible
- Qualité du cash flow si mentionné
- Soutenabilité du dividende

---

## 4. RISQUES & OPPORTUNITÉS

**Risques classés par impact:**
1. [Élevé] description courte
2. [Moyen] description courte
3. [Faible] description courte

**Catalyseurs haussiers:**
1. Court terme — description
2. Moyen terme — description

**Trigger de révision:** Condition chiffrée qui changerait la recommandation

---

## 5. MOAT RATING — AVANTAGE CONCURRENTIEL

**Rating:** [WIDE / NARROW / NONE]
- **WIDE** = avantage durable >20 ans (monopole, réseau, coûts de switching élevés)
- **NARROW** = avantage limité 10-20 ans (marque forte, efficacité opérationnelle)
- **NONE** = pas d'avantage structurel identifiable

**Justification en 2-3 lignes:** Source de l'avantage concurrentiel identifié dans le rapport.

---

## 6. CONTEXTE SECTORIEL BRVM

Paragraphe de 3-4 lignes:
- Position de la société dans son secteur sur la BRVM
- Comparaison qualitative vs peers si possible
- Impact du contexte macro UEMOA (BCEAO, taux, cycle économique)

---

IMPORTANT:
- Structure OBLIGATOIRE — respecte exactement les 5 sections avec titres markdown
- Cite les chiffres exacts du rapport — ne jamais inventer de données
- Si une donnée est absente, écris N/D
- Mentionne la date et la période du rapport analysé
- Rédige en français professionnel, ton institutionnel
- Reste factuel et objectif"""

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
            "temperature": 0.3
        }
        
        try:
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=120)
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    analysis = result['choices'][0]['message']['content']
                    self.request_count['deepseek'] += 1
                    return analysis
            else:
                logging.warning(f"      ⚠️ DeepSeek erreur {response.status_code}")
                if hasattr(response, 'text'):
                    logging.warning(f"      {response.text[:200]}")
            return None
            
        except Exception as e:
            logging.error(f"      ❌ DeepSeek exception: {e}")
            return None

    def _analyze_with_gemini(self, text_content, symbol, report_title):
        """Analyse avec Gemini API"""
        if not GEMINI_API_KEY:
            return None
        
        prompt = f"""Tu es un analyste financier expert spécialisé dans la BRVM (Bourse Régionale des Valeurs Mobilières). Analyse ce rapport financier de la société {symbol} ({report_title}).

RAPPORT:
{text_content}

CONSIGNES:
Fournis une analyse structurée en français couvrant:

1. CHIFFRE D'AFFAIRES ET ÉVOLUTION
- Montant du chiffre d'affaires
- Évolution par rapport à l'année précédente
- Analyse des tendances

## RECOMMANDATION

**Signal:** [ACHAT FORT / ACHAT / CONSERVER / VENTE / VENTE FORTE]
**Objectif de cours:** [EPS moyen 3 ans x P/E sectoriel ~10x. Si absent: N/D]
**Niveau de confiance:** [Élevé / Moyen / Faible]
**Horizon:** [Court terme / Moyen terme / Long terme]

Justification en 3-4 lignes synthétisant les points clés.

---

## 1. CHIFFRE D'AFFAIRES & CROISSANCE

Paragraphe 4-5 lignes: CA exact, croissance YoY, moteurs, tendance.

---

## 2. RENTABILITÉ & MARGES

Paragraphe 4-5 lignes: résultat net, marge nette, EBITDA, ROE si disponibles.

---

## 3. DIVIDENDE & CASH FLOW

Paragraphe 3-4 lignes: DPA, taux distribution, rendement, soutenabilité.

---

## 4. RISQUES & OPPORTUNITÉS

Risques (Élevé/Moyen/Faible) + Catalyseurs (court/moyen terme) + Trigger de révision.

---

## 5. MOAT RATING — AVANTAGE CONCURRENTIEL

**Rating:** [WIDE / NARROW / NONE]
- WIDE = avantage durable >20 ans
- NARROW = avantage limité 10-20 ans
- NONE = pas d'avantage structurel

Justification en 2-3 lignes depuis le rapport.

---

## 6. CONTEXTE SECTORIEL BRVM

Paragraphe 3-4 lignes: position sectorielle, peers, macro UEMOA.

---

IMPORTANT:
- Structure OBLIGATOIRE — 6 sections avec titres markdown
- Chiffres exacts du rapport uniquement — jamais inventer
- Si donnée absente: N/D
- Français professionnel, ton institutionnel"""

        url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
        
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 2000
            }
        }
        
        try:
            response = requests.post(url, json=data, timeout=120)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    analysis = result['candidates'][0]['content']['parts'][0]['text']
                    self.request_count['gemini'] += 1
                    return analysis
            else:
                logging.warning(f"      ⚠️ Gemini erreur {response.status_code}")
            return None
            
        except Exception as e:
            logging.error(f"      ❌ Gemini exception: {e}")
            return None

    def _analyze_with_mistral(self, text_content, symbol, report_title):
        """Analyse avec Mistral API"""
        if not MISTRAL_API_KEY:
            return None
        
        prompt = f"""Tu es un analyste financier expert spécialisé dans la BRVM (Bourse Régionale des Valeurs Mobilières). Analyse ce rapport financier de la société {symbol} ({report_title}).

RAPPORT:
{text_content}

CONSIGNES:
Fournis une analyse structurée en français couvrant:

1. CHIFFRE D'AFFAIRES ET ÉVOLUTION
- Montant du chiffre d'affaires
- Évolution par rapport à l'année précédente
- Analyse des tendances

## RECOMMANDATION

**Signal:** [ACHAT FORT / ACHAT / CONSERVER / VENTE / VENTE FORTE]
**Objectif de cours:** [EPS moyen 3 ans x P/E sectoriel ~10x. Si absent: N/D]
**Niveau de confiance:** [Élevé / Moyen / Faible]
**Horizon:** [Court terme / Moyen terme / Long terme]

Justification en 3-4 lignes synthétisant les points clés.

---

## 1. CHIFFRE D'AFFAIRES & CROISSANCE

Paragraphe 4-5 lignes: CA exact, croissance YoY, moteurs, tendance.

---

## 2. RENTABILITÉ & MARGES

Paragraphe 4-5 lignes: résultat net, marge nette, EBITDA, ROE si disponibles.

---

## 3. DIVIDENDE & CASH FLOW

Paragraphe 3-4 lignes: DPA, taux distribution, rendement, soutenabilité.

---

## 4. RISQUES & OPPORTUNITÉS

Risques (Élevé/Moyen/Faible) + Catalyseurs (court/moyen terme) + Trigger de révision.

---

## 5. MOAT RATING — AVANTAGE CONCURRENTIEL

**Rating:** [WIDE / NARROW / NONE]
- WIDE = avantage durable >20 ans
- NARROW = avantage limité 10-20 ans
- NONE = pas d'avantage structurel

Justification en 2-3 lignes depuis le rapport.

---

## 6. CONTEXTE SECTORIEL BRVM

Paragraphe 3-4 lignes: position sectorielle, peers, macro UEMOA.

---

IMPORTANT:
- Structure OBLIGATOIRE — 6 sections avec titres markdown
- Chiffres exacts du rapport uniquement — jamais inventer
- Si donnée absente: N/D
- Français professionnel, ton institutionnel"""

        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": MISTRAL_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2500,
            "temperature": 0.3
        }
        
        try:
            response = requests.post(MISTRAL_API_URL, headers=headers, json=data, timeout=120)
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    analysis = result['choices'][0]['message']['content']
                    self.request_count['mistral'] += 1
                    return analysis
            else:
                logging.warning(f"      ⚠️ Mistral erreur {response.status_code}")
            return None
            
        except Exception as e:
            logging.error(f"      ❌ Mistral exception: {e}")
            return None

    def _analyze_pdf_with_multi_ai(self, company_id, symbol, report):
        """Analyse un rapport avec rotation automatique des API"""
        
        url = report['url']
        
        # Si l'URL est déjà en base → skip définitif (contrainte UNIQUE garantit un seul enregistrement)
        if url in self.analysis_memory:
            logging.info(f"    ⏭️  Déjà en base: {report['titre'][:60]}...")
            return None
        
        logging.info(f"    📄 Nouvelle analyse: {report['titre'][:80]}...")
        
        # Extraire le texte du PDF
        text_content = self._extract_text_from_pdf(url)
        
        if not text_content or len(text_content) < 100:
            logging.warning(f"    ⚠️  PDF vide ou illisible pour {symbol} — {report['titre'][:60]}")
            return False
        
        logging.info(f"    📝 {len(text_content)} caractères extraits, envoi à l'IA...")
        
        # Fetch peers data pour peer comparison
        peers_text = self._fetch_peers_data(symbol)
        if peers_text:
            logging.info(f"    📊 Données peers ajoutées ({len(peers_text)} caractères)")
            text_content = text_content + "\n\n" + "="*60 + "\n" + peers_text + "\n" + "="*60
        
        # ROTATION DES API: DeepSeek → Gemini → Mistral
        analysis = None
        provider_used = None
        
        # Tentative 1: DeepSeek
        if DEEPSEEK_API_KEY:
            logging.info("      🤖 Tentative DeepSeek...")
            analysis = self._analyze_with_deepseek(text_content, symbol, report['titre'])
            if analysis:
                provider_used = "deepseek"
                logging.info("      ✅ DeepSeek: Succès!")
        
        # Tentative 2: Gemini
        if not analysis and GEMINI_API_KEY:
            logging.info("      🤖 Tentative Gemini...")
            analysis = self._analyze_with_gemini(text_content, symbol, report['titre'])
            if analysis:
                provider_used = "gemini"
                logging.info("      ✅ Gemini: Succès!")
        
        # Tentative 3: Mistral
        if not analysis and MISTRAL_API_KEY:
            logging.info("      🤖 Tentative Mistral...")
            analysis = self._analyze_with_mistral(text_content, symbol, report['titre'])
            if analysis:
                provider_used = "mistral"
                logging.info("      ✅ Mistral: Succès!")
        
        # Si aucune API n'a fonctionné
        if not analysis:
            logging.error(f"    ❌ Échec des 3 API pour {symbol} — {report['titre'][:60]}")
            fallback_text = f"Analyse automatique indisponible. Rapport: {report['titre']}"
            self._save_to_db(company_id, report, fallback_text, "fallback")
            return False
        
        # Sauvegarde
        if self._save_to_db(company_id, report, analysis, provider_used):
            self.newly_analyzed_reports.append({
                'symbol': symbol,
                'title': report['titre'],
                'provider': provider_used,
                'summary': analysis[:200] + '...'
            })
            return True
        
        return False

    def run_and_get_results(self):
        """Fonction principale"""
        logging.info("="*80)
        logging.info("📄 ÉTAPE 4: ANALYSE FONDAMENTALE (V30.0 - Multi-AI historisée)")
        logging.info("🤖 Rotation: DeepSeek → Gemini → Mistral")
        logging.info("📦 Mode: UPSERT — régénération avec nouveau prompt NYC-style")
        logging.info("="*80)
        
        conn = None
        try:
            # Vérifier les API disponibles avec log détaillé
            available_apis = []
            missing_apis = []
            if DEEPSEEK_API_KEY:
                available_apis.append("DeepSeek")
            else:
                missing_apis.append("DeepSeek (DEEPSEEK_API_KEY absent)")
            if GEMINI_API_KEY:
                available_apis.append("Gemini")
            else:
                missing_apis.append("Gemini (GEMINI_API_KEY absent)")
            if MISTRAL_API_KEY:
                available_apis.append("Mistral")
            else:
                missing_apis.append("Mistral (MISTRAL_API_KEY absent)")
            
            if not available_apis:
                logging.error("❌ Aucune clé API configurée!")
                return {}, []
            
            logging.info(f"✅ API disponibles: {', '.join(available_apis)}")
            if missing_apis:
                logging.warning(f"⚠️  API non configurées (ajouter dans GitHub Secrets): {', '.join(missing_apis)}")
            
            # Charger la mémoire des analyses existantes
            self._load_analysis_memory_from_db()
            
            # Connexion DB pour récupérer les sociétés
            conn = self.connect_to_db()
            if not conn: 
                return {}, []
            
            with conn.cursor() as cur:
                cur.execute("SELECT symbol, id, name FROM companies")
                companies_from_db = cur.fetchall()
            conn.close()
            
            self.company_ids = {symbol: (id, name) for symbol, id, name in companies_from_db}
            
            logging.info(f"\n🔍 Phase 1: Collecte des rapports...")
            all_reports = self._find_all_reports()
            
            logging.info(f"\n🤖 Phase 2: Analyse Multi-AI...")
            
            total_analyzed = 0
            total_skipped = 0
            total_errors = 0
            
            for symbol, (company_id, company_name) in self.company_ids.items():
                logging.info(f"\n📊 {symbol} - {company_name}")
                
                company_reports = all_reports.get(symbol, [])
                
                if not company_reports:
                    logging.info(f"   ⏭️  Aucun rapport disponible")
                    continue
                
                # ✅ Fix bug 4: Filtre élargi à 2020 (au lieu de 2023)
                # Inclut les rapports 2020-2024 pour une meilleure couverture fondamentale
                date_limite = datetime(2020, 1, 1).date()
                recent_reports = [r for r in company_reports if r['date'] >= date_limite]
                recent_reports.sort(key=lambda x: x['date'], reverse=True)
                
                if not recent_reports:
                    logging.info(f"   ⏭️  Aucun rapport depuis 2020")
                    continue
                
                logging.info(f"   📂 {len(recent_reports)} rapport(s) depuis 2020")
                
                # Séparer les déjà en base des nouveaux
                already_analyzed = []
                new_reports = []
                
                for report in recent_reports:
                    if report['url'] in self.analysis_memory:
                        already_analyzed.append(report)
                    else:
                        new_reports.append(report)
                
                logging.info(f"   ✅ Déjà en base (skip): {len(already_analyzed)}")
                logging.info(f"   🆕 Nouveaux à analyser: {len(new_reports)}")
                
                # Max 3 nouveaux rapports par société par run
                for report in new_reports[:3]:
                    try:
                        result = self._analyze_pdf_with_multi_ai(company_id, symbol, report)
                        if result is True:
                            total_analyzed += 1
                        elif result is False:
                            total_errors += 1
                        time.sleep(2)
                    except Exception as e:
                        logging.error(f"    ❌ Erreur analyse: {e}")
                        total_errors += 1
                
                total_skipped += len(already_analyzed)
            
            # Statistiques finales
            logging.info("\n" + "="*80)
            logging.info("✅ ANALYSE FONDAMENTALE TERMINÉE")
            logging.info(f"📊 Nouvelles analyses réussies: {total_analyzed}")
            logging.info(f"📊 Rapports déjà en base (skippés): {total_skipped}")
            logging.info(f"❌ Erreurs (PDF illisible ou API échouée): {total_errors}")
            logging.info(f"📊 Statistiques requêtes API:")
            logging.info(f"   - DeepSeek: {self.request_count['deepseek']}")
            logging.info(f"   - Gemini: {self.request_count['gemini']}")
            logging.info(f"   - Mistral: {self.request_count['mistral']}")
            logging.info(f"   - TOTAL: {sum(self.request_count.values())}")
            logging.info("="*80)
            
            # Récupérer toutes les analyses pour le rapport
            conn = self.connect_to_db()
            if not conn: 
                return {}, self.newly_analyzed_reports
            
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT c.symbol, fa.analysis_summary, c.name 
                    FROM fundamental_analysis fa 
                    JOIN companies c ON fa.company_id = c.id
                    ORDER BY fa.report_date DESC
                """)
                final_results = defaultdict(lambda: {'rapports_analyses': [], 'nom': ''})
                
                for symbol, summary, name in cur.fetchall():
                    final_results[symbol]['rapports_analyses'].append({'analyse_ia': summary})
                    final_results[symbol]['nom'] = name
            
            logging.info(f"📊 Résultats finaux: {len(final_results)} société(s) avec analyses")
            return (dict(final_results), self.newly_analyzed_reports)
        
        except Exception as e:
            logging.critical(f"❌ Erreur critique: {e}", exc_info=True)
            return {}, []
        
        finally:
            if conn and not conn.closed: 
                conn.close()


if __name__ == "__main__":
    analyzer = BRVMAnalyzer()
    analyzer.run_and_get_results()
