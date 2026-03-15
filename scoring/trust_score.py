import re
from datetime import datetime

def check_medical_disclaimer(text: str) -> bool:
    """Returns True if common medical disclaimer language is found."""
    disclaimer_phrases = [
        "not medical advice",
        "consult a doctor",
        "consult your physician",
        "for educational purposes",
        "for informational purposes only"
    ]
    text_lower = text.lower()
    for phrase in disclaimer_phrases:
        if phrase in text_lower:
            return True
    return False

def count_citations(text: str) -> int:
    """Estimates citation count based on brackets [1] or (Author, Year) patterns."""
    # Count [1], [2], etc.
    bracket_citations = len(re.findall(r'\[\d+\]', text))
    
    # Count (Author, YYYY) roughly
    author_year_citations = len(re.findall(r'\([A-Za-z]+, \d{4}\)', text))
    
    return bracket_citations + author_year_citations

def calculate_trust_score(item: dict) -> float:
    """
    Computes a trust score between 0.0 and 1.0 based on 5 factors:
    - Author Credibility (30%)
    - Domain Authority (20%)
    - Citation Count (20%)
    - Recency (20%)
    - Disclaimer Presence (10%)
    """
    author = item.get("author", "")
    source_type = item.get("source_type", "")
    source_url = item.get("source_url", "")
    published_date = item.get("published_date", "")
    raw_text = item.get("_raw_text_for_scoring", "")
    
    # --- 1. Author Credibility (0.3) ---
    author_score = 0.5 # default unknown author
    if not author:
        author_score = 0.1 # heavily penalize missing author
    else:
        author_lower = author.lower()
        if source_type == "pubmed":
             author_score = 1.0 # Indexed researchers
        else:
             medical_titles = ["dr.", "md", "ph.d", "doctor"]
             for title in medical_titles:
                 if title in author_lower:
                     author_score = 0.9
                     break
                 
    # --- 2. Domain Authority (0.2) ---
    domain_score = 0.4 # Default
    if "pubmed.ncbi.nlm.nih.gov" in source_url or "nih.gov" in source_url:
        domain_score = 1.0
    elif "youtube.com" in source_url or "youtu.be" in source_url:
        domain_score = 0.7 # Platform doesn't guarantee info
    elif ".edu" in source_url or ".gov" in source_url or ".org" in source_url:
        domain_score = 0.9
    elif ".com" in source_url:
        # Penalize unknown .com domains slightly more than standard
        domain_score = 0.4
    else:
        domain_score = 0.2
        
    # --- 3. Citation Count (0.2) ---
    citations = count_citations(raw_text)
    citation_score = min(citations / 10.0, 1.0) # Cap at 10 citations = 1.0
    # PubMed is peer reviewed, so it gets max score automatically implicitly
    if source_type == "pubmed": citation_score = 1.0 
    
    # --- 4. Recency (0.2) ---
    recency_score = 0.1 # Default penalty for missing date
    if published_date:
        try:
            pub_dt = datetime.strptime(published_date, "%Y-%m-%d")
            age_days = (datetime.now() - pub_dt).days
            age_years = age_days / 365.25
            
            if age_years < 1: recency_score = 1.0
            elif age_years < 3: recency_score = 0.8
            elif age_years < 5: recency_score = 0.5
            else: recency_score = 0.2 # Penalty for > 5 years old
        except ValueError:
             pass # keeping 0.1 if parsing fails
             
    # --- 5. Medical Disclaimer (0.1) ---
    disclaimer_score = 0.0
    if check_medical_disclaimer(raw_text) or source_type == "pubmed":
        disclaimer_score = 1.0 # PubMed is inherently factual research
        
    score = (0.30 * author_score) + (0.20 * domain_score) + (0.20 * citation_score) + (0.20 * recency_score) + (0.10 * disclaimer_score)
    
    return round(score, 3)
