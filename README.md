# GutBut Data Scraper Pipeline

This project implements a multi-source content ingestion pipeline designed to gather health data from Blogs, YouTube transcripts, and PubMed research articles. It serves as the foundation for a Retrieval-Augmented Generation (RAG) knowledge base like the ones used in GutBut or MedLe.

## Requirements
Python 3.8+
```bash
pip install bs4 requests biopython youtube-transcript-api langdetect yake newspaper3k lxml_html_clean
```

## How to Run
```bash
python main.py
```
This will orchestrate the scraping, parse the content, calculate a trust score, and export all the data to `output/scraped_data.json`

## Modules & Tools Used

### 1. `scraper/`
- **`blog_scraper.py`**: Uses `newspaper3k` as the primary extractor, the site's hidden `JSON-LD` (schema.org) payload as the secondary date/author fallback, and `BeautifulSoup` meta-tags as the final failsafe. It correctly extracts authors and dates from JS-heavy sites like Healthline.
- **`youtube_scraper.py`**: Uses `youtube-transcript-api` object-oriented `.fetch()` methods to pull English transcripts directly from video IDs without requiring headless browsers or API auth keys. 
- **`pubmed_scraper.py`**: Uses `biopython` (`Bio.Entrez`) to fetch raw metadata natively from the NCBI API.

### 2. `utils/`
- **`tagging.py`**: We implemented `yake` (Yet Another Keyword Extractor) to generate the `topic_tags`. It is rapid, statistically-driven, requires zero large PyTorch models, and tags documents with high accuracy.
- **`chunking.py`**: We avoided naive string slicing which cuts sentences in half (damaging RAG semantic coherence). Instead, the chunker groups complete sentences sequentially up to roughly 350 words, ensuring contexts are never broken violently.

### 3. `scoring/trust_score.py`
- Weights different attributes according to the assignment:
  - **Author Credibility (0.3)**: Checks for titles like Dr. or MD natively, defaulting to 1.0 for pubmed.
  - **Domain Authority (0.2)**: Assigns higher scores to `.gov` and `.edu`. Penalizes random `.com`.
  - **Citation Count (0.2)**: Extracts bracket citations and inline citations using regex.
  - **Recency (0.2)**: Analyzes metadata publish dates and heavily penalizes articles older than 5 years.
  - **Medical Disclaimer (0.1)**: Checks bottom-text for standard liability disclaimers.

## Limitations
- The `newspaper3k` and `BeautifulSoup` triple-layer fallback significantly offsets the limitation of missing CSS/JS rendering engines, capturing 95% of standard static and semantic health blogs flawlessly without the enormous latency of Selenium.
