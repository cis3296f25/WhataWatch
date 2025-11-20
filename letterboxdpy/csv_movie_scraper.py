"""
CSV Movie Scraper - Reads a CSV file with Letterboxd movie slugs and scrapes detailed movie data.

This module takes a CSV file as input (must contain a 'slug' column) and scrapes:
- Director information
- Movie length (runtime)
- Average user rating
- Total user view count
- Genres

All data is written to a single shared output CSV file. The script checks if movies are already
logged in the output file and skips them to allow resumable scraping.

Usage:
    python csv_movie_scraper.py --input path/to/input.csv --output path/to/output.csv
    
    Or programmatically:
    from letterboxdpy.csv_movie_scraper import scrape_movies_from_csv
    scrape_movies_from_csv('input.csv', 'output.csv')
"""

import csv
import os
import sys
from typing import Optional, Dict, List, Any, Set

from letterboxdpy.movie import Movie
from letterboxdpy.core.exceptions import PrivateRouteError


def scrape_movie_data(slug: str) -> Dict[str, Any]:
    """
    Scrape detailed movie data from a single Letterboxd movie slug.
    
    Args:
        slug: The Letterboxd movie slug (e.g., 'inception', 'v-for-vendetta')
        
    Returns:
        Dictionary with keys: director, runtime, rating, views, genres
        Values are strings suitable for CSV output.
    """
    # Return the exact fields required for the output CSV
    data = {
        'name': '',
        'slug': slug,
        'id': '',
        'poster': '',
        'runtime': '',
        'director': '',
        'users_rating': '',
        'views': '',
        'total_likes': '',
        'genres': ''
    }
    
    try:
        movie = Movie(slug)

        # Basic fields
        name = movie.get_title()
        movie_id = movie.get_id()
        poster = movie.get_poster()
        runtime = movie.get_runtime()
        users_rating = movie.get_rating()

        data['name'] = name or ''
        data['id'] = str(movie_id) if movie_id else ''
        data['poster'] = poster or ''
        data['runtime'] = str(runtime) if runtime else ''
        data['users_rating'] = str(users_rating) if users_rating is not None else ''

        # Genres
        genres_list = movie.get_genres()
        if isinstance(genres_list, list) and genres_list:
            genre_names = []
            for genre in genres_list:
                if isinstance(genre, dict):
                    genre_names.append(genre.get('name', ''))
                elif isinstance(genre, str):
                    genre_names.append(genre)
            data['genres'] = ','.join(filter(None, genre_names))

        # Director(s)
        director = None
        try:
            crew = movie.get_crew()
            if isinstance(crew, dict):
                directors = crew.get('directors') or crew.get('director') or []
                if isinstance(directors, list) and directors:
                    director_names = []
                    for director_item in directors:
                        if isinstance(director_item, dict):
                            name = director_item.get('name') or director_item.get('title')
                            if name:
                                director_names.append(name)
                        elif isinstance(director_item, str):
                            director_names.append(director_item)
                    if director_names:
                        director = ','.join(filter(None, director_names))
        except Exception:
            pass

        if director:
            data['director'] = director

        # Watchers / members stats -> views and total_likes
        try:
            watchers_stats = movie.get_watchers_stats()
            if isinstance(watchers_stats, dict):
                # collect numeric candidates and likes separately
                views_candidates = []
                for key, val in watchers_stats.items():
                    try:
                        # val should already be an int from extract_numeric_text
                        if isinstance(val, int):
                            views_candidates.append(val)
                        else:
                            # try to coerce numeric-like strings
                            v = int(str(val))
                            views_candidates.append(v)
                    except Exception:
                        pass

                    kl = key.lower()
                    if 'like' in kl or 'liked' in kl:
                        data['total_likes'] = str(val)

                # prefer the largest numeric watcher stat as total views (best-effort)
                if views_candidates:
                    data['views'] = str(max(views_candidates))
        except Exception:
            pass
        
    except PrivateRouteError:
        pass
    except Exception:
        pass
    
    return data


def scrape_movies_from_csv(
    input_csv: str,
    output_csv: str,
    slug_column: str = 'slug',
    verbose: bool = True
) -> None:
    """
    Read a CSV file with movie slugs and scrape enriched movie data to a single shared output file.
    
    Checks if movies are already in the output file and skips them for resumable scraping.
    
    Args:
        input_csv: Path to input CSV file (must contain a slug column)
        output_csv: Path to output CSV file (shared/single file)
        slug_column: Name of the column containing movie slugs (default: 'slug')
        verbose: Print progress messages (default: True)
        
    Raises:
        FileNotFoundError: If input CSV file does not exist
        ValueError: If slug_column is not found in input CSV headers
    """
    
    if not os.path.isfile(input_csv):
        raise FileNotFoundError(f"Input CSV file not found: {input_csv}")
    
    # Read input CSV
    rows = []
    with open(input_csv, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        if not reader.fieldnames:
            raise ValueError("Input CSV has no headers")
        
        if slug_column not in reader.fieldnames:
            raise ValueError(f"Column '{slug_column}' not found in input CSV. Available columns: {reader.fieldnames}")
        
        rows = list(reader)
    
    # Define output fieldnames (fixed): only keep the requested columns
    # Add `list_count` so the output is aggregated per-slug rather than repeated per input row
    output_fieldnames = ['name', 'slug', 'list_count', 'id', 'poster', 'runtime', 'director', 'users_rating', 'views', 'total_likes', 'genres']
    
    # Load existing output rows (if any) so we can merge/update rather than duplicate
    existing_rows: Dict[str, Dict[str, str]] = {}
    if os.path.isfile(output_csv):
        try:
            with open(output_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    slug_val = (row.get(slug_column) or row.get('slug') or '').strip()
                    if slug_val:
                        # normalize row values to strings
                        existing_rows[slug_val] = {k: (v if v is not None else '') for k, v in row.items()}
        except Exception as e:
            if verbose:
                print(f"Warning: Could not read existing output file: {e}")
    
    # Count occurrences per slug in the input (so we can aggregate rather than produce per-entry rows)
    from collections import Counter
    slug_counts = Counter()
    for r in rows:
        s = (r.get(slug_column) or '').strip()
        if s:
            slug_counts[s] += 1

    # Filter slugs to only those not already present in existing output
    slugs_to_process = [s for s in slug_counts.keys() if s not in existing_rows]
    
    if verbose:
        print(f"Found {len(rows)} movies total, {len(existing_rows)} already in output, {len(slugs_to_process)} unique to process.")

    if not slugs_to_process:
        if verbose:
            print("All movies already scraped!")
        return
    
    # Merge: update counts for existing rows and scrape only new slugs
    # Update existing rows' list_count by adding occurrences from this input
    for s, count in slug_counts.items():
        if s in existing_rows:
            existing_count = 0
            try:
                existing_count = int(existing_rows[s].get('list_count', '0') or 0)
            except Exception:
                existing_count = 0
            existing_rows[s]['list_count'] = str(existing_count + count)

    # Scrape new slugs and add to existing_rows
    for idx, slug in enumerate(slugs_to_process, 1):
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

    # Write merged output (overwrite) so file stays de-duplicated and counts are up-to-date
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_fieldnames)
        writer.writeheader()
        for slug_key, row in existing_rows.items():
            # Ensure we write only the expected columns in order
            out_row = {k: row.get(k, '') for k in output_fieldnames}
            writer.writerow(out_row)
    
    if verbose:
        print(f"✓ Scraping complete! Data appended to: {output_csv}")



if __name__ == "__main__":
    import argparse
    
    sys.stdout.reconfigure(encoding='utf-8')
    
    parser = argparse.ArgumentParser(
        description="Scrape Letterboxd movie data from CSV file with movie slugs."
    )
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Path to input CSV file (must contain a slug column)'
    )
    parser.add_argument(
        '--output', '-o',
        required=True,
        help='Path to output CSV file'
    )
    parser.add_argument(
        '--slug-column',
        default='slug',
        help='Name of the column containing movie slugs (default: slug)'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress progress messages'
    )
    
    args = parser.parse_args()
    
    try:
        scrape_movies_from_csv(
            input_csv=args.input,
            output_csv=args.output,
            slug_column=args.slug_column,
            verbose=not args.quiet
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
