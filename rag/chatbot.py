import logging
import os
import re
from typing import List, Dict, Any, Generator, Optional
from google import genai
from google.genai import types
from rag.vector_store import HealthVectorStore
from rag.dynamic_scraper import DynamicScraperEngine

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

SYSTEM_INSTRUCTION = """You are GutBut Health Assistant, an evidence-grounded medical AI assistant.
Your mission is to provide accurate, reliable, and transparent answers to health and wellness questions, grounded strictly in vetted content retrieved from our health knowledge pipeline.

CONTEXT & TRUST SCORING:
You are provided with relevant retrieved passages. Each passage includes:
- Source Type (PubMed Research, Blog, YouTube)
- Author / Organization
- Publication Date
- URL
- Mathematical Trust Score (0.0 to 1.0, where higher scores indicate peer-reviewed literature, medical credentials, and verified citations).

CRITICAL RESPONSE GUIDELINES:
1. Grounding: Answer strictly using facts from the provided context. If the context does not contain enough information to answer safely and comprehensively, honestly admit what is missing.
2. Source Transparency & Citations: In-line or at the end of each key point, cite the source name and its Trust Score (e.g., "[PubMed PMID: 31315227, Trust: 0.84]" or "[Healthline, Ruairi Robertson, Trust: 0.27]").
3. Scientific Hierarchy: Prioritize peer-reviewed scientific papers (PubMed) over general consumer blogs or video transcripts.
4. Professional Medical Disclaimer: Conclude any clinical or wellness advice with a standard educational disclaimer ("Note: This information is for educational purposes and is not a substitute for professional medical advice. Always consult a healthcare provider.").
"""

class HealthRAGChatbot:
    """
    RAG Chatbot using Gemini 3.5 Flash and Trust-Weighted Retrieval.
    """

    def __init__(
        self,
        vector_store: HealthVectorStore,
        api_key: Optional[str] = None,
        model_name: str = "gemini-3.5-flash",
        min_trust_score: float = 0.0
    ):
        self.vector_store = vector_store
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required to initialize HealthRAGChatbot.")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name
        self.min_trust_score = min_trust_score
        self.auto_scraper = DynamicScraperEngine()
        self.history: List[Dict[str, str]] = []

    def _format_context(self, retrieved_chunks: List[Dict[str, Any]]) -> str:
        """Formats retrieved chunks into structured context for Gemini."""
        if not retrieved_chunks:
            return "No matching sources passed the trust threshold for this query."

        lines = ["=== RETRIEVED VETTED HEALTH PASSAGES ==="]
        for idx, c in enumerate(retrieved_chunks, 1):
            lines.append(
                f"\n[Source #{idx}]\n"
                f"- Type: {c['source_type'].upper()}\n"
                f"- Author: {c['author']}\n"
                f"- Date: {c['published_date'] or 'Unknown'}\n"
                f"- URL: {c['source_url']}\n"
                f"- Trust Score: {c['trust_score']:.2f} (Similarity: {c['similarity']:.2f}, Composite: {c['composite_score']:.2f})\n"
                f"- Content Passage:\n\"{c['text']}\"\n"
            )
        lines.append("=========================================")
        return "\n".join(lines)

    def _is_coverage_insufficient(self, chunks: List[Dict[str, Any]], user_query: str) -> bool:
        """
        Detects if existing knowledge lacks coverage on the user's specific topic,
        using both similarity score threshold and subject-matter presence checks.
        """
        if not chunks:
            return True

        top_similarity = chunks[0].get("similarity", 0.0)
        if top_similarity < 0.62:
            return True

        # Extract specific subject keywords (filtering out generic domain words)
        words = [re.sub(r'[^\w]', '', w.lower()) for w in user_query.split()]
        common_terms = {
            "what", "is", "are", "how", "does", "do", "can", "could", "tell", "me", "about",
            "explain", "the", "and", "in", "of", "to", "a", "an", "with", "for", "on", "my",
            "microbiome", "bacteria", "gut", "health", "affect", "affects", "effect", "effects",
            "influence", "body", "human", "system", "role", "help", "work", "ways", "article",
            "research", "study", "studies"
        }
        subject_keywords = [w for w in words if len(w) > 3 and w not in common_terms]
        if subject_keywords:
            combined_text = " ".join([c["text"].lower() for c in chunks[:3]])
            has_subject = any(term in combined_text for term in subject_keywords)
            if not has_subject:
                return True

        return False

    def ask(
        self,
        user_query: str,
        top_k: int = 4,
        min_trust_score: Optional[float] = None,
        auto_scrape: bool = True
    ) -> Dict[str, Any]:
        """
        Retrieves trustworthy passages and generates a grounded response.
        If local evidence is insufficient, autonomously discovers and scrapes
        new medical literature from PubMed, scores it, and embeds it.
        """
        threshold = self.min_trust_score if min_trust_score is None else min_trust_score
        
        # 1. First retrieval attempt against local database
        chunks = self.vector_store.search(
            query=user_query,
            top_k=top_k,
            min_trust_score=threshold
        )

        newly_scraped = []
        # 2. Check if coverage is insufficient
        if auto_scrape and self._is_coverage_insufficient(chunks, user_query):
            logging.info(f"⚡ Local coverage low or missing key terms. Triggering dynamic auto-scraper...")
            new_sources = self.auto_scraper.discover_and_scrape(user_query, max_articles=2)
            if new_sources:
                newly_scraped = new_sources
                self.vector_store.add_new_sources(new_sources)
                # Re-retrieve with newly indexed evidence
                chunks = self.vector_store.search(
                    query=user_query,
                    top_k=top_k,
                    min_trust_score=threshold
                )

        formatted_context = self._format_context(chunks)

        # 3. Build Prompt
        prompt = (
            f"{formatted_context}\n\n"
            f"User Question: {user_query}\n\n"
            f"Please synthesize a clear, trustworthy answer addressing the user's question with citations."
        )

        # 3. Call Gemini with fallback
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.2, # Low temperature for factual consistency
                )
            )
            answer_text = response.text or "I could not generate an answer based on the provided sources."
        except Exception as e:
            logging.warning(f"Error calling {self.model_name}: {e}. Trying fallback 'gemini-3.5-flash-lite'...")
            try:
                response = self.client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.2
                    )
                )
                answer_text = response.text or "I could not generate an answer based on the provided sources."
            except Exception as e2:
                logging.error(f"Fallback also failed: {e2}")
                answer_text = f"An error occurred while communicating with Gemini API: {e2}"

        # 4. Save to history
        self.history.append({"user": user_query, "assistant": answer_text})

        return {
            "answer": answer_text,
            "sources": chunks,
            "min_trust_used": threshold,
            "newly_scraped": [
                {
                    "url": s["source_url"],
                    "author": s["author"],
                    "trust": s["trust_score"]
                }
                for s in newly_scraped
            ]
        }

    def reset_history(self):
        """Clears conversation history."""
        self.history = []

