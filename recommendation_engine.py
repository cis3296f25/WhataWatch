"""
WhataWatch Movie Recommendation Engine
Generates personalized movie recommendations based on Letterboxd user data
"""

import pandas as pd
import numpy as np
from collections import Counter, defaultdict
from typing import List, Dict, Tuple
import re


class MovieRecommender:
    def __init__(self, csv_path: str = 'recommendations.csv'):  #Initialize  recommender
        self.movies_df = pd.read_csv(csv_path)
        self._preprocess_data()
        
    def _preprocess_data(self):
         # Split genres into lists
        self.movies_df['genre_list'] = self.movies_df['genres'].apply(
            lambda x: x.split('|') if pd.notna(x) else []
        )
        
        # Create genre mapping for each movie
        self.movies_df['genre_set'] = self.movies_df['genre_list'].apply(set)
        
        # Normalize titles for matching
        self.movies_df['title_normalized'] = self.movies_df['title'].apply(
            lambda x: self._normalize_title(x)
        )
        
    def _normalize_title(self, title: str) -> str:
        if pd.isna(title):
            return ""
        # Remove special characters, convert to lowercase
        return re.sub(r'[^\w\s]', '', title.lower().strip())
    
    def match_letterboxd_movies(self, letterboxd_data: List[Dict]) -> pd.DataFrame:
        
        #Match Letterboxd user data with movies in our database

        
        matched_movies = []
        
        for entry in letterboxd_data:
            title = entry.get('title', '')
            year = entry.get('year')
            rating = entry.get('rating', 0)  # Letterboxd uses 0.5-5.0 scale
            
            # Normalize the title
            norm_title = self._normalize_title(title)
            
            # Try to find match in database
            matches = self.movies_df[
                self.movies_df['title_normalized'] == norm_title
            ]
            
            # If multiple matches, use year to distinguish
            if len(matches) > 1 and year:
                year_matches = matches[matches['release_year'] == year]
                if len(year_matches) > 0:
                    matches = year_matches
            
            # Take the first match if found
            if len(matches) > 0:
                movie = matches.iloc[0].copy()
                movie['user_rating'] = rating
                matched_movies.append(movie)
        
        return pd.DataFrame(matched_movies)
    
    def analyze_user_preferences(self, user_movies: pd.DataFrame) -> Dict:
        #Analyze users preferences based on rated movies.
        preferences = {}
        
        # Genre preferences (weighted by rating)
        genre_scores = defaultdict(float)
        genre_counts = defaultdict(int)
        
        for _, movie in user_movies.iterrows():
            rating = movie.get('user_rating', 0)
            genres = movie.get('genre_list', [])
            
            for genre in genres:
                genre_scores[genre] += rating
                genre_counts[genre] += 1
        
        # Calculate average rating per genre
        genre_preferences = {
            genre: genre_scores[genre] / genre_counts[genre]
            for genre in genre_scores
        }
        preferences['genres'] = dict(sorted(
            genre_preferences.items(), 
            key=lambda x: x[1], 
            reverse=True
        ))
        
        # Average rating given by user
        preferences['avg_rating'] = user_movies['user_rating'].mean()
        preferences['rating_std'] = user_movies['user_rating'].std()
        
        # Year preferences
        preferences['avg_year'] = user_movies['release_year'].mean()
        preferences['year_std'] = user_movies['release_year'].std()
        
        # Runtime preferences
        preferences['avg_runtime'] = user_movies['runtime_minutes'].mean()
        preferences['runtime_std'] = user_movies['runtime_minutes'].std()
        
        # High-rated movies (4+ stars)
        high_rated = user_movies[user_movies['user_rating'] >= 4.0]
        preferences['high_rated_genres'] = []
        if len(high_rated) > 0:
            all_genres = [g for genres in high_rated['genre_list'] for g in genres]
            preferences['high_rated_genres'] = [
                g[0] for g in Counter(all_genres).most_common(5)
            ]
        
        return preferences
    
    def calculate_similarity_score(self, movie: pd.Series, preferences: Dict, 
                                   watched_titles: set) -> float:
        
        #Calculate how well a movie matches user preferences
        
        
        # Skip if already watched
        if movie['title'] in watched_titles:
            return -1
        
        score = 0.0
        
        # Genre matching (40% weight)
        movie_genres = set(movie['genre_list'])
        genre_score = 0
        genre_match_count = 0
        
        for genre in movie_genres:
            if genre in preferences['genres']:
                genre_score += preferences['genres'][genre]
                genre_match_count += 1
        
        if genre_match_count > 0:
            score += (genre_score / genre_match_count) * 0.4
        
        # High cvbvrated genre bonus (10% weight)
        high_rated_match = len(movie_genres.intersection(
            set(preferences['high_rated_genres'])
        ))
        score += (high_rated_match / max(len(preferences['high_rated_genres']), 1)) * 0.1
        
        # TMDb vote average (20% weight) - prefer highly rated movies
        # Normalize to 0-1 scale (assuming vote_average is 0-10)
        vote_avg = movie.get('vote_average', 0) / 10.0
        score += vote_avg * 0.2
        
        # Popularity bonus (10% weight) - movies with more votes are more reliable
        # Used log scale to prevent extremely popular movies from dominating
        vote_count = movie.get('vote_count', 0)
        if vote_count > 0:
            popularity_score = min(np.log10(vote_count) / 5, 1.0)  # Cap at 100k votes
            score += popularity_score * 0.1


        year_diff = abs(movie['release_year'] - preferences['avg_year'])
        year_score = max(0, 1 - (year_diff / (preferences['year_std'] * 2 + 1)))
        score += year_score * 0.1
        
        # Runtime preference (10% weight)
        runtime_diff = abs(movie['runtime_minutes'] - preferences['avg_runtime'])
        runtime_score = max(0, 1 - (runtime_diff / (preferences['runtime_std'] * 2 + 1)))
        score += runtime_score * 0.1
        
        return score
    
    def get_recommendations(self, letterboxd_data: List[Dict], 
                          n_recommendations: int = 20,
                          min_vote_count: int = 100) -> pd.DataFrame:
        
        #Generate movie recommendations for a user
        user_movies = self.match_letterboxd_movies(letterboxd_data)
        
        if len(user_movies) == 0:
            raise ValueError("No movies could be matched from Letterboxd data")
        
        print(f"Matched {len(user_movies)} movies from user's Letterboxd")
        
        
        preferences = self.analyze_user_preferences(user_movies)
        print(f"\nTop genres: {list(preferences['genres'].keys())[:5]}")
        print(f"Average rating: {preferences['avg_rating']:.2f}")
        
        watched_titles = set(user_movies['title'].values)

        candidates = self.movies_df[
            (self.movies_df['vote_count'] >= min_vote_count)
        ].copy()
        
        # Calculate scores for all candidates
        candidates['recommendation_score'] = candidates.apply(
            lambda movie: self.calculate_similarity_score(
                movie, preferences, watched_titles
            ),
            axis=1
        )
        
        # Remove already watched movies (score = -1)
        candidates = candidates[candidates['recommendation_score'] > 0]
        
        recommendations = candidates.nlargest(n_recommendations, 'recommendation_score')
        
        # Select relevant columns for output
        output_cols = [
            'title', 'release_year', 'genres', 'runtime_minutes',
            'vote_average', 'vote_count', 'tmdb_url', 'recommendation_score'
        ]
        
        return recommendations[output_cols].reset_index(drop=True)
    
    def get_diverse_recommendations(self, letterboxd_data: List[Dict],
                                   n_recommendations: int = 20,
                                   diversity_factor: float = 0.3) -> pd.DataFrame:
        
        #Generate diverse movie recommendations (mix of safe bets and exploration)
        
        # Get more recommendations than needed
        candidates = self.get_recommendations(
            letterboxd_data, 
            n_recommendations=int(n_recommendations * 3),
            min_vote_count=50
        )
        
        # Split into safe bets (high scores) and exploration (diverse)
        n_safe = int(n_recommendations * (1 - diversity_factor))
        n_diverse = n_recommendations - n_safe
        
        # Safe bets: top scoring movies
        safe_bets = candidates.head(n_safe)
        
        # Diverse picks: sample from remaining candidates weighted by score
        remaining = candidates.iloc[n_safe:]
        if len(remaining) > 0:
            # Weight by score but add randomness
            weights = remaining['recommendation_score'] ** 0.5  # Square root for more diversity
            weights = weights / weights.sum()
            
            diverse_indices = np.random.choice(
                remaining.index,
                size=min(n_diverse, len(remaining)),
                replace=False,
                p=weights
            )
            diverse_picks = candidates.loc[diverse_indices]
        else:
            diverse_picks = pd.DataFrame()
        
        # Combine and return
        result = pd.concat([safe_bets, diverse_picks], ignore_index=True)
        return result.head(n_recommendations)


# Example usage and testing
if __name__ == "__main__":
    # Initialize recommender
    recommender = MovieRecommender('recommendations.csv')
    
    # Example Letterboxd data format (this would come from your letterboxdpy module)
    example_user_data = [
        {'title': 'Gladiator', 'year': 2000, 'rating': 5.0},
        {'title': 'Interstellar', 'year': 2014, 'rating': 5.0},
        {'title': 'American Gangster', 'year': 2007, 'rating': 5.0},
        {'title': 'Inglourious Basterds', 'year': 2009, 'rating': 5.0},
        {'title': 'Kingdom of Heaven', 'year': 2005, 'rating': 4.0},
    ]
    
    # Get recommendations
    try:
        recommendations = recommender.get_recommendations(
            example_user_data,
            n_recommendations=10
        )
        
        print("\n=== TOP RECOMMENDATIONS ===")
        for idx, movie in recommendations.iterrows():
            print(f"\n{idx + 1}. {movie['title']} ({int(movie['release_year'])})")
            print(f"   Genres: {movie['genres']}")
            print(f"   Rating: {movie['vote_average']:.1f}/10")
            print(f"   Match Score: {movie['recommendation_score']:.3f}")
            
    except ValueError as e:
        print(f"Error: {e}")