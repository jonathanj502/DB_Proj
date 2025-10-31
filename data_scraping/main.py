#!/usr/bin/env python3
"""
Query Google Books for the top N books from a CSV and write selected fields to a TSV.

Output columns: title, author, publication_year, summary, page_count, language, image_url

Usage:
  python main.py --csv top10k_books.csv --count 1000 --out top1k_gbooks.tsv

Requires: requests (pip install requests)
"""
from __future__ import annotations
import csv
import os
import sys
import time
import argparse
from typing import List, Tuple, Optional

try:
    import requests
    from requests import RequestException
except Exception:
    print("Missing dependency 'requests'. Install with: pip install requests", file=sys.stderr)
    raise

BASE_URL = "https://www.googleapis.com/books/v1/volumes"


def load_top_books(csv_path: str = "top10k_books.csv", count: int = 1000) -> List[Tuple[str, str]]:
    books: List[Tuple[str, str]] = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for i, row in enumerate(reader, start=1):
                if i > count:
                    break
                title = (row.get("bookTitle") or row.get("title") or "").strip()
                author = (row.get("authorName") or row.get("author") or "").strip()
                books.append((title, author))
    except FileNotFoundError:
        print(f"CSV not found: {csv_path}", file=sys.stderr)
    except Exception as e:
        print(f"Error reading CSV {csv_path}: {e}", file=sys.stderr)
    return books


def build_query(title: str, author: str) -> str:
    # Safe quoting for fielded query
    t = title.replace('"', "\"")
    a = author.replace('"', "\"")
    return f'intitle:"{t}" inauthor:"{a}"'


def query_google_books(title: str, author: str, api_key: Optional[str] = None, timeout: float = 10.0) -> Optional[dict]:
    params = {"q": build_query(title, author), "maxResults": 1}
    if api_key:
        params["key"] = api_key
    try:
        resp = requests.get(BASE_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except RequestException:
        return None


def extract_fields(item: Optional[dict]) -> Tuple[str, str, str, str, str, str]:
    # return title, pub_year, summary, page_count, language, image_url
    if not item:
        return ("", "", "", "", "", "")
    info = item.get("volumeInfo", {}) or {}
    title = info.get("title") or ""
    published = info.get("publishedDate") or ""
    pub_year = ""
    if isinstance(published, str) and len(published) >= 4 and published[:4].isdigit():
        pub_year = published[:4]
    summary = info.get("description") or info.get("subtitle") or ""
    page_count = str(info.get("pageCount")) if info.get("pageCount") is not None else ""
    language = info.get("language") or ""
    image_links = info.get("imageLinks") or {}
    image_url = image_links.get("thumbnail") or image_links.get("smallThumbnail") or ""
    authors = ", ".join(info.get("authors") or [])
    return (title, pub_year, summary, page_count, language, image_url), authors


def sanitize_field(s: Optional[str]) -> str:
    if s is None:
        return ""
    return str(s).replace("\t", " ").replace("\n", " ").strip()


def write_tsv(out_path: str, rows: List[dict]):
    headers = ["title", "author", "publication_year", "summary", "page_count", "language", "image_url"]
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(headers)
        for r in rows:
            writer.writerow([
                sanitize_field(r.get("title")),
                sanitize_field(r.get("author")),
                sanitize_field(r.get("publication_year")),
                sanitize_field(r.get("summary")),
                sanitize_field(r.get("page_count")),
                sanitize_field(r.get("language")),
                sanitize_field(r.get("image_url")),
            ])


def run(csv_path: str, count: int, out_path: str, delay: float, api_key: Optional[str]):
    books = load_top_books(csv_path, count)
    if not books:
        print("No books to process.")
        return

    rows = []
    print(f"Querying {len(books)} books from Google Books (delay={delay}s)...")
    for idx, (title, author) in enumerate(books, start=1):
        print(f"[{idx}/{len(books)}] {title} — {author}")
        data = query_google_books(title, author, api_key=api_key)
        item = None
        if data and data.get("items"):
            item = data["items"][0]
        # extract_fields historically returned either ((fields...), authors)
        # or a flat tuple of 7 items. Handle both shapes robustly.
        result = extract_fields(item)
        # normalize to (fields_tuple, authors)
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], (list, tuple)):
            fields, authors = result
        elif isinstance(result, (list, tuple)) and len(result) >= 7:
            fields = tuple(result[:6])
            authors = result[6]
        else:
            # fallback: try to coerce
            try:
                fields = tuple(result)
                authors = ""
            except Exception:
                fields = ("", "", "", "", "", "")
                authors = ""
        ex_title, pub_year, summary, page_count, language, image_url = fields
        rows.append({
            "title": ex_title or title,
            "author": authors or author,
            "publication_year": pub_year,
            "summary": summary,
            "page_count": page_count,
            "language": language,
            "image_url": image_url,
        })
        try:
            time.sleep(delay)
        except KeyboardInterrupt:
            print("Interrupted by user; writing partial results.")
            break

    write_tsv(out_path, rows)
    print(f"Wrote {len(rows)} rows to {out_path}")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Query Google Books for top-N CSV entries and write TSV")
    p.add_argument("--csv", default="top10k_books.csv")
    p.add_argument("--count", type=int, default=1000)
    p.add_argument("--out", default="top1k_gbooks.tsv")
    p.add_argument("--delay", type=float, default=0.25)
    p.add_argument("--key", help="Optional Google API key")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    api_key = args.key or os.environ.get("GOOGLE_BOOKS_API_KEY")
    run(csv_path=args.csv, count=args.count, out_path=args.out, delay=args.delay, api_key=api_key)


if __name__ == "__main__":
    main()
