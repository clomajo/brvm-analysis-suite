"""
news_collector.py
═══════════════════════════════════════════════════════════════
BRVM News Pipeline — RSS Feed Collector + AI Sentiment Scoring
═══════════════════════════════════════════════════════════════
Reads RSS feeds from major West African financial outlets,
filters BRVM-relevant articles, scores them with Claude AI,
and saves results to the news_events table in Supabase.

Runs as ÉTAPE 6 in the daily GitHub Actions pipeline.
"""

import os
import logging
import psycopg2
import feedparser
import requests
from datetime import datetime, timezone
from anthropic import Anthropic

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ─── Database connection ───────────────────────────────────────────────────────
def get_db_connection():
    return psycopg2.connect(
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        sslmode="require",
        connect_timeout=30,
    )

# ─── RSS Feed Sources ──────────────────────────────────────────────────────────
RSS_FEEDS = [
    {
        "name": "Agence Ecofin",
        "url": "https://www.agenceecofin.com/rss/bourse.xml",
        "language": "fr",
        "region": "UEMOA",
    },
    {
        "name": "Agence Ecofin - Finance",
        "url": "https://www.agenceecofin.com/rss/finance.xml",
        "language": "fr",
        "region": "UEMOA",
    },
    {
        "name": "Financial Afrik",
        "url": "https://www.financialafrik.com/feed/",
        "language": "fr",
        "region": "Africa",
    },
    {
        "name": "BRVM Official",
        "url": "https://www.brvm.org/fr/rss.xml",
        "language": "fr",
        "region": "BRVM",
    },
    {
        "name": "Lejecos",
        "url": "https://www.lejecos.com/feed/",
        "language": "fr",
        "region": "Senegal",
    },
    {
        "name": "Reuters Africa",
        "url": "https://feeds.reuters.com/reuters/AFRICANews",
        "language": "en",
        "region": "Africa",
    },
]

# ─── BRVM company symbols and keywords ────────────────────────────────────────
BRVM_SYMBOLS = [
    "SGBC", "BICC", "NSBC", "ECOC", "BOAC", "SIBC", "BOABF", "BOAS",
    "BOAM", "BOAN", "BOAB", "BICB", "CBIBF", "ETIT", "ORGT", "SAFC",
    "SOGC", "SNTS", "ORAC", "ONTBF", "PALC", "NTLC", "UNLC", "SLBC",
    "SICC", "SCRC", "STBC", "UNXC", "CABC", "FTSC", "SEMC", "SIVC",
    "STAC", "SMBC", "TTLC", "TTLS", "SHEC", "CIEC", "CFAC", "PRSC",
    "SDSC", "BNBC", "NEIC", "SDCC", "ABJC", "LNBB",
]

BRVM_KEYWORDS = [
    # Market keywords
    "BRVM", "bourse", "action", "cotation", "indice", "BCEAO",
    "UEMOA", "WAEMU", "XOF", "FCFA", "dividende", "résultat",
    # Company names
    "Sonatel", "Ecobank", "Bank of Africa", "SGBCI", "Oragroup",
    "Palm CI", "CFAO", "Totalenergies", "Onatel", "Orange CI",
    "NSIA", "Coris", "Société Générale", "BICICI",
    # Economic keywords
    "taux directeur", "inflation", "croissance", "PIB", "privatisation",
    "introduction en bourse", "émission obligataire", "capitalisation",
    # Country keywords
    "Côte d'Ivoire", "Sénégal", "Burkina", "Mali", "Niger", "Togo",
    "Bénin", "Guinée-Bissau", "Abidjan",
]

# ─── Filter relevant articles ─────────────────────────────────────────────────
def is_brvm_relevant(title, summary):
    text = (title + " " + summary).lower()
    keywords_lower = [k.lower() for k in BRVM_KEYWORDS + BRVM_SYMBOLS]
    return any(kw in text for kw in keywords_lower)

# ─── Score article with Claude AI ─────────────────────────────────────────────
def score_with_claude(client, title, summary, source):
    prompt = f"""You are a financial analyst specializing in West African capital markets (BRVM/UEMOA).

Analyze this news article and return ONLY a valid JSON object — no markdown, no backticks, no extra text.

Source: {source}
Title: {title}
Summary: {summary}

Return exactly this JSON:
{{
  "impact": 1,
  "impact_label": "Positive",
  "confidence": 75,
  "affected_sectors": ["Banque", "Telecom"],
  "affected_symbols": ["SNTS", "ECOC"],
  "category": "Monetary Policy",
  "summary_fr": "Résumé en une phrase de l'impact sur le marché BRVM.",
  "key_risks": ["risque 1"],
  "key_opportunities": ["opportunité 1"],
  "recency": "recent"
}}

Rules:
- impact: 1=positive, 0=neutral, -1=negative
- confidence: 0-100
- affected_sectors: only from [Banque, Telecom, Industrie, Energie, Distribution, Services]
- affected_symbols: only real BRVM symbols if mentioned, empty array if none specific
- category: one of [Monetary Policy, Regulation, Legislation, Trade Policy, Earnings, Dividend, Market News, Political, Commodity, Other]
- recency: "recent" always for new articles"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = message.content[0].text.strip()
        import json
        return json.loads(text)
    except Exception as e:
        logger.warning(f"Claude scoring failed: {e}")
        return None

# ─── Fetch and parse RSS feeds ────────────────────────────────────────────────
def fetch_rss_articles():
    articles = []
    for feed_info in RSS_FEEDS:
        try:
            logger.info(f"📡 Fetching {feed_info['name']}...")
            feed = feedparser.parse(feed_info["url"])
            count = 0
            for entry in feed.entries[:20]:  # Max 20 articles per feed
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))[:500]
                link = entry.get("link", "")
                published = entry.get("published", "")

                # Parse date
                try:
                    if entry.get("published_parsed"):
                        pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    else:
                        pub_date = datetime.now(timezone.utc)
                except Exception:
                    pub_date = datetime.now(timezone.utc)

                if is_brvm_relevant(title, summary):
                    articles.append({
                        "source": feed_info["name"],
                        "title": title,
                        "summary": summary[:500],
                        "url": link,
                        "published_at": pub_date,
                        "language": feed_info["language"],
                        "region": feed_info["region"],
                    })
                    count += 1

            logger.info(f"  ✅ {count} relevant articles found in {feed_info['name']}")
        except Exception as e:
            logger.warning(f"  ⚠️ Failed to fetch {feed_info['name']}: {e}")

    logger.info(f"📰 Total relevant articles: {len(articles)}")
    return articles

# ─── Check if article already exists ──────────────────────────────────────────
def article_exists(conn, url):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM news_events WHERE url = %s", (url,))
        return cur.fetchone() is not None

# ─── Save scored article to database ──────────────────────────────────────────
def save_article(conn, article, scoring):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO news_events (
                source, title, summary, url, published_at, language, region,
                impact, impact_label, confidence, affected_sectors,
                affected_symbols, category, ai_summary, key_risks,
                key_opportunities, recency, scored_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (url) DO NOTHING
        """, (
            article["source"],
            article["title"],
            article["summary"],
            article["url"],
            article["published_at"],
            article["language"],
            article["region"],
            scoring.get("impact", 0),
            scoring.get("impact_label", "Neutral"),
            scoring.get("confidence", 50),
            scoring.get("affected_sectors", []),
            scoring.get("affected_symbols", []),
            scoring.get("category", "Other"),
            scoring.get("summary_fr", ""),
            scoring.get("key_risks", []),
            scoring.get("key_opportunities", []),
            scoring.get("recency", "recent"),
            datetime.now(timezone.utc),
        ))
        conn.commit()

# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    logger.info("=" * 70)
    logger.info("📰 ÉTAPE 6: COLLECTE NEWS & SCORING IA (Claude)")
    logger.info("=" * 70)

    # Check API key
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        logger.error("❌ ANTHROPIC_API_KEY not set — skipping news scoring")
        return

    client = Anthropic(api_key=anthropic_key)
    logger.info("✅ Claude API ready")

    # Connect to database
    try:
        conn = get_db_connection()
        logger.info("✅ Database connected")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return

    # Fetch RSS articles
    articles = fetch_rss_articles()
    if not articles:
        logger.info("ℹ️ No relevant articles found today")
        conn.close()
        return

    # Score and save each article
    saved = 0
    skipped = 0
    failed = 0

    for article in articles:
        try:
            # Skip if already in database
            if article_exists(conn, article["url"]):
                skipped += 1
                continue

            # Score with Claude
            logger.info(f"🤖 Scoring: {article['title'][:60]}...")
            scoring = score_with_claude(
                client,
                article["title"],
                article["summary"],
                article["source"]
            )

            if scoring:
                save_article(conn, article, scoring)
                saved += 1
                logger.info(f"  ✅ Saved — Impact: {scoring.get('impact_label')} ({scoring.get('confidence')}% confidence)")
            else:
                failed += 1

        except Exception as e:
            logger.error(f"  ❌ Error processing article: {e}")
            failed += 1

    conn.close()

    logger.info("=" * 70)
    logger.info(f"📊 RÉSULTATS NEWS PIPELINE:")
    logger.info(f"  ✅ Articles sauvegardés: {saved}")
    logger.info(f"  ⏭  Articles skippés (déjà en base): {skipped}")
    logger.info(f"  ❌ Erreurs: {failed}")
    logger.info("=" * 70)

if __name__ == "__main__":
    main()
