import argparse
import os
import sys
from dotenv import load_dotenv

# Load environment variables (.env)
load_dotenv()

from rag.vector_store import HealthVectorStore
from rag.chatbot import HealthRAGChatbot

def print_banner():
    banner = """
===================================================================
      🧬 GUTBUT TRUST-AWARE HEALTH RAG CHATBOT (Powered by Gemini)
===================================================================
 Gathers evidence from PubMed, Health Blogs, and YouTube transcripts.
 Content is mathematically graded for trust & medical credibility.

 Commands:
   /trust <score>  - Set minimum trust filter (e.g. /trust 0.5 or /trust 0.8)
   /sources        - View all indexed sources and their trust scores
   /clear          - Clear conversation history
   /help           - Show this help menu
   /exit or /quit  - Exit the chatbot
===================================================================
"""
    print(banner)

def list_sources(store: HealthVectorStore):
    print("\n--- Currently Indexed Sources & Trust Scores ---")
    seen_urls = {}
    for c in store.chunks:
        url = c["source_url"]
        if url not in seen_urls:
            seen_urls[url] = {
                "type": c["source_type"],
                "author": c["author"],
                "trust": c["trust_score"],
                "date": c["published_date"],
                "chunks": 0
            }
        seen_urls[url]["chunks"] += 1

    for idx, (url, info) in enumerate(seen_urls.items(), 1):
        trust_badge = "🌟 HIGH TRUST" if info["trust"] >= 0.7 else ("⚡ MODERATE" if info["trust"] >= 0.4 else "⚠️ CONSUMER BLOG")
        print(f"[{idx}] {info['type'].upper()} ({trust_badge})")
        print(f"    Author: {info['author'] or 'N/A'}")
        print(f"    Trust Score: {info['trust']:.2f} | Chunks: {info['chunks']} | Date: {info['date'] or 'N/A'}")
        print(f"    URL: {url}\n")

def run_cli_interactive():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("\n[ERROR] GEMINI_API_KEY not found in environment or .env file.")
        print("Please ensure GEMINI_API_KEY is configured in .env\n")
        sys.exit(1)

    print("Initializing Vector Index & Trust Store...")
    try:
        vector_store = HealthVectorStore()
        chatbot = HealthRAGChatbot(vector_store=vector_store, min_trust_score=0.0)
    except Exception as e:
        print(f"\n[ERROR] Initialization failed: {e}")
        sys.exit(1)

    print_banner()

    min_trust = 0.0

    while True:
        try:
            prompt_label = f"\n[Trust Filter >= {min_trust:.2f}] Ask GutBut > "
            user_input = input(prompt_label).strip()
            
            if not user_input:
                continue

            # Command routing
            if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
                print("\nGoodbye! Stay healthy. 👋\n")
                break

            if user_input.lower() == "/help":
                print_banner()
                continue

            if user_input.lower() == "/clear":
                chatbot.reset_history()
                print("\n[INFO] Conversation history cleared.")
                continue

            if user_input.lower() == "/sources":
                list_sources(vector_store)
                continue

            if user_input.lower().startswith("/trust"):
                parts = user_input.split()
                if len(parts) > 1:
                    try:
                        val = float(parts[1])
                        if 0.0 <= val <= 1.0:
                            min_trust = val
                            print(f"\n[INFO] Minimum trust score filter set to: {min_trust:.2f}")
                            if min_trust >= 0.8:
                                print("       (Only peer-reviewed scientific studies like PubMed will be retrieved)")
                            elif min_trust >= 0.4:
                                print("       (Peer-reviewed studies and credible medical channels will be retrieved)")
                        else:
                            print("\n[ERROR] Please specify a trust score between 0.0 and 1.0 (e.g. /trust 0.5)")
                    except ValueError:
                        print("\n[ERROR] Invalid number format. Example: /trust 0.5")
                else:
                    print(f"\n[INFO] Current trust score threshold: {min_trust:.2f}")
                continue

            # Regular Question
            print(f"\n🔎 Searching evidence with trust score >= {min_trust:.2f}...")
            result = chatbot.ask(user_input, min_trust_score=min_trust)

            newly_scraped = result.get("newly_scraped", [])
            if newly_scraped:
                print(f"\n✨ [AUTONOMOUS DISCOVERY] Local database had low coverage for this topic.")
                print(f"   Successfully queried PubMed, scraped, and scored {len(newly_scraped)} new medical study:")
                for ns in newly_scraped:
                    print(f"   -> {ns['author']} (Trust: {ns['trust']:.2f}) | {ns['url']}")

            # Display retrieved evidence sources
            sources = result.get("sources", [])
            if sources:
                print("\n📚 Retrieved Evidence:")
                for s_i, src in enumerate(sources, 1):
                    badge = "🌟 High Trust" if src["trust_score"] >= 0.7 else "⚡ General"
                    print(f"   [{s_i}] {src['source_type'].upper()} ({badge}) | Trust: {src['trust_score']:.2f} | Sim: {src['similarity']:.2f}")
                    print(f"       Author: {src['author']} | URL: {src['source_url']}")
            else:
                print("\n⚠️ No evidence found passing the current trust threshold.")

            print("\n🤖 GutBut Assistant Response:")
            print("-" * 65)
            print(result["answer"])
            print("-" * 65)

        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Goodbye! 👋\n")
            break

def main():
    parser = argparse.ArgumentParser(description="GutBut Trust-Aware Health RAG Chatbot")
    parser.add_argument("--query", "-q", type=str, help="Ask a single question and output response")
    parser.add_argument("--min-trust", "-t", type=float, default=0.0, help="Minimum trust score threshold (0.0 to 1.0)")
    parser.add_argument("--list-sources", action="store_true", help="List all ingested sources and exit")
    args = parser.parse_args()

    if args.list_sources:
        store = HealthVectorStore()
        list_sources(store)
        return

    if args.query:
        store = HealthVectorStore()
        bot = HealthRAGChatbot(vector_store=store, min_trust_score=args.min_trust)
        result = bot.ask(args.query)

        newly_scraped = result.get("newly_scraped", [])
        if newly_scraped:
            print(f"\n✨ [AUTONOMOUS DISCOVERY] Local database lacked specific coverage on this topic.")
            print(f"   Successfully queried PubMed, scraped, and scored {len(newly_scraped)} new medical study:")
            for ns in newly_scraped:
                print(f"   -> {ns['author']} (Trust: {ns['trust']:.2f}) | {ns['url']}")

        print("\nAnswer:")
        print(result["answer"])
        print("\nSources:")
        for s in result["sources"]:
            print(f"- {s['source_type']} by {s['author']} (Trust: {s['trust_score']}) -> {s['source_url']}")
        return

    run_cli_interactive()

if __name__ == "__main__":
    main()

