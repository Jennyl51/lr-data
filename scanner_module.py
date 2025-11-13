from dotenv import load_dotenv
import os
from firecrawl import Firecrawl
from bs4 import BeautifulSoup
import re

# -----------------------------------
# FIRECRAWL CLIENT
# -----------------------------------
load_dotenv()
api_key = os.getenv("FIRECRAWL_API_KEY")
fc = Firecrawl(api_key=api_key)

# -----------------------------------
# Helper extraction functions
# -----------------------------------
def extract_title(html, md):
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    first_line = md.split("\n")[0].replace("#", "").strip()
    return first_line


def extract_author(md):
    m = re.search(r"By ([A-Za-z ]+)", md)
    return m.group(1).strip() if m else None


def extract_date(md):
    m = re.search(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s*\d{4}",
        md
    )
    return m.group(0) if m else None


def extract_image(html):
    soup = BeautifulSoup(html, "html.parser")
    img = soup.find("img")
    if img and img.get("src"):
        return img["src"]
    return None


# -----------------------------------
# Core crawler function (homepage → extract url of article)
# -----------------------------------
def get_article_urls():
    print("Scraping homepage...")
    home = fc.scrape(
        "https://www.berkeleyscanner.com/",
        formats=["html", "links"]
    )

    article_urls = []
    for link in home.links:
        url = str(link)
        if (
            "https://www.berkeleyscanner.com" in url 
            and re.search(r"/\d{4}/\d{2}/\d{2}/", url)
        ):
            article_urls.append(url)

    article_urls = list(set(article_urls))
    print(f"Found {len(article_urls)} article URLs")
    return article_urls


# -----------------------------------
# Scrape article details
# -----------------------------------
def scrape_article(url):
    try:
        data = fc.scrape(url, formats=["markdown", "html"])
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

    md, html = data.markdown, data.html
    return {
        "url": url,
        "title": extract_title(html, md),
        "author": extract_author(md),
        "published_date": extract_date(md),
        "image_url": extract_image(html),
        "content_markdown": md
    }
