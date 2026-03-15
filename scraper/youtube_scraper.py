import logging
from typing import Dict, Any
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi

class YouTubeScraper:
    """Scrapes YouTube video transcripts."""

    def _extract_video_id(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.hostname == "youtu.be":
            return parsed.path[1:]
        if parsed.hostname in ("www.youtube.com", "youtube.com"):
            if parsed.path == "/watch":
                return parse_qs(parsed.query).get("v", [""])[0]
        return ""

    def scrape(self, url: str) -> Dict[str, Any]:
        video_id = self._extract_video_id(url)
        if not video_id:
            return {"source_url": url, "source_type": "youtube", "author": "", "published_date": "", "raw_text": ""}

        try:
            api = YouTubeTranscriptApi()
            transcript = api.fetch(video_id)
            transcript_text = " ".join([snippet.text.replace("\n", " ") for snippet in transcript.snippets])

            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")

            author = ""
            author_tag = soup.find("link", itemprop="name")
            if author_tag: author = author_tag.get("content", "")
            if not author: author = "YouTube Channel"

            published_date = ""
            date_tag = soup.find("meta", itemprop="uploadDate") or soup.find("meta", {"itemprop": "datePublished"})
            if date_tag and date_tag.get("content"):
                published_date = date_tag["content"][:10]

            title = ""
            title_tag = soup.find("meta", {"property": "og:title"})
            if title_tag: title = title_tag.get("content", "")

            raw_text = (title + ". " + transcript_text) if title else transcript_text

            return {
                "source_url": url,
                "source_type": "youtube",
                "author": author,
                "published_date": published_date,
                "raw_text": raw_text,
            }
        except Exception as e:
            logging.error(f"Error scraping YouTube {video_id}: {e}")
            return {"source_url": url, "source_type": "youtube", "author": "", "published_date": "", "raw_text": ""}
