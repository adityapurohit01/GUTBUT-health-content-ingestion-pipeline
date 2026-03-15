import json
import logging
import os

from scraper.blog_scraper import BlogScraper
from scraper.youtube_scraper import YouTubeScraper
from scraper.pubmed_scraper import PubMedScraper
from scoring.trust_score import calculate_trust_score
from utils.chunking import chunk_text
from utils.tagging import detect_language, detect_region, extract_topic_tags

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "scraped_data.json")

def process_raw_data(data: dict) -> dict:
    """Enriches the raw dictionary with language, tags, and chunks."""
    raw_text = data.get("raw_text", "")
    
    lang = detect_language(raw_text)
    region = detect_region(data.get("source_url", ""), lang)
    tags = extract_topic_tags(raw_text)
    chunks = chunk_text(raw_text)
    
    return {
        "source_url": data.get("source_url", ""),
        "source_type": data.get("source_type", ""),
        "author": data.get("author", ""),
        "published_date": data.get("published_date", ""),
        "language": lang,
        "region": region,
        "topic_tags": tags,
        "trust_score": "", 
        "content_chunks": chunks,
        "_raw_text_for_scoring": raw_text 
    }

def main():
    blog1 = "https://www.healthline.com/nutrition/gut-microbiome-and-health"
    blog2 = "https://www.medicalnewstoday.com/articles/325293"
    blog3 = "https://zoe.com/learn/how-to-improve-gut-health"
    yt1 = "https://www.youtube.com/watch?v=1sISguPDlhY"
    yt2 = "https://www.youtube.com/watch?v=d-Ln9NNj2KY"
    pubmed1 = "https://pubmed.ncbi.nlm.nih.gov/31315227/"

    sources = [
        ("blog", blog1),
        ("blog", blog2),
        ("blog", blog3),
        ("youtube", yt1),
        ("youtube", yt2),
        ("pubmed", pubmed1)
    ]

    scrapers_map = {
        "blog": BlogScraper(),
        "youtube": YouTubeScraper(),
        "pubmed": PubMedScraper(email="gutbut_pipeline@example.com")
    }

    # Group output by source type
    results = {
        "blog": [],
        "youtube": [],
        "pubmed": []
    }

    logging.info(f"Starting pipeline for {len(sources)} sources...")

    for stype, url in sources:
        logging.info(f"Scraping {stype.upper()} URL: {url}")
        
        scraper = scrapers_map.get(stype)
        if not scraper: continue
            
        raw_data = scraper.scrape(url)
        processed_data = process_raw_data(raw_data)
        
        score = calculate_trust_score(processed_data)
        processed_data["trust_score"] = score
        
        if "_raw_text_for_scoring" in processed_data:
            del processed_data["_raw_text_for_scoring"]

        results[stype].append(processed_data)

    finally_output = results["blog"] + results["youtube"] + results["pubmed"]

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    logging.info(f"Exporting {len(finally_output)} entries cleanly to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(finally_output, f, indent=4, ensure_ascii=False)

    logging.info("Pipeline completed successfully!")

if __name__ == "__main__":
    main()
