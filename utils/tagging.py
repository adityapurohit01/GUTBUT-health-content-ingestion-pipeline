import yake
from langdetect import detect, DetectorFactory

DetectorFactory.seed = 0

def detect_language(text: str) -> str:
    """Attempts to detect language of the text. Defaults to 'en'."""
    try:
        if not text.strip(): return "en"
        return detect(text)
    except Exception:
        return "en"

def detect_region(url: str, lang: str) -> str:
    """Crude heuristic to detect region based on TLD or Language."""
    url_lower = url.lower()
    if ".co.uk" in url_lower or ".gov.uk" in url_lower or ".nhs.uk" in url_lower or ".uk/" in url_lower: return "UK"
    if ".com.au" in url_lower or ".gov.au" in url_lower or ".au/" in url_lower: return "AU"
    if ".ca/" in url_lower or ".gc.ca" in url_lower: return "CA"
    
    if lang == "en": return "US"
    if lang == "fr": return "FR"
    if lang == "es": return "ES"
    if lang == "de": return "DE"
    
    return "UNKNOWN"

def extract_topic_tags(text: str, num_keywords: int = 5) -> list[str]:
    """Extracts keywords from the text using YAKE."""
    if not text.strip(): return []
    
    text_to_analyze = text[:10000]
    
    custom_kw_extractor = yake.KeywordExtractor(
        lan="en", 
        n=2, 
        dedupLim=0.9, 
        top=num_keywords, 
        features=None
    )
    
    keywords = custom_kw_extractor.extract_keywords(text_to_analyze)
    return [kw[0] for kw in keywords]
