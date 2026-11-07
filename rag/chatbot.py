import logging
import os
from typing import List, Dict, Any, Generator, Optional
from google import genai
from google.genai import types
from rag.vector_store import HealthVectorStore

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

    def ask(
        self,
        user_query: str,
        top_k: int = 4,
        min_trust_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Retrieves trustworthy passages and generates a grounded response.
        """
        threshold = self.min_trust_score if min_trust_score is None else min_trust_score
        
        # 1. Retrieve trust-weighted context chunks
        chunks = self.vector_store.search(
            query=user_query,
            top_k=top_k,
            min_trust_score=threshold
        )

        formatted_context = self._format_context(chunks)

        # 2. Build Prompt
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
            "min_trust_used": threshold
        }

    def reset_history(self):
        """Clears conversation history."""
        self.history = []

