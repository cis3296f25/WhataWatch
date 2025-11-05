if __loader__.name == '__main__':
    import sys
    sys.path.append(sys.path[0] + '/..')

import re
import os
import csv
from json import (
    dumps as json_dumps,
    loads as json_loads
)

from letterboxdpy.core.encoder import SecretsEncoder
from letterboxdpy.pages import user_diary
from letterboxdpy.core.exceptions import PrivateRouteError
from letterboxdpy.core.scraper import parse_url
from letterboxdpy.movie import Movie
from letterboxdpy.url import get_stats_url
from letterboxdpy.utils.utils_parser import extract_numeric_text



class Diary:

    class DiaryPages:
        def __init__(self, username: str) -> None:
            self.diary = user_diary.UserDiary(username)

    def __init__(self, username: str) -> None:
        assert re.match("^[A-Za-z0-9_]+$", username), "Invalid author"
        self.username = username
        self.pages = self.DiaryPages(self.username)
        self.url = self.get_url()
        self._entries = None

    # Properties
    @property
    def entries(self) -> dict:
        if self._entries is None:
            self._entries = self.get_entries()
        return self._entries

    # Magic Methods
    def __str__(self) -> str:
        return json_dumps(self, indent=2, cls=SecretsEncoder, secrets=['pages'])

    def jsonify(self) -> dict:
        return json_loads(self.__str__())

    # Data Retrieval Methods
    def get_url(self) -> str:
        return self.pages.diary.url
    def get_entries(self) -> dict:
        return self.pages.diary.get_diary()




def _fetch_poster_for_slug(slug: str) -> str:
    """Fetch the poster image URL for a given film slug using Letterboxd's AJAX poster endpoint.

    Returns the poster URL string or empty string on failure.
    """
    if not slug:
        return ''
    # First try the AJAX poster endpoint
    try:
        poster_ajax = f"https://letterboxd.com/ajax/poster/film/{slug}/std/500x750/"
        poster_page = parse_url(poster_ajax)
        if poster_page and getattr(poster_page, 'img', None):
            srcset = poster_page.img.get('srcset') or poster_page.img.get('src')
            if srcset:
                return srcset.split('?')[0]
    except Exception:
        # ignore and try fallback
        pass

    # Fallback: instantiate Movie and ask for its poster (reads movie profile script)
    try:
        movie = Movie(slug)
        poster = movie.get_poster()
        if poster:
            return poster.split('?')[0]
    except Exception:
        pass

    return ''


def _fetch_stats_for_slug(slug: str) -> dict:
    """Fetch runtime, avg_rating, total_views, total_likes, and genres for a film slug.

    Returns a dict with keys: runtime, avg_rating, total_views, total_likes, genres
    Values are simple scalars or lists; failures return empty/None values.
    """
    out = {
        'runtime': None,
        'avg_rating': None,
        'total_views': None,
        'total_likes': None,
        'genres': None,
    }
    if not slug:
        return out

    # First try to fetch stats via CSI stats endpoint
    try:
        stats_url = get_stats_url(slug)
        stats_dom = parse_url(stats_url)

        # The stats page uses divs with aria-labels like
        # "Watched by 1,419,375 members" and "Liked by 367,289 members".
        # Prefer extracting the numeric value from the aria-label which has full numbers.
        stat_divs = stats_dom.find_all('div', class_=lambda x: x and 'production-statistic' in x)
        for d in stat_divs:
            aria = (d.get('aria-label') or '').strip()
            if not aria:
                # try anchor title fallback
                a = d.find('a')
                aria = (a.get('title') if a else '') or aria
            if not aria:
                continue
            lower = aria.lower()
            if 'watched by' in lower or 'watched' in lower:
                num = extract_numeric_text(aria)
                if num is not None:
                    out['total_views'] = int(num)
            if 'liked by' in lower or 'liked' in lower:
                num = extract_numeric_text(aria)
                if num is not None:
                    out['total_likes'] = int(num)
    except Exception:
        # ignore failures and fallback to Movie
        pass

    # Fallback to Movie class to get runtime, avg rating and genres
    try:
        movie = Movie(slug)
        if out['runtime'] is None:
            out['runtime'] = movie.get_runtime()
        if out['avg_rating'] is None:
            out['avg_rating'] = movie.get_rating()
        if out['genres'] is None:
            genres = movie.get_genres()
            # genres is a list of dicts; convert to comma-separated names
            if isinstance(genres, list):
                out['genres'] = ','.join([g.get('name', '') for g in genres if isinstance(g, dict)])
            else:
                out['genres'] = ''
    except Exception:
        pass

    # Ensure simple scalars
    if isinstance(out.get('genres'), list):
        out['genres'] = ','.join(out['genres'])

    return out


if __name__ == "__main__":
    import argparse
    import sys

    sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description="Fetch a user's diary.")
    parser.add_argument('--user', '-u', help="Username to fetch diary for", required=False)
    parser.add_argument('--debug', action='store_true', help='Print debug info about first diary entry')
    args = parser.parse_args()

    username = args.user or input('Enter username: ').strip()

    while not username:
        username = input('Please enter a valid username: ').strip()

    print(f"Fetching diary for username: {username}")

    try:
        diary_instance = Diary(username)
        print('URL:', diary_instance.url)
        entries = diary_instance.entries
        if args.debug:
            # print a short debug summary of the first entry
            sample = None
            if isinstance(entries, dict) and 'entries' in entries:
                vals = list(entries['entries'].values())
                sample = vals[0] if vals else None
            elif isinstance(entries, dict):
                vals = [v for v in entries.values() if isinstance(v, dict)]
                sample = vals[0] if vals else None
            elif isinstance(entries, list):
                sample = entries[0] if entries else None
            print('DEBUG sample entry:', sample)
        entries = diary_instance.entries
        if entries:
            output_dir = os.path.join(os.path.dirname(__file__), 'output_csv')
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f'diary_{username}.csv')

            # Normalize structure
            if isinstance(entries, dict):
                # Case 1: {'entries': {id: entry, ...}, 'count': N, ...}
                if 'entries' in entries and isinstance(entries['entries'], dict):
                    entries_list = list(entries['entries'].values())
                # Case 2: dict of entries keyed by id: {id: entry, ...}
                elif all(isinstance(v, dict) for v in entries.values()):
                    entries_list = list(entries.values())
                else:
                    # fallback: look for lists inside values
                    possible_lists = [v for v in entries.values() if isinstance(v, list)]
                    if possible_lists:
                        entries_list = [item for sublist in possible_lists for item in sublist]
                    else:
                        entries_list = []
            elif isinstance(entries, list):
                entries_list = entries
            else:
                entries_list = []

            # Filter only dicts
            entries_list = [e for e in entries_list if isinstance(e, dict)]

            # Only keep specified headers and flatten nested fields
            # Include poster URL and extra movie metadata
            fieldnames = [
                "name", "slug", "id", "release",
                "length", "avg_rating", "total_views", "total_likes", "genres",
                "runtime", "poster", "rewatched", "rating", "liked", "reviewed", "date"
            ]
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for entry in entries_list:
                    actions = entry.get('actions', {}) if isinstance(entry.get('actions', {}), dict) else {}
                    date_obj = entry.get('date', {}) if isinstance(entry.get('date', {}), dict) else {}
                    # format date as YYYY-MM-DD if possible
                    if date_obj and all(k in date_obj and date_obj[k] is not None for k in ('year', 'month', 'day')):
                        try:
                            date_str = f"{int(date_obj['year']):04d}-{int(date_obj['month']):02d}-{int(date_obj['day']):02d}"
                        except Exception:
                            date_str = str(date_obj)
                    else:
                        date_str = str(date_obj) if date_obj else ''

                    # Fetch poster and additional stats/metadata
                    slug = entry.get('slug', '') or ''
                    if not entry.get('poster'):
                        try:
                            entry['poster'] = _fetch_poster_for_slug(slug)
                        except Exception:
                            entry['poster'] = entry.get('poster', '') or ''

                    stats = _fetch_stats_for_slug(slug)

                    # length: human readable runtime, use runtime if available
                    length = stats.get('runtime') or entry.get('runtime') or ''
                    avg_rating = stats.get('avg_rating') if stats.get('avg_rating') is not None else actions.get('rating', '')

                    row = {
                        'name': entry.get('name', '') or '',
                        'slug': slug,
                        'id': entry.get('id', '') or '',
                        'release': entry.get('release', '') or '',
                        'length': length or '',
                        'avg_rating': avg_rating or '',
                        'total_views': stats.get('total_views') or '',
                        'total_likes': stats.get('total_likes') or '',
                        'genres': stats.get('genres') or '',
                        'runtime': entry.get('runtime', '') or '',
                        'poster': entry.get('poster', '') or '',
                        'rewatched': actions.get('rewatched', ''),
                        'rating': actions.get('rating', ''),
                        'liked': actions.get('liked', ''),
                        'reviewed': actions.get('reviewed', ''),
                        'date': date_str,
                    }
                    # Ensure all values are simple scalars for CSV
                    for k, v in row.items():
                        if isinstance(v, bool):
                            row[k] = '1' if v else '0'
                        elif v is None:
                            row[k] = ''
                        else:
                            row[k] = str(v)
                    writer.writerow(row)
            print(f" Diary saved to: {output_path}")
        else:
            print(" No entries found.")
    except PrivateRouteError:
        print(f"Error: User's diary is private.")
    except Exception as e:
        print(f" Failed to save diary to CSV: {e}")
        print(f" Failed to save diary to CSV: {e}")
