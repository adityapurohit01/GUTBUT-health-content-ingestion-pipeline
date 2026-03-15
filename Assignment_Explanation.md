# The GutBut Data Scraping Assignment: A Layman's Guide

This document explains the entire project in simple terms: **what** we built, **why** we built it this way, and **why** we rejected other possible ways of doing it.

---

## 1. The Big Picture: What is this for?

**The Goal:** Companies like Jetty AI (the creators of GutBut) build Artificial Intelligence assistants for health and wellness. 
For an AI to answer user questions accurately (e.g., "What foods improve gut health?"), it needs to "read" trusted medical information first. However, the AI cannot just "Google" things live—it needs a structured, organized database of knowledge to pull from.

**What we built:** We built the "Knowledge Ingestion Pipeline." This is an automated robot (a scraper) that goes out to the internet, reads articles and videos, grades them to see if they are trustworthy, chops them into bite-sized pieces for the AI to understand, and saves them neatly into a digital filing cabinet (a JSON file).

This process is the absolute foundation of a technology called **RAG (Retrieval-Augmented Generation)**, which is how modern AI chatbots are built.

---

## 2. Task 1: The Scraper (Gathering the Data)

We needed to pull information from three wildly different places: Health Blogs, YouTube Videos, and PubMed (scientific research).

### A. Health Blogs
*   **What we did:** We wrote a program that visits blog URLs (like Healthline or Zoe), grabs the headline, the author, the publication date, and the main article text, while ignoring all the annoying ads, sidebars, and cookie pop-ups.
*   **Alternative Approach:** We *could* have used a "Headless Browser" (like Selenium or Puppeteer). This physically opens a hidden Google Chrome window on the computer, waits for the page to visually load, and clicks around.
*   **Why we didn't do that:** Headless browsers are incredibly slow, use tons of computer memory, and break easily if a website changes its visual layout. Instead, we used lightweight tools (`newspaper3k` and `BeautifulSoup`) to directly read the invisible code (HTML and JSON-LD schema) behind the website. It is 100x faster and much more reliable.

### B. YouTube Videos
*   **What we did:** We used a tool that connects to YouTube's hidden subtitle system to instantly download the English spoken transcript of the video, along with the channel name and upload date.
*   **Alternative Approach:** We *could* have built a system that downloads the actual video file (MP4) and runs audio-recognition AI (like OpenAI's Whisper) to generate text from the audio.
*   **Why we didn't do that:** Downloading video is slow, wastes bandwidth, and running an AI audio-transcription model is extremely expensive and requires heavy graphics cards (GPUs). Grabbing the transcript that YouTube has *already* generated is free, takes less than 1 second, and requires zero heavy hardware.

### C. PubMed (Scientific Papers)
*   **What we did:** We used the official scientific database connection (the NCBI Entrez API) to instantly request the structured data of a medical paper (Title, Authors, Abstract) using its ID number.
*   **Alternative Approach:** We *could* have just scraped the PubMed webpage visually like we did with the blogs.
*   **Why we didn't do that:** Web scraping HTML is always a "hack" when a dedicated API exists. APIs (Application Programming Interfaces) are official, legal backdoors provided by the website to give you exactly the data you want in a perfectly clean format without any webpage junk. 

---

## 3. Task 1b: Processing the Data (Making it AI-Friendly)

Once we had the text, we couldn't just hand the AI a massive 10,000-word essay. We had to process it.

### A. Topic Tagging (Keywords)
*   **What we did:** We used a mathematical tool called `yake` to scan the text and figure out the 5 most important keywords (e.g., "Gut Microbiome", "Digestion").
*   **Alternative Approach:** We *could* have asked ChatGPT or an LLM: "Please summarize the keywords of this text."
*   **Why we didn't do that:** Calling ChatGPT via an API costs money for every single article and takes 3-5 seconds per request. Our mathematical tool runs locally on your laptop for free in 0.01 seconds. 

### B. Chunking (Chopping the text)
*   **What we did:** We chopped long articles into smaller chunks of about 300 words. Crucially, our code ensures a chop *only* happens at the end of a sentence (after a period ".", question mark "?", or exclamation point "!").
*   **Alternative Approach:** The standard beginner way to do this is "Character Slicing"—just chopping the text every 1,000 characters, regardless of what the text says.
*   **Why we didn't do that:** If you chop blindly, you might cut a sentence in half (e.g., "The cure for the disease is... [CHUNK ENDS]"). When the AI tries to read that chunk later, it will be hopelessly confused. Preserving the "semantic boundary" (the sentence) is the hallmark of a professional AI Engineering pipeline.

---

## 4. Task 2: The Trust Score System (Beating Fake News)

The internet is full of fake health advice, SEO spam, and snake oil. If GutBut's AI reads fake advice, it will give users fake advice. We had to build a BS-detector.

*   **What we did:** We built a mathematical grading system (from 0 to 1) based on 5 strict rules:
    1.  **Author:** Is there an author? Do they have "Dr." or "MD" in their name?
    2.  **Domain:** Is this a `.gov` or `.edu` (high trust), or just a random `.com` (low trust)?
    3.  **Citations:** Does the article have references to scientific studies (e.g., `[1]`, `[2]`)?
    4.  **Recency:** Was this written in the last year, or is it 10 years old? Science changes fast.
    5.  **Medical Disclaimer:** Does the site legally state "This is not medical advice"? (Legitimate health sites ALWAYS have this to avoid lawsuits; spam sites usually forget it).

*   **Alternative Approach:** We *could* have sent the whole article to an advanced AI model and asked, "Rate how trustworthy this is from 1 to 10."
*   **Why we didn't do that:** 
    1.  **Cost & Speed:** Again, running an LLM on thousands of articles costs a fortune.
    2.  **Hallucinations:** AI models are gullible. A beautifully written, highly-convincing article about snake oil might trick the AI into giving it a 10/10. 
    3.  **Transparency:** If the AI rates an article a 3/10, we don't know *why*. With our mathematical formula, we can pinpoint exactly why an article failed (e.g., "It failed because it is 8 years old and has no author"). We have full control.

---

## 5. Why so many folders instead of one file?

You might notice the code is split into `scraper/`, `scoring/`, `utils/`, and `main.py`.

*   **Alternative Approach:** Just write one massive file called `script.py` with 500 lines of code.
*   **Why we didn't do that:** In professional software engineering, we follow "Single Responsibility." If YouTube changes its website tomorrow and our YouTube scraper breaks, we only have to open `scraper/youtube_scraper.py`. We don't have to dig through a massive file and risk accidentally breaking the Trust Score logic while fixing YouTube. It makes the code scalable, testable, and professional.

## Summary
We built an automated, highly defensive pipeline that acts as a digital librarian. It finds books (scraping), checks if the author is a fraud (trust scoring), highlights the key themes (tagging), and cuts out the best passages for the AI to read later (chunking). And we did it all using fast, free, and robust techniques without taking lazy shortcuts.
