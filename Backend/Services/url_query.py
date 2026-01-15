"""
Service for scraping content from URLs.

This module provides functionality to fetch web pages, extract visible text,
and save the content to local files for ingestion.
"""
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re


def scrape_and_save_website(url: str, datastore_folder: Path) -> str:
    """
    Scrape visible text from a website and save it into the provided datastore folder.

    Args:
        url (str): Website URL to scrape
        datastore_folder (Path): Path to the datastore folder where file will be saved

    Returns:
        str: Path to the saved .txt file
    """

    # 1. Fetch website content
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # 2. Remove unwanted tags
    for tag in soup(["script", "style", "noscript", "iframe", "header", "footer", "nav", "form"]):
        tag.extract()

    # 3. Extract visible text
    text = " ".join(soup.stripped_strings)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        raise ValueError(f"No readable text found on {url}")

    # 4. Ensure datastore folder exists
    datastore_folder.mkdir(parents=True, exist_ok=True)

    # 5. Generate safe filename from URL
    safe_name = re.sub(r"[^a-zA-Z0-9]", "_", url)[:100]  # avoid very long names
    file_path = datastore_folder / f"{safe_name}.txt"

    # 6. Save to file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)

    return str(file_path)
