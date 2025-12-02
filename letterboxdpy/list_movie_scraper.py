"""
List Movie Scraper - Scrape movies from a Letterboxd user list and produce the same CSV output
format as `csv_movie_scraper.py`.

Usage:
    python list_movie_scraper.py --author username --list-slug my-list --output out.csv
    python list_movie_scraper.py --url https://letterboxd.com/username/list/slug/ --output out.csv

Or programmatically:
    from letterboxdpy.list_movie_scraper import scrape_movies_from_list
    scrape_movies_from_list(author='maxsuck', list_slug='broforce-movies-ranked', output_csv='out.csv')
"""

import csv
import os
import sys
import re
from collections import Counter
from typing import Dict, Any

from letterboxdpy.list import List as LBList
from letterboxdpy.csv_movie_scraper import scrape_movie_data


def _slug_from_url(url: str) -> (str, str):
    """Parse a Letterboxd list URL and return (username, list_slug)
    Accepts URLs like: https://letterboxd.com/username/list/list-slug/ or variations.
    """
    if not url:
        return None, None
    m = re.search(r"letterboxd\.com/([^/]+)/list/([^/]+)/?", url)
    if m:
        return m.group(1).lower(), m.group(2)
    # try looser parsing
    parts = url.rstrip('/').split('/')
    if len(parts) >= 3 and parts[-3] == 'letterboxd.com':
        return parts[-2].lower(), parts[-1]
    return None, None


def scrape_movies_from_list(
    author: str = None,
    list_slug: str = None,
    url: str = None,
    output_csv: str = 'output.csv',
    verbose: bool = True
) -> None:
    """Scrape movies referenced in a Letterboxd user list and write the same fields
    as produced by `csv_movie_scraper.py`.

    Either provide (author and list_slug) or an absolute list URL via `url`.
    """

    if url and (not author or not list_slug):
        parsed_author, parsed_slug = _slug_from_url(url)
        if not parsed_author or not parsed_slug:
            raise ValueError(f"Could not parse list URL: {url}")
        author = author or parsed_author
        list_slug = list_slug or parsed_slug

    if not author or not list_slug:
        raise ValueError("Author and list_slug (or url) must be provided")

    # instantiate the List object from letterboxdpy
    lb_list = LBList(author, list_slug)
    movies_dict = lb_list.movies  # Expecting a dict-like structure

    # Print collection start message and expected count if available
    if verbose:
        try:
            total_expected = int(getattr(lb_list, 'count', 0) or 0)
        except Exception:
            total_expected = 0
        if total_expected:
            print(f"Collecting movies from list: {author}/{list_slug} (expected {total_expected} entries)")
        else:
            print(f"Collecting movies from list: {author}/{list_slug}...")

    # Extract slugs robustly from the list entries
    slugs = []
    for i, (key, val) in enumerate(movies_dict.items(), 1):
        # val might be a dict with keys like 'slug', 'film', 'url'
        slug = None
        if isinstance(val, dict):
            slug = (val.get('slug') or val.get('film') or val.get('url') or '').strip()
        elif isinstance(val, str):
            slug = val.strip()
        # if slug looks like a URL, take last path segment
        if slug and '/' in slug:
            slug = slug.rstrip('/').split('/')[-1]
        if slug:
            slugs.append(slug)
        # intermittent progress update
        if verbose and i % 100 == 0:
            print(f"Collected {i} entries so far...")



    if not slugs:
        if verbose:
            print("No movie slugs found in the list.")
        return

    slug_counts = Counter(slugs)

    # Define output fieldnames (same as csv_movie_scraper)
    output_fieldnames = ['name', 'slug', 'list_count', 'id', 'poster', 'runtime', 'director', 'users_rating', 'views', 'total_likes', 'genres']

    # Load existing output rows (if any)
    existing_rows: Dict[str, Dict[str, str]] = {}
    if os.path.isfile(output_csv):
        try:
            with open(output_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    slug_val = (row.get('slug') or '').strip()
                    if slug_val:
                        existing_rows[slug_val] = {k: (v if v is not None else '') for k, v in row.items()}
        except Exception as e:
            if verbose:
                print(f"Warning: Could not read existing output file: {e}")

    # Update counts for existing rows
    for s, count in slug_counts.items():
        if s in existing_rows:
            existing_count = 0
            try:
                existing_count = int(existing_rows[s].get('list_count', '0') or 0)
            except Exception:
                existing_count = 0
            existing_rows[s]['list_count'] = str(existing_count + count)

    # Determine which slugs to scrape
    slugs_to_process = [s for s in slug_counts.keys() if s not in existing_rows]

    if verbose:
        print(f"Found {len(slugs)} entries in list, {len(existing_rows)} already in output, {len(slugs_to_process)} unique to process.")

    if not slugs_to_process:
        if verbose:
            print("All movies already scraped!")
        return

    # Scrape each new slug using the existing scrape_movie_data
    for idx, slug in enumerate(slugs_to_process[1000:2000], 1):
        if not slug:
            if verbose:
                print(f"[{idx}/{len(slugs_to_process)}] Skipping empty slug")
            continue

        if verbose:
            print(f"[{idx}/{len(slugs_to_process)}] Scraping: {slug}")

        movie_data = scrape_movie_data(slug)
        movie_data['list_count'] = str(slug_counts.get(slug, 0))
        # normalize to string values
        existing_rows[slug] = {k: (str(movie_data.get(k, '')) if movie_data.get(k, '') is not None else '') for k in output_fieldnames}

    # Write merged output (overwrite)
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_fieldnames)
        writer.writeheader()
        for slug_key, row in existing_rows.items():
            out_row = {k: row.get(k, '') for k in output_fieldnames}
            writer.writerow(out_row)

    if verbose:
        print(f"✓ Scraping complete! Data written to: {output_csv}")


if __name__ == '__main__':
    import argparse

    sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description='Scrape movies from a Letterboxd user list to CSV')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--url', help='Full URL to the Letterboxd list (e.g. https://letterboxd.com/username/list/slug/)')
    group.add_argument('--author', '-a', help='Author (username) of the list; requires --list-slug')
    group.add_argument('--sample', action='store_true', help='Use built-in sample list URL (barnhillkent top-10000)')
    parser.add_argument('--list-slug', '-l', help='List slug (required if --author is used)')
    parser.add_argument('--output', '-o', required=True, help='Path to output CSV file')
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress progress messages')

    args = parser.parse_args()

    try:
        if args.sample:
            sample_url = 'https://letterboxd.com/barnhillkent/list/top-10000-films-of-all-time-1/'
            scrape_movies_from_list(url=sample_url, output_csv=args.output, verbose=not args.quiet)
        elif args.url:
            scrape_movies_from_list(url=args.url, output_csv=args.output, verbose=not args.quiet)
        else:
            if not args.list_slug:
                parser.error('--list-slug is required when using --author')
            scrape_movies_from_list(author=args.author, list_slug=args.list_slug, output_csv=args.output, verbose=not args.quiet)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
