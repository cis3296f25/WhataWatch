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
    data = {
        'director': '',
        'runtime': '',
        'rating': '',
        'views': '',
        'genres': ''
    }
    
    try:
        movie = Movie(slug)
        
        # Get runtime
        runtime = movie.get_runtime()
        data['runtime'] = str(runtime) if runtime else ''
        
        # Get average rating
        rating = movie.get_rating()
        data['rating'] = str(rating) if rating else ''
        
        # Get genres as comma-separated string
        genres_list = movie.get_genres()
        if isinstance(genres_list, list) and genres_list:
            genre_names = []
            for genre in genres_list:
                if isinstance(genre, dict):
                    genre_names.append(genre.get('name', ''))
                elif isinstance(genre, str):
                    genre_names.append(genre)
            data['genres'] = ','.join(filter(None, genre_names))
        
        # Get director from crew - try multiple approaches
        director = None
        try:
            crew = movie.get_crew()
            if isinstance(crew, dict):
                # Try 'directors' key first
                directors = crew.get('directors', [])
                if not directors:
                    # Try 'director' (singular)
                    directors = crew.get('director', [])
                
                if isinstance(directors, list) and directors:
                    director_names = []
                    for director_item in directors:
                        if isinstance(director_item, dict):
                            # Try 'name' or other common keys
                            name = director_item.get('name') or director_item.get('title') or str(director_item)
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
        
        # Get watchers/views stats
        try:
            watchers_stats = movie.get_watchers_stats()
            if isinstance(watchers_stats, dict):
                # Look for 'watched by' key which contains view count
                for key in watchers_stats.keys():
                    if 'watched' in key.lower():
                        data['views'] = str(watchers_stats[key])
                        break
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
    
    # Define output fieldnames: original fields + new enriched fields
    output_fieldnames = list(reader.fieldnames) + ['director', 'runtime', 'rating', 'views', 'genres']
    
    # Load already-scraped slugs from output file
    already_scraped: Set[str] = set()
    if os.path.isfile(output_csv):
        try:
            with open(output_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    slug = (row.get(slug_column) or '').strip()
                    if slug:
                        already_scraped.add(slug)
        except Exception as e:
            if verbose:
                print(f"Warning: Could not read existing output file: {e}")
    
    # Filter rows to only those not already scraped
    rows_to_process = [r for r in rows if (r.get(slug_column) or '').strip() not in already_scraped]
    
    if verbose:
        print(f"Found {len(rows)} movies total, {len(already_scraped)} already scraped, {len(rows_to_process)} to process.")
    
    if not rows_to_process:
        if verbose:
            print("All movies already scraped!")
        return
    
    # Scrape data and append to output CSV
    file_exists = os.path.isfile(output_csv)
    
    with open(output_csv, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_fieldnames)
        
        # Write header only if file is new
        if not file_exists:
            writer.writeheader()
        
        for idx, row in enumerate(rows_to_process, 1):
            slug = (row.get(slug_column) or '').strip()
            
            if not slug:
                if verbose:
                    print(f"[{idx}/{len(rows_to_process)}] Skipping row with empty slug")
                continue
            
            if verbose:
                print(f"[{idx}/{len(rows_to_process)}] Scraping: {slug}")
            
            # Scrape movie data
            movie_data = scrape_movie_data(slug)
            
            # Merge original row with new data
            enriched_row = {**row, **movie_data}
            writer.writerow(enriched_row)
    
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
