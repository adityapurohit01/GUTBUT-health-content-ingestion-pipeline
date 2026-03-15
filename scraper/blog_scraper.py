import json
import logging
from typing import Dict, Any

import requests
from bs4 import BeautifulSoup
from newspaper import Article

class BlogScraper:
    """Scrapes health blog articles using newspaper3k + JSON-LD."""

    def _extract_jsonld(self, html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                if script.string:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        data = data[0]
                    return data
            except (json.JSONDecodeError, IndexError):
                continue
        return {}

    def scrape(self, url: str) -> Dict[str, Any]:
        try:
            article = Article(url)
            article.download()
            article.parse()

            title = article.title or ""
            authors = [a for a in article.authors if len(a) < 40 and "reviewed" not in a.lower()]
            author = ", ".join(authors)
            text = article.text or ""
            pub_date = str(article.publish_date)[:10] if article.publish_date else ""

            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=15)
            jsonld = self._extract_jsonld(response.text)

            if not pub_date and jsonld.get("datePublished"):
                pub_date = str(jsonld["datePublished"])[:10]

            if not author and jsonld.get("author"):
                a = jsonld["author"]
                if isinstance(a, dict):
                    author = a.get("name", "")
                elif isinstance(a, list):
                    author = ", ".join([x.get("name", "") for x in a if isinstance(x, dict)])

            if not pub_date:
                soup = BeautifulSoup(response.text, "html.parser")
                for spec in [{"property": "article:published_time"}, {"itemprop": "datePublished"}]:
                    tag = soup.find("meta", spec)
                    if tag and tag.get("content"):
                        pub_date = tag["content"][:10]
                        break
                if not pub_date:
                    time_el = soup.find("time", {"datetime": True})
                    if time_el:
                        pub_date = time_el["datetime"][:10]

            return {
                "source_url": url,
                "source_type": "blog",
                "author": author,
                "published_date": pub_date,
                "raw_text": title + ". " + text,
            }
        except Exception as e:
            logging.error(f"Error scraping blog {url}: {e}")
            return {"source_url": url, "source_type": "blog", "author": "", "published_date": "", "raw_text": ""}
