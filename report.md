# Data Scraping Assignment: Pipeline Strategy & Implementation Report

## Overview
This report details the architectural design and strategic implementation of a multi-source content ingestion pipeline designed for AI health platforms, such as GutBut or MedLe. The goal is to ingest un-structured health data from Blogs, YouTube, and PubMed, process it for semantic context, and assign it a mathematical trust score before saving it to a unified JSON datastore. 

## 1. Scraping Strategy
To adhere to the principle of "Minimal Code" without sacrificing robust functionality, a layered extraction strategy was built utilizing specific libraries adapted to each platform's structure:

*   **Blogs (`newspaper3k` & `bs4`)**: Standard headless browser environments (like `selenium`) are far too heavy and slow. Instead, `newspaper3k` operates as the primary high-speed text extractor. To combat heavily obfuscated JavaScript-rendered health sites (e.g., Zoe, Healthline) where standard HTML meta-tags for dates or authors are missing, the pipeline implements a triple-layer fallback: it scans the hidden `JSON-LD` (schema.org) structured data payloads directly, and falls back to defensively querying specific `BeautifulSoup` meta-tags as a last resort.
*   **YouTube (`youtube-transcript-api`)**: Rather than requesting keys from Google Cloud Platform, `youtube-transcript-api` uses the internal, publicly available caption endpoints. The pipeline filters specifically for English `['en']` transcripts. Metadata like Channel Name and Publish Date, which are not present in the bare transcript data, are scraped concurrently by requesting the video HTML structure and extracting OpenGraph tags (`itemprop="name"` and `uploadDate`).
*   **PubMed (`biopython` / `Bio.Entrez`)**: Scraping scientific HTML pages is notoriously unstable. Instead, the native NCBI Entrez API was used. This guarantees cleanly parsed `XML` metadata without DOM scraping. The script extracts the PMIDs from provided URLs and pulls Journal Title, full Abstract combinations, Authors, and canonical Publication Year definitively.

## 2. Topic Tagging Method
Extracting relevant topic tags is critical for metadata vector searches (RAG mappings). 

While `spaCy` or `KeyBERT` provide high accuracy, they require downloading massive language models which drastically limit pipeline portability and testability in constrained environments. 

**Solution: YAKE (Yet Another Keyword Extractor)**
We implemented `yake`, an unsupervised automatic keyword extraction method. It rests entirely on statistical text features (casing, word frequency, position, sentence context) rather than deep learning dictionaries. 
*   **Configuration**: The configuration operates with a maximum n-gram size of 2 (bigrams) to extract standard medical terms (e.g., "gut microbiome"), and a heavy deduplication limit of `0.9` to prevent semantic repetition across the 5 output keywords.

## 3. Trust Scoring Algorithm
A weighted mathematical trust formulation ranks ingested sources on a `0.0` to `1.0` certainty continuum. The scoring operates across 5 heuristic rules:

1.  **Author Credibility (Weight: 30%)**: Default scores are set to 0.5. The text undergoes title detection mapping `("dr.", "md", "ph.d")` to boost the score to 0.9. Missing authors immediately truncate the base sub-score to 0.1, whereas PubMed indexed authors receive a guaranteed 1.0.
2.  **Domain Authority (Weight: 20%)**: Domain TLDs are parsed from the origin URL. High-trust bodies (`.gov`, `.edu`, `pubmed.ncbi.nlm.nih.gov`) hold standard `0.9` to `1.0` ceilings. Standard `.com` spaces retain medium priority (`0.4`), and untagged/non-standard sites drop to `0.2`.
3.  **Citation Count (Weight: 20%)**: RAG pipelines fundamentally distrust uncited assertions. A regex parses `[1]`-style brackets and `(Author, Year)` inline placements. Up to 10 identified citations scales the sub-score to `1.0` maximum.
4.  **Recency (Weight: 20%)**: Medical literature decays in accuracy rapidly over time. The string timestamps are converted to Unix variants. Content `< 1 year` old maxes at `1.0`, `< 3 years` at `0.8`, and steeply penalizes contents `>= 5 years` old to `0.2`.
5.  **Medical Disclaimer (Weight: 10%)**: Standard internet medical liabilities ("not medical advice", "consult a doctor") are string-matched (lowercased) against the raw un-chunked buffer body. An absence of disclaimers operates as a `0.0` on this specific metric. 

## 4. Edge Case Handling & Processing Resiliency
Building an abuse-prevention logic demands gracefully failing bad data without pipeline closures.
*   **Language and Region Safeguards**: All inputs check against `langdetect`. Non-English or broken encodings don't crash but return their detected strings. Regions operate on coarse Top-Level Domain (TLD) heuristics or regional language boundaries (e.g., matching English loosely to US, UK, AU hints).
*   **Semantic Chunking**: Large texts break context windows. A custom splitter utilizes regex end-of-sentence look-behinds `(?<=[.!?]) +` to cleanly slice sentences up to a 350-word cap. Sentences are structurally left intact ensuring LLMs do not drop mid-verb mappings in the resulting JSON chunks arrays.
*   **False Medical Claims**: The overarching Trust Formula dynamically catches sensational pages generated by fake personas by chaining together the `0.1` missing-author limit, a low domain rank (`0.4`), and the absence of a liability clause (`0.0`), driving the general trust score down severely—thereby deprioritizing its RAG retrieval.
