import pandas as pd
import sys
import os
import re
import csv
from typing import List, Dict
from json import dumps as json_dumps, loads as json_loads

def scrape_letterboxd_diary(username: str) -> str:
    try:
        from letterboxdpy.core.encoder import SecretsEncoder
        from letterboxdpy.pages import user_diary
        from letterboxdpy.core.exceptions import PrivateRouteError
    except ImportError as e:
        print(f"Error: Could not import letterboxdpy modules: {e}")
        print("Make sure letterboxdpy is installed and available.")
        sys.exit(1)
    
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

        @property
        def entries(self) -> dict:
            if self._entries is None:
                self._entries = self.get_entries()
            return self._entries

        def get_url(self) -> str:
            return self.pages.diary.url
        
        def get_entries(self) -> dict:
            return self.pages.diary.get_diary()
    
    output_dir = 'output_csv'
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'diary_{username}.csv')
    
    print(f"Fetching diary for username: {username}")
    
    try:
        diary_instance = Diary(username)
        entries = diary_instance.entries
        
        if not entries:
            print("No entries found.")
            sys.exit(1)
        
        if isinstance(entries, dict):
            if 'entries' in entries and isinstance(entries['entries'], dict):
                entries_list = list(entries['entries'].values())
            elif all(isinstance(v, dict) for v in entries.values()):
                entries_list = list(entries.values())
            else:
                possible_lists = [v for v in entries.values() if isinstance(v, list)]
                if possible_lists:
                    entries_list = [item for sublist in possible_lists for item in sublist]
                else:
                    entries_list = []
        elif isinstance(entries, list):
            entries_list = entries
        else:
            entries_list = []
        
        entries_list = [e for e in entries_list if isinstance(e, dict)]
        
        fieldnames = ["name", "slug", "id", "release", "runtime", "rewatched", "rating", "liked", "reviewed", "date"]
        
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for entry in entries_list:
                actions = entry.get('actions', {}) if isinstance(entry.get('actions', {}), dict) else {}
                date_obj = entry.get('date', {}) if isinstance(entry.get('date', {}), dict) else {}
                
                if date_obj and all(k in date_obj and date_obj[k] is not None for k in ('year', 'month', 'day')):
                    try:
                        date_str = f"{int(date_obj['year']):04d}-{int(date_obj['month']):02d}-{int(date_obj['day']):02d}"
                    except Exception:
                        date_str = str(date_obj)
                else:
                    date_str = str(date_obj) if date_obj else ''
                
                row = {
                    'name': entry.get('name', '') or '',
                    'slug': entry.get('slug', '') or '',
                    'id': entry.get('id', '') or '',
                    'release': entry.get('release', '') or '',
                    'runtime': entry.get('runtime', '') or '',
                    'rewatched': actions.get('rewatched', ''),
                    'rating': actions.get('rating', ''),
                    'liked': actions.get('liked', ''),
                    'reviewed': actions.get('reviewed', ''),
                    'date': date_str,
                }
                
                for k, v in row.items():
                    if isinstance(v, bool):
                        row[k] = '1' if v else '0'
                    elif v is None:
                        row[k] = ''
                    else:
                        row[k] = str(v)
                writer.writerow(row)
        
        print(f"Diary saved to: {output_path}")
        return output_path
        
    except PrivateRouteError:
        print(f"Error: User's diary is private.")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to scrape diary: {e}")
        sys.exit(1)


def load_letterboxd_diary(csv_path: str) -> List[Dict]:
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Could not find diary file: {csv_path}")
    
    user_data = []
    
    for _, row in df.iterrows():
        if pd.isna(row.get('name')) or row.get('name') == '':
            continue
            
        rating = row.get('rating', '')
        if pd.isna(rating) or rating == '' or rating == '0':
            continue
        
        entry = {
            'title': str(row['name']),
            'year': int(row['release']) if pd.notna(row.get('release')) and row.get('release') != '' else None,
            'rating': float(rating)
        }
        
        if entry['title'] and entry['rating'] > 0:
            user_data.append(entry)
    
    return user_data


def get_rated_titles(csv_path: str) -> set:
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        return set()
    
    rated = set()
    for _, row in df.iterrows():
        title = row.get('name')
        rating = row.get('rating', '')
        
        if pd.notna(title) and title != '' and pd.notna(rating) and rating != '' and rating != '0':
            rated.add(str(title))
    
    return rated


def generate_recommendations(username: str, 
                            recommendations_csv: str = 'recommendations.csv',
                            n_recommendations: int = 20,
                            diverse: bool = False,
                            skip_scrape: bool = False):
    
    try:
        from recommendation_engine import MovieRecommender
    except ImportError:
        print("Error: Could not import MovieRecommender from recommendation_engine.py")
        print("Make sure recommendation_engine.py is in the same directory.")
        sys.exit(1)
    
    diary_csv_path = f'output_csv/diary_{username}.csv'
    
    if not skip_scrape or not os.path.exists(diary_csv_path):
        diary_csv_path = scrape_letterboxd_diary(username)
    else:
        print(f"Using existing diary: {diary_csv_path}")
    
    try:
        user_data = load_letterboxd_diary(diary_csv_path)
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        sys.exit(1)
    
    if len(user_data) == 0:
        print("\nError: No rated movies found in diary.")
        print("The recommendation engine needs at least some rated movies to work.")
        sys.exit(1)
    
    print(f"Loaded {len(user_data)} rated movies from diary")
    
    rated_titles = get_rated_titles(diary_csv_path)
    print(f"Found {len(rated_titles)} rated movies (will exclude from recommendations)")
    
    try:
        recommender = MovieRecommender(recommendations_csv)
    except FileNotFoundError:
        print(f"\nError: Could not find movie database: {recommendations_csv}")
        print("Make sure recommendations.csv is in the current directory.")
        sys.exit(1)
    
    print(f"\nGenerating personalized recommendations...")
    
    if diverse:
        recommendations = recommender.get_diverse_recommendations(
            user_data,
            n_recommendations=n_recommendations
        )
    else:
        recommendations = recommender.get_recommendations(
            user_data,
            n_recommendations=n_recommendations
        )
    
    def normalize_title(title):
        return title.lower().strip()
    
    rated_normalized = {normalize_title(t) for t in rated_titles}
    recommendations = recommendations[
        ~recommendations['title'].apply(lambda x: normalize_title(x) in rated_normalized)
    ]
    
    print("\n" + "="*80)
    print(f"TOP {n_recommendations} PERSONALIZED RECOMMENDATIONS FOR @{username}")
    print("="*80 + "\n")
    
    for idx, movie in recommendations.head(n_recommendations).iterrows():
        print(f"{idx + 1}. {movie['title']} ({int(movie['release_year'])})")
        print(f"   Genres: {movie['genres']}")
        print(f"   Rating: {movie['vote_average']:.1f}/10 ({int(movie['vote_count'])} votes)")
        print(f"   Runtime: {int(movie['runtime_minutes'])} minutes")
        print(f"   Match Score: {movie['recommendation_score']:.3f}")
        print(f"   TMDb: {movie['tmdb_url']}")
        print()
    
    return recommendations


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate personalized movie recommendations from Letterboxd"
    )
    parser.add_argument(
        'username',
        help="Letterboxd username"
    )
    parser.add_argument(
        '--database',
        help="Path to movie database CSV",
        default='recommendations.csv'
    )
    parser.add_argument(
        '--count', '-n',
        type=int,
        default=20,
        help="Number of recommendations to generate (default: 20)"
    )
    parser.add_argument(
        '--diverse',
        action='store_true',
        help="Use diverse recommendation mode"
    )
    parser.add_argument(
        '--skip-scrape',
        action='store_true',
        help="Skip scraping and use existing diary CSV"
    )
    
    args = parser.parse_args()
    
    generate_recommendations(
        username=args.username,
        recommendations_csv=args.database,
        n_recommendations=args.count,
        diverse=args.diverse,
        skip_scrape=args.skip_scrape
    )