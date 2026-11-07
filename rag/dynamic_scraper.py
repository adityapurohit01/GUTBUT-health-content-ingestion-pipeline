import json
import logging
import os
import re
from typing import List, Dict, Any, Optional
from Bio import Entrez

from scraper.pubmed_scraper import PubMedScraper
from scoring.trust_score import calculate_trust_score
from utils.chunking import chunk_text
from utils.tagging import detect_language, detect_region, extract_topic_tags

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

class DynamicScraperEngine:
    """
    Autonomously discovers, scrapes, chunks, scores, and saves new medical research
    when local RAG vector coverage is insufficient for a user's question.
    """

    def __init__(
        self,
        data_path: str = "output/scraped_data.json",
        email: str = "gutbut_autoscraper@example.com"
    ):
        self.data_path = data_path
        self.email = email
        Entrez.email = self.email
        self.pubmed_scraper = PubMedScraper(email=self.email)

    def extract_search_terms(self, query: str) -> str:
        """Strips conversational noise to produce effective biomedical search keywords."""
        stop_words = r'(?i)\b(what|is|are|how|does|do|can|could|tell|me|about|explain|please|the|and|in|of|to|a|an|with|for|on|my|i|you)\b'
        cleaned = re.sub(stop_words, ' ', query)
        cleaned = re.sub(r'[^\w\s-]', ' ', cleaned)
        words = cleaned.split()
        
        # If very short or general, append 'gut' or 'health' for targeted retrieval
        search_query = " ".join(words[:6])
        if len(words) <= 2 and "gut" not in search_query.lower():
            search_query += " gut microbiome"
            
        return search_query.strip()

    def discover_and_scrape(self, query: str, max_articles: int = 2) -> List[Dict[str, Any]]:
        """
        Searches PubMed for articles matching the user query that are not already
        in our local database, scrapes their content, scores them, and writes to disk.
        """
        search_term = self.extract_search_terms(query)
        if not search_term:
            return []

        logging.info(f"🔍 Dynamic Discovery: Searching PubMed for '{search_term}'...")

        try:
            handle = Entrez.esearch(db="pubmed", term=search_term, retmax=max_articles * 2)
            search_results = Entrez.read(handle)
            handle.close()
            pmids = search_results.get("IdList", [])
        except Exception as e:
            logging.error(f"PubMed search failed: {e}")
            return []

        if not pmids:
            logging.info("Dynamic Discovery: No new PubMed articles found.")
            return []

        # Load existing source URLs to avoid duplicating
        existing_urls = set()
        existing_data = []
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    existing_urls = {item.get("source_url") for item in existing_data}
            except Exception as e:
                logging.warning(f"Could not read existing data: {e}")

        newly_ingested = []

        for pmid in pmids:
            if len(newly_ingested) >= max_articles:
                break

            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            if url in existing_urls:
                continue

            logging.info(f"📥 Dynamic Scraping new PubMed article: {url}")
            raw = self.pubmed_scraper.scrape(url)
            raw_text = raw.get("raw_text", "")
            if not raw_text or len(raw_text.strip()) < 50:
                continue

            # Process metadata, chunks, and tags
            lang = detect_language(raw_text)
            region = detect_region(url, lang)
            tags = extract_topic_tags(raw_text)
            chunks = chunk_text(raw_text)

            processed = {
                "source_url": url,
                "source_type": "pubmed",
                "author": raw.get("author", "Medical Researcher"),
                "published_date": raw.get("published_date", ""),
                "language": lang,
                "region": region,
                "topic_tags": tags,
                "trust_score": "",
                "content_chunks": chunks,
                "_raw_text_for_scoring": raw_text
            }

            # Calculate mathematical trust score
            score = calculate_trust_score(processed)
            processed["trust_score"] = score
            del processed["_raw_text_for_scoring"]

            newly_ingested.append(processed)
            existing_data.append(processed)
            existing_urls.add(url)

        if newly_ingested:
            logging.info(f"💾 Saving {len(newly_ingested)} newly scraped and scored sources to {self.data_path}...")
            os.makedirs(os.path.dirname(self.data_path) or ".", exist_ok=True)
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, indent=4, ensure_ascii=False)

        return newly_ingested

