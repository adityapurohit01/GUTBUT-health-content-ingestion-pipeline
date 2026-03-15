import logging
from typing import Dict, Any
from urllib.parse import urlparse

from Bio import Entrez

class PubMedScraper:
    """Fetches article metadata and abstract from PubMed."""

    def __init__(self, email: str = "researcher@example.com"):
        Entrez.email = email

    def _extract_pmid(self, url: str) -> str:
        path_parts = urlparse(url).path.strip("/").split("/")
        return path_parts[-1] if path_parts else ""

    def scrape(self, url: str) -> Dict[str, Any]:
        pmid = self._extract_pmid(url)
        if not pmid.isdigit():
            return {"source_url": url, "source_type": "pubmed", "author": "", "published_date": "", "raw_text": ""}

        try:
            handle = Entrez.efetch(db="pubmed", id=pmid, retmode="xml")
            records = Entrez.read(handle)
            handle.close()

            if not records or "PubmedArticle" not in records or len(records["PubmedArticle"]) == 0:
                return {"source_url": url, "source_type": "pubmed", "author": "", "published_date": "", "raw_text": ""}

            article = records["PubmedArticle"][0]["MedlineCitation"]["Article"]
            title = str(article.get("ArticleTitle", ""))

            authors = []
            if "AuthorList" in article:
                for a in article["AuthorList"]:
                    last, fore = a.get("LastName", ""), a.get("ForeName", "")
                    if last or fore: authors.append(f"{fore} {last}".strip())
            author_str = ", ".join(authors)

            published_date = ""
            if "ArticleDate" in article and len(article["ArticleDate"]) > 0:
                d = article["ArticleDate"][0]
                y, m, dy = str(d.get("Year","")), str(d.get("Month","01")), str(d.get("Day","01"))
                published_date = f"{y}-{m.zfill(2)}-{dy.zfill(2)}"
            elif "Journal" in article and "JournalIssue" in article["Journal"]:
                ji = article["Journal"]["JournalIssue"]
                if "PubDate" in ji:
                    y = str(ji["PubDate"].get("Year", ""))
                    if y: published_date = f"{y}-01-01"

            abstract = ""
            if "Abstract" in article and "AbstractText" in article["Abstract"]:
                abstract = " ".join([str(t) for t in article["Abstract"]["AbstractText"]])

            return {
                "source_url": url,
                "source_type": "pubmed",
                "author": author_str,
                "published_date": published_date,
                "raw_text": title + ". " + abstract,
            }
        except Exception as e:
            logging.error(f"Error fetching PubMed {pmid}: {e}")
            return {"source_url": url, "source_type": "pubmed", "author": "", "published_date": "", "raw_text": ""}
