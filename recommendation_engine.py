#!/usr/bin/env python

import pandas as pd
import numpy as np
from collections import Counter, defaultdict
import re


class MovieRecommender:
    COL_NAME = 'name'
    COL_YEAR = 'year'
    COL_LENGTH = 'length'
    COL_RATING = 'ratings'
    COL_GENRES = 'genres'
    COL_POPULARITY = 'total_likes'
    COL_POSTER = 'poster_url'

    def __init__(self, csv_path='movies.csv'):
        self.movies_df = pd.read_csv(csv_path, dtype={self.COL_NAME: str})
        self._preprocess_data()

    def _normalize_name(self, name: str) -> str:
        if pd.isna(name):
            return ''
        # collapse whitespace, remove punctuation, lowercase
        s = re.sub(r'[^\w\s]', '', str(name).lower().strip())
        s = re.sub(r'\s+', ' ', s)
        return s

    def _split_genres(self, g):
        if pd.isna(g):
            return []
        parts = [p.strip() for p in str(g).split(',')]
        # filter out empties and normalize casing
        parts = [p for p in parts if p]
        return parts

    def _preprocess_data(self):
        for c in [self.COL_NAME, self.COL_GENRES]:
            if c not in self.movies_df.columns:
                self.movies_df[c] = None

        # Split genres into lists and set
        self.movies_df['genre_list'] = self.movies_df[self.COL_GENRES].apply(self._split_genres)
        self.movies_df['genre_set'] = self.movies_df['genre_list'].apply(set)

        # Normalize names for matching
        self.movies_df['name_normalized'] = self.movies_df[self.COL_NAME].apply(self._normalize_name)

        # Fill numeric columns with sensible defaults
        for col in [self.COL_RATING, self.COL_YEAR, self.COL_LENGTH, self.COL_POPULARITY]:
            if col not in self.movies_df.columns:
                self.movies_df[col] = np.nan

        # Coerce numeric types
        self.movies_df[self.COL_RATING] = pd.to_numeric(self.movies_df[self.COL_RATING], errors='coerce')
        self.movies_df[self.COL_YEAR] = pd.to_numeric(self.movies_df[self.COL_YEAR], errors='coerce')
        self.movies_df[self.COL_LENGTH] = pd.to_numeric(self.movies_df[self.COL_LENGTH], errors='coerce')
        self.movies_df[self.COL_POPULARITY] = pd.to_numeric(self.movies_df[self.COL_POPULARITY], errors='coerce').fillna(0)

        # Fill missing genre_list with empty lists (already handled) and fill missing strings
        self.movies_df[self.COL_NAME] = self.movies_df[self.COL_NAME].fillna('')
        self.movies_df[self.COL_POSTER] = self.movies_df.get(self.COL_POSTER, '').fillna('')

    def match_letterboxd_movies(self, letterboxd_data):
        '''
        letterboxd_data: list of dicts: {'name':..., 'year':..., 'ratings': ...}
        returns DataFrame of matched movies with letterboxd ratings saved in column 'user_rating'
        '''
        matched = []
        for entry in letterboxd_data:
            name = entry.get('name', '')
            year = entry.get('year')
            user_rating = entry.get('ratings', np.nan)  # Letterboxd uses 0.5-5.0

            norm = self._normalize_name(name)
            matches = self.movies_df[self.movies_df['name_normalized'] == norm]

            # if multiple, try year
            if len(matches) > 1 and year:
                year_matches = matches[matches[self.COL_YEAR] == year]
                if len(year_matches) > 0:
                    matches = year_matches

            if len(matches) > 0:
                # copy series and attach user's rating
                row = matches.iloc[0].copy()
                row['user_rating'] = float(user_rating) if not pd.isna(user_rating) else np.nan
                matched.append(row)

        if not matched:
            return pd.DataFrame(columns=list(self.movies_df.columns) + ['user_rating'])

        return pd.DataFrame(matched)

    def analyze_user_preferences(self, user_movies_df):
        '''
        From matched user movies, derive preferences:
          - average rating per genre (weighted by user's rating)
          - overall avg rating, year and runtime preferences
          - top genres among high-rated movies
        '''
        prefs = {}
        genre_scores = defaultdict(float)
        genre_counts = defaultdict(int)

        # If user didn't give explicit user_rating, fallback to movie's rating
        if 'user_rating' not in user_movies_df.columns:
            user_movies_df['user_rating'] = user_movies_df[self.COL_RATING]

        user_movies_df['user_rating'] = pd.to_numeric(user_movies_df['user_rating'], errors='coerce').fillna(0)

        for _, r in user_movies_df.iterrows():
            u_r = float(r.get('user_rating', 0) or 0)
            genres = r.get('genre_list') or []
            for g in genres:
                genre_scores[g] += u_r
                genre_counts[g] += 1

        # Average rating per genre
        genre_preferences = {}
        for g in genre_scores:
            genre_preferences[g] = genre_scores[g] / max(genre_counts[g], 1)

        # Sort genres by preference
        prefs['genres'] = dict(sorted(genre_preferences.items(), key=lambda kv: kv[1], reverse=True))

        # overall user stats
        prefs['avg_ratings'] = float(user_movies_df['user_rating'].mean()) if len(user_movies_df) > 0 else 0.0
        prefs['ratings_std'] = float(user_movies_df['user_rating'].std(ddof=0)) if len(user_movies_df) > 1 else 0.0

        prefs['avg_year'] = float(user_movies_df[self.COL_YEAR].mean()) if len(user_movies_df) > 0 else np.nan
        prefs['year_std'] = float(user_movies_df[self.COL_YEAR].std(ddof=0)) if len(user_movies_df) > 1 else 0.0

        prefs['avg_runtime'] = float(user_movies_df[self.COL_LENGTH].mean()) if len(user_movies_df) > 0 else np.nan
        prefs['runtime_std'] = float(user_movies_df[self.COL_LENGTH].std(ddof=0)) if len(user_movies_df) > 1 else 0.0

        # Top genres among movies the user really liked (>=4.0 on 0-5 scale)
        high_rated = user_movies_df[user_movies_df['user_rating'] >= 4.0]
        if len(high_rated) > 0:
            all_genres = [g for genres in high_rated['genre_list'] for g in genres]
            prefs['high_rated_genres'] = [g for g, _ in Counter(all_genres).most_common(5)]
        else:
            prefs['high_rated_genres'] = []

        return prefs

    def calculate_similarity_score(self, movie_row, prefs, watched_normalized_names):
        '''
        movie_row: pandas Series representing a candidate movie
        prefs: preferences dict from analyze_user_preferences
        watched_normalized_names: set of normalized movie names the user has already watched
        returns float score, higher is better. If already watched returns -1
        '''

        name_norm = self._normalize_name(movie_row.get(self.COL_NAME, ''))
        if name_norm in watched_normalized_names:
            return -1.0

        score = 0.0

        # Genre matching (40%)
        movie_genres = set(movie_row.get('genre_list') or [])
        if len(movie_genres) > 0 and prefs['genres']:
            # average of user's avg ratings for matched genres (on 0-5 scale)
            matched_scores = [prefs['genres'].get(g, 0) for g in movie_genres]
            if matched_scores:
                genre_component = (sum(matched_scores) / len(matched_scores)) / 5.0  # normalize to 0-1
                score += genre_component * 0.40

        # High-rated genre bonus (10%)
        if prefs.get('high_rated_genres'):
            high_matches = len(movie_genres.intersection(set(prefs['high_rated_genres'])))
            high_ratio = high_matches / max(len(prefs['high_rated_genres']), 1)
            score += high_ratio * 0.10

        # Movie's own average rating (20%) - ratings column is 0-5, normalize to 0-1
        movie_rating = float(movie_row.get(self.COL_RATING) or 0.0)
        score += (movie_rating / 5.0) * 0.20

        # Popularity (10%) - using total_likes / total_views or fallback; log-scaled
        pop = float(movie_row.get(self.COL_POPULARITY) or 0.0)
        if pop > 0:
            pop_score = min(np.log10(pop + 1) / 5.0, 1.0)  # scale so 100k likes ~ 1.0
            score += pop_score * 0.10

        # Year proximity (10%)
        avg_year = prefs.get('avg_year')
        year_std = prefs.get('year_std', 0.0) or 0.0
        movie_year = movie_row.get(self.COL_YEAR)
        if not pd.isna(avg_year) and not pd.isna(movie_year):
            denom = (year_std * 2.0) + 1.0
            year_diff = abs(float(movie_year) - float(avg_year))
            year_score = max(0.0, 1.0 - (year_diff / denom))
            score += year_score * 0.10

        # Runtime proximity (10%)
        avg_runtime = prefs.get('avg_runtime')
        runtime_std = prefs.get('runtime_std', 0.0) or 0.0
        movie_runtime = movie_row.get(self.COL_LENGTH)
        if not pd.isna(avg_runtime) and not pd.isna(movie_runtime):
            denom_rt = (runtime_std * 2.0) + 10.0  # add 10 min tolerance baseline
            runtime_diff = abs(float(movie_runtime) - float(avg_runtime))
            runtime_score = max(0.0, 1.0 - (runtime_diff / denom_rt))
            score += runtime_score * 0.10

        return float(score)

    def get_recommendations(self, letterboxd_data, n_recommendations=20, min_popularity=1000):
        '''
        Returns top n_recommendations as DataFrame with relevant columns:
        name, year, genre_list, length, ratings, total_likes, poster_url, recommendation_score
        '''
        user_movies = self.match_letterboxd_movies(letterboxd_data)
        if len(user_movies) == 0:
            raise ValueError('No movies could be matched from Letterboxd data.')

        prefs = self.analyze_user_preferences(user_movies)

        # set of normalized watched names to exclude
        watched_norm = set(user_movies['name_normalized'].values)

        # Candidates: require at least min_popularity (total_likes / total_views)
        candidates = self.movies_df[self.movies_df[self.COL_POPULARITY] >= min_popularity].copy()

        # compute score column
        candidates['recommendation_score'] = candidates.apply(
            lambda row: self.calculate_similarity_score(row, prefs, watched_norm), axis=1
        )

        # filter out negative scores (already watched or poor match)
        candidates = candidates[candidates['recommendation_score'] > 0].copy()

        if candidates.empty:
            return pd.DataFrame(columns=[
                self.COL_NAME, self.COL_YEAR, 'genre_list', self.COL_LENGTH,
                self.COL_RATING, self.COL_POPULARITY, self.COL_POSTER, 'recommendation_score'
            ])

        # select top
        top = candidates.nlargest(n_recommendations, 'recommendation_score')

        # keep friendly output columns
        out = top[[
            self.COL_NAME, self.COL_YEAR, 'genre_list', self.COL_LENGTH,
            self.COL_RATING, self.COL_POPULARITY, self.COL_POSTER, 'recommendation_score'
        ]].reset_index(drop=True)

        return out

    def get_diverse_recommendations(self, letterboxd_data, n_recommendations=20, diversity_factor=0.35):
        '''
        Diversify the recommendations.
        diversity_factor in [0,1] controls how much exploration.
        '''
        # request more candidates and then sample
        pool = self.get_recommendations(letterboxd_data, n_recommendations=int(n_recommendations * 3 / (1 - diversity_factor + 1e-9)), min_popularity=50)
        if pool.empty:
            return pool

        n_safe = int(n_recommendations * (1 - diversity_factor))
        n_explore = n_recommendations - n_safe

        safe = pool.head(n_safe)

        rest = pool.iloc[n_safe:].copy()
        if len(rest) == 0:
            return safe.head(n_recommendations)

        # weighting by sqrt(score) for exploration
        scores = rest['recommendation_score'].clip(lower=0).astype(float)
        weights = (scores ** 0.5)
        weights_sum = weights.sum()
        if weights_sum <= 0:
            chosen = rest.sample(n=min(n_explore, len(rest)), replace=False)
        else:
            probs = weights / weights_sum
            chosen_idx = np.random.choice(rest.index, size=min(n_explore, len(rest)), replace=False, p=probs)
            chosen = rest.loc[chosen_idx]

        result = pd.concat([safe, chosen], ignore_index=True).head(n_recommendations)
        return result.reset_index(drop=True)


if __name__ == '__main__':
    recommender = MovieRecommender('movies.csv')

    example_user_data = [
        {'name': 'Gladiator', 'year': 2000, 'ratings': 5.0},
        {'name': 'Interstellar', 'year': 2014, 'ratings': 5.0},
        {'name': 'American Gangster', 'year': 2007, 'ratings': 5.0},
        {'name': 'Inglourious Basterds', 'year': 2009, 'ratings': 5.0},
        {'name': 'Kingdom of Heaven', 'year': 2005, 'ratings': 4.0},
    ]

    try:
        recs = recommender.get_recommendations(example_user_data, n_recommendations=10, min_popularity=100)
        print('\n=== TOP RECOMMENDATIONS ===')
        for idx, row in recs.iterrows():
            genres = ', '.join(row['genre_list']) if isinstance(row['genre_list'], (list, tuple)) else row['genre_list']
            print(f'{idx + 1}. {row[recommender.COL_NAME]} ({int(row[recommender.COL_YEAR]) if not pd.isna(row[recommender.COL_YEAR]) else 'N/A'})')
            print(f'    Genres: {genres}')
            print(f'    Rating: {row[recommender.COL_RATING]:.2f}/5')
            print(f'    Popularity: {int(row[recommender.COL_POPULARITY])}')
            print(f'    Score: {row['recommendation_score']:.4f}\n')

    except ValueError as e:
        print('Error:', e)
