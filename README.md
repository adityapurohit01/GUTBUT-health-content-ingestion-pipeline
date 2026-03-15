# 🧬 Health Knowledge Extraction Pipeline (RAG)
![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white) 
![Architecture](https://img.shields.io/badge/Architecture-Modular-success)
![Status](https://img.shields.io/badge/Build-Passing-brightgreen)

A multi-source data ingestion pipeline engineered for health-tech AI platforms. It extracts, semantically chunks, automatically tags, and mathematically scores the trustworthiness of medical content from **Health Blogs**, **YouTube Transcripts**, and **PubMed Research Articles**. 

This repository was built as the foundational data ingestion layer for modern Retrieval-Augmented Generation (RAG) applications.

---

## 🚀 Quick Start
Run the pipeline to successfully scrape all 6 test sources and export them into the final structured JSON artifact in under 60 seconds.

**1. Clone & Install Dependencies**
```bash
git clone https://github.com/adityapurohit01/GUTBUT-health-content-ingestion-pipeline.git
cd GUTBUT-health-content-ingestion-pipeline
pip install bs4 requests biopython youtube-transcript-api langdetect yake newspaper3k lxml_html_clean
```

**2. Execute the Pipeline**
```bash
python main.py
```
*The final structured dataset will be securely written to `output/scraped_data.json`.*

---

## 🏗️ Project Architecture
The codebase strictly adheres to the Single-Responsibility Principle, avoiding monolithic script architectures. 

```text
project/
├── main.py                     # Central orchestrator 
├── scraper/                 
│   ├── blog_scraper.py         # newspaper3k + JS-LD + BS4 fallback loop
│   ├── youtube_scraper.py      # Instance-based transcript API extraction
│   └── pubmed_scraper.py       # Bio.Entrez NCBI API extraction
├── scoring/
│   └── trust_score.py          # 5-factor mathematical heuristic (Spam Prevention)
├── utils/
│   ├── chunking.py             # Semantic sentence-boundary RAG chunker
│   └── tagging.py              # Rapid, local statistical keyword extraction (YAKE)
└── output/
    └── scraped_data.json       # Clean, unified JSON datastore (Generated)
```

---

## 🧠 Engineering Highlights

### 1. The "Triple-Layer" Blog Scraper
Standard health sites heavily encrypt metadata or use Single Page Applications (SPAs) causing HTML scraping to fail. Instead of using a slow, heavy headless browser (Selenium), `scraper/blog_scraper.py` runs a 3-layer defensive protocol:
1. **`newspaper3k`**: A rapid NLP extraction layer.
2. **`JSON-LD`**: If visual tags fail, it digs into the site's hidden `schema.org` payload array to fetch canonical authorship.
3. **`BS4`**: A final safety net utilizing OpenGraph & standard `<meta>` property filters.

### 2. Semantic Context Chunking for RAG
Naive chunking (e.g., slicing strings every 1000 characters) cuts sentences in half and ruins downstream AI embeddings. `utils/chunking.py` utilizes regex end-of-sentence lookbehinds `(?<=[.!?]) +` to cluster *complete sentences* into ~350-word bounded arrays. 

### 3. Anti-Abuse Trust Heuristics
A mathematical formulation designed to filter out SEO spam and snake-oil, mapping articles on a `0.0` to `1.0` certainty continuum:
* **Domain Rank:** Prioritizes `.gov`/`.edu` over standard internet spaces.
* **Author Mapping:** Natively detects `Dr.` and `MD` titles, and penalizes null authors heavily.
* **Medical Liability Check:** Scans the text buffer for defensive medical disclaimers ("not medical advice").
* **Citation & Recency Decay:** Ranks peer-reviewed indexed PubMed data highly (`~0.84+`), while heavily decaying blogs older than 5 years. This dynamically depreciates bad, outdated health advice in the final RAG retrieval system.

---
## 📑 Supporting Documentation
- **[Technical Strategy Report](report.md)**: A 1-2 page dive into the exact parsing methodology and edge-case decisions.
- **[Layman's Explainer](Assignment_Explanation_for_Layman.md)**: A non-technical brief expanding on why specific industry alternatives (LLM Tagging, Headless Browsers) were purposely rejected to save latency and cost.
