import csv
import requests

TMDB_API_KEY = "030edc6acd11dfeb9196b90438838b7e"

TOP_RATED_URL = "https://api.themoviedb.org/3/movie/top_rated"
MOVIE_DETAIL_URL = "https://api.themoviedb.org/3/movie/{}"

# Output file
OUTPUT_CSV = "recommendations.csv"


MAX_PAGES = 500

def fetch_top_rated_page(page_number: int) -> dict:
    """Fetch one page of TMDb top rated movies."""
    params = {
        "api_key": TMDB_API_KEY,
        "language": "en-US",
        "page": page_number,
    }
    print(f"[TMDb] Fetching top-rated page {page_number}")
    response = requests.get(TOP_RATED_URL, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def fetch_movie_details(movie_id: int) -> dict:
    """Fetch detailed info for a single movie (runtime, genres, etc.)."""
    url = MOVIE_DETAIL_URL.format(movie_id)
    params = {
        "api_key": TMDB_API_KEY,
        "language": "en-US",
    }
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def build_movie_catalog():
    """Main function: fetch top rated movies, enrich with details, write CSV."""
    if TMDB_API_KEY == "YOUR_TMDB_API_KEY_HERE":
        print("ERROR: Please set TMDB_API_KEY in the script before running.")
        return

    all_movies = []
    page = 1

    while page <= MAX_PAGES:
        data = fetch_top_rated_page(page)
        results = data.get("results") or []

        # No more results -> stop
        if not results:
            print(f"[TMDb] No results on page {page}, stopping.")
            break

        for item in results:
            movie_id = item["id"]
            title = item.get("title") or item.get("name") or "Unknown title"
            release_date = item.get("release_date") or ""
            release_year = release_date.split("-")[0] if release_date else ""
            vote_average = item.get("vote_average")
            vote_count = item.get("vote_count")

            # Fetch runtime and genres
            details = fetch_movie_details(movie_id)
            runtime = details.get("runtime")  # in minutes
            genres_list = details.get("genres") or []
            genres = [g.get("name") for g in genres_list if g.get("name")]

            tmdb_url = f"https://www.themoviedb.org/movie/{movie_id}"

            all_movies.append(
                {
                    "tmdb_id": movie_id,
                    "title": title,
                    "release_year": release_year,
                    "runtime_minutes": runtime if runtime is not None else "",
                    "genres": "|".join(genres),
                    "vote_average": vote_average if vote_average is not None else "",
                    "vote_count": vote_count if vote_count is not None else "",
                    "tmdb_url": tmdb_url,
                }
            )

            print(f"[TMDb] Collected: {title} ({release_year})")

        page += 1

    # Write to CSV
    print(f"\nWriting {len(all_movies)} movies to {OUTPUT_CSV}...")
    fieldnames = [
        "tmdb_id",
        "title",
        "release_year",
        "runtime_minutes",
        "genres",
        "vote_average",
        "vote_count",
        "tmdb_url",
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_movies:
            writer.writerow(row)

    print("Done! Movie catalog saved to", OUTPUT_CSV)


if __name__ == "__main__":
    build_movie_catalog()
