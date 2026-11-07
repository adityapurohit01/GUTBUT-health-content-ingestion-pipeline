import json
import os
import pytest
from dotenv import load_dotenv

load_dotenv()

from utils.chunking import chunk_text
from utils.tagging import detect_language, detect_region, extract_topic_tags
from scoring.trust_score import calculate_trust_score, check_medical_disclaimer, count_citations
from rag.vector_store import HealthVectorStore
from rag.chatbot import HealthRAGChatbot

# ==========================================
# 1. UNIT TESTS: PROCESSING & SCORING LOGIC
# ==========================================

def test_chunking_preserves_sentences():
    text = (
        "The gut microbiome plays a vital role in human digestion. "
        "Short-chain fatty acids are produced by fermenting dietary fiber. "
        "These acids nourish the colon epithelial cells and protect against disease."
    )
    chunks = chunk_text(text, words_per_chunk=15)
    assert len(chunks) > 0
    for c in chunks:
        assert c.strip()[-1] in ".!?"

def test_chunking_empty_text():
    assert chunk_text("") == []
    assert chunk_text("   ") == []

def test_language_detection():
    assert detect_language("This is a medical paper written in English about microbiome health.") == "en"

def test_region_detection():
    assert detect_region("https://www.nhs.uk/conditions/gut", "en") == "UK"
    assert detect_region("https://health.ca/gut", "en") == "CA"
    assert detect_region("https://healthline.com", "en") == "US"

def test_topic_tagging():
    health_text = "The gut microbiome contains trillions of intestinal bacteria that produce butyrate and regulate immune health."
    tags = extract_topic_tags(health_text, num_keywords=3)
    assert len(tags) > 0
    assert any("gut" in t.lower() or "microbiome" in t.lower() or "bacteria" in t.lower() for t in tags)

def test_medical_disclaimer_detection():
    assert check_medical_disclaimer("This article is for informational purposes only and is not medical advice.") is True
    assert check_medical_disclaimer("Consult a doctor before taking any supplements.") is True
    assert check_medical_disclaimer("Eat more apples every day.") is False

def test_citation_counting():
    text_with_citations = "Previous studies have shown positive effects [1], [2] and according to (Smith, 2020) fiber is essential."
    assert count_citations(text_with_citations) == 3

def test_trust_score_pubmed_peer_reviewed():
    item = {
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        "source_type": "pubmed",
        "author": "Dr. Alice Smith, Dr. Bob Jones",
        "published_date": "2024-01-01",
        "_raw_text_for_scoring": "A peer reviewed clinical trial on microbiome."
    }
    score = calculate_trust_score(item)
    assert score >= 0.80

def test_trust_score_missing_author_penalty():
    no_author_item = {
        "source_url": "https://randomhealthspam.com/article",
        "source_type": "blog",
        "author": "",
        "published_date": "2015-01-01",
        "_raw_text_for_scoring": "Buy our miracle cure now."
    }
    score = calculate_trust_score(no_author_item)
    assert score <= 0.35

def test_trust_score_multiple_authors_average():
    item = {
        "source_url": "https://example.com/blog",
        "source_type": "blog",
        "author": "Dr. Jane Doe, John Public",
        "published_date": "2024-01-01",
        "_raw_text_for_scoring": "Gut health overview. Consult a doctor before changes."
    }
    score = calculate_trust_score(item)
    assert 0.40 <= score <= 0.85


# ==========================================
# 2. END-TO-END TESTS: SCRAPED DATA & STORAGE
# ==========================================

def test_e2e_scraped_data_schema():
    """Validates the scraped dataset against the assignment specifications."""
    data_path = "output/scraped_data.json"
    assert os.path.exists(data_path), f"Missing {data_path}"

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) >= 6, "Expected at least 6 scraped sources."

    source_types = set()
    for item in data:
        # Check required schema fields
        for field in ["source_url", "source_type", "author", "published_date", "language", "region", "topic_tags", "trust_score", "content_chunks"]:
            assert field in item, f"Missing field '{field}' in item {item.get('source_url')}"

        assert item["source_type"] in ["blog", "youtube", "pubmed"]
        source_types.add(item["source_type"])
        assert isinstance(item["topic_tags"], list)
        assert len(item["topic_tags"]) > 0
        assert isinstance(item["content_chunks"], list)
        assert len(item["content_chunks"]) > 0
        assert 0.0 <= float(item["trust_score"]) <= 1.0

    # Ensure all three platform types are present
    assert "blog" in source_types
    assert "youtube" in source_types
    assert "pubmed" in source_types


# ==========================================
# 3. END-TO-END TESTS: VECTOR STORE & EMBEDDINGS
# ==========================================

def test_e2e_vector_cache_storage():
    """Validates that vectors are stored on disk with correct 3072 dimensions."""
    cache_path = "output/embeddings.json"
    assert os.path.exists(cache_path), f"Vector cache missing at {cache_path}"

    with open(cache_path, "r", encoding="utf-8") as f:
        cache = json.load(f)

    assert len(cache) > 0, "Vector cache is empty"
    for record in cache:
        assert "chunk_id" in record
        assert "embedding" in record
        assert isinstance(record["embedding"], list)
        # Gemini gemini-embedding-2 produces 3072-dimensional vectors
        assert len(record["embedding"]) == 3072

def test_e2e_rag_vector_search_and_ranking():
    """Tests that semantic retrieval computes similarity and composite scores."""
    store = HealthVectorStore()
    results = store.search("short-chain fatty acids butyrate health benefits", top_k=3)

    assert len(results) > 0
    top = results[0]
    assert "text" in top
    assert "similarity" in top
    assert "trust_score" in top
    assert "composite_score" in top
    assert top["composite_score"] > 0

def test_e2e_rag_trust_filtering():
    """Tests that min_trust_score strictly excludes low-trust sources."""
    store = HealthVectorStore()
    # High trust threshold only accepts peer-reviewed PubMed (trust = 0.84)
    results = store.search("microbiome disease link", top_k=5, min_trust_score=0.7)

    assert len(results) > 0
    for r in results:
        assert r["trust_score"] >= 0.7
        assert r["source_type"] == "pubmed"


# ==========================================
# 4. END-TO-END TESTS: RAG CHATBOT (GEMINI)
# ==========================================

def test_e2e_rag_chatbot_response():
    """Tests end-to-end question answering and source grounding with Gemini."""
    store = HealthVectorStore()
    bot = HealthRAGChatbot(vector_store=store)

    query = "What do short chain fatty acids do in the gut?"
    res = bot.ask(query, top_k=2)

    assert "answer" in res
    assert len(res["answer"]) > 50
    assert "sources" in res
    assert len(res["sources"]) > 0

    # Ensure response contains grounding or citation indicators
    ans_text = res["answer"].lower()
    has_substance = ("fatty" in ans_text or "butyrate" in ans_text or "fiber" in ans_text or "gut" in ans_text)
    assert has_substance, "Expected answer to discuss fatty acids or gut health"
