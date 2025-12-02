import asyncio
import logging

from asgiref.sync import sync_to_async
from bs4 import BeautifulSoup
import httpx

from django.shortcuts import render
from django.http import HttpResponseBadRequest

from movie.models import Movie
from utils import extractors, recommendation_engine as engine
from director.models import Director
from genre.models import Genre

logger = logging.getLogger(__name__)

LETTERBOXD_BASE = 'https://letterboxd.com'

async def fetch_html(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url, follow_redirects=True, timeout=30.0)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPStatusError as e:
        logger.warning('HTTP error fetching %s: %s', url, e)
        return None
    except Exception as e:
        logger.warning('Error fetching %s: %s', url, e)
        return None


def parse_films_list(html):
    '''Return list of film dicts from a /{username}/films/ page'''
    soup = BeautifulSoup(html, 'html.parser')
    results = []

    poster_items = soup.select('div.poster-grid>ul')[0].find_all('li')

    for item in poster_items:
        react_component = item.find('div.react-component') or item.div
        movie_slug = react_component.get('data-item-slug') or react_component.get('data-film-slug')
        movie_id = react_component['data-film-id']

        results.append({
            'id': movie_id,
            'slug': movie_slug
        })

    return results


def parse_film_page(html):
    '''Best-effort extraction from an individual film page'''
    soup = BeautifulSoup(html, 'html.parser')
    data = {
        'name': extractors.extract_title(soup),
        'year': extractors.extract_year(soup),
        'description': extractors.extract_description(soup),
        'genres': extractors.extract_genres(soup),
        'cast': extractors.extract_cast(soup),
        'directors': extractors.extract_directors(soup),
        'length': extractors.extract_runtime(soup),
        'poster_url': extractors.extract_poster(soup),
    }
    return data


# Use sync_to_async to run blocking DB operations in threadpool
@sync_to_async
def save_movie_from_data(movie_data):
    genres = movie_data.pop('genres')
    directors = movie_data.pop('directors')
    casts = movie_data.pop('cast')

    movie, _ = Movie.objects.get_or_create(
        movie_id=movie_data.pop('movie_id'),
        name=movie_data.pop('name'),
        slug=movie_data.pop('slug'),
        defaults=movie_data
    )

    for name in directors:
        director, _ = Director.objects.get_or_create(name=name)
        movie.directors.add(director)

    for name in genres:
        genre, _ = Genre.objects.get_or_create(name=name)
        movie.genres.add(genre)


async def scrape_all_watched(username, concurrency=6):
    '''
    Scrapes all /{username}/films/ pages until no more film entries are found.
    Returns (list_of_film_dicts, pages_scraped)
    '''
    async with httpx.AsyncClient(headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=30.0) as client:
        page = 1
        all_films = []
        seen_urls = set()
        while True:
            if page == 1:
                url = f'{LETTERBOXD_BASE}/{username}/films/'
            else:
                url = f'{LETTERBOXD_BASE}/{username}/films/page/{page}/'

            html = await fetch_html(client, url)
            if not html:
                # stop on error/404
                break

            films = parse_films_list(html)
            # filter new films by url
            new = [f for f in films if f['slug'] not in seen_urls]
            if not new:
                # no new films found -> conclude we're done
                break

            for f in new:
                seen_urls.add(f['slug'])
                all_films.append(f)

            page += 1

        pages_scraped = page - 1
        return all_films, pages_scraped


async def fetch_and_save_all(films, concurrency=6):
    sem = asyncio.Semaphore(concurrency)
    saved_movies = []

    async with httpx.AsyncClient(headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=30.0) as client:
        async def worker(film):
            async with sem:
                html = await fetch_html(client, f"{LETTERBOXD_BASE}/film/{film['slug']}")
                stats_html = await fetch_html(client, f"{LETTERBOXD_BASE}/csi/film/{film['slug']}/stats/")
                ratings_html = await fetch_html(client, f"{LETTERBOXD_BASE}/csi/film/{film['slug']}/ratings-summary/")

                stats = extractors.extract_stats(stats_html)
                ratings = extractors.extract_ratings(ratings_html)

                details = parse_film_page(html) if html else {}
                details = {
                    **details,
                    'movie_id': film['id'],
                    'slug': film['slug'],
                    'total_views': stats[0],
                    'in_lists': stats[1],
                    'total_likes': stats[2],
                    'ratings': ratings,
                }

                await save_movie_from_data(details.copy())

                saved_movies.append(details)

        tasks = [asyncio.create_task(worker(f)) for f in films]
        # process tasks in batches to avoid huge concurrency spikes
        BATCH = 50
        for i in range(0, len(tasks), BATCH):
            batch = tasks[i : i + BATCH]
            await asyncio.gather(*batch)

    return saved_movies


@sync_to_async
def get_movies_from_db_by_ids(movie_ids):
    qs = Movie.objects.filter(movie_id__in=movie_ids)
    return list(qs)


async def import_letterboxd_view(request):
    if request.method == 'GET':
        return render(request, 'username_form.html')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        if not username:
            return HttpResponseBadRequest('username required')

        # Scrape the user's watched film list pages until exhausted
        films, pages_scraped = await scrape_all_watched(username, concurrency=6)

        # Fetch each film detail and save to DB
        # saved_movies = await fetch_and_save_all(films, concurrency=6)

        movie_ids = [f['id'] for f in films]
        recommendations = []
        recommender_error = None

        try:
            # Query DB for the movies we just scraped
            db_movies = await get_movies_from_db_by_ids(movie_ids)

            # build letterboxd_data list of dicts: name, year, ratings
            letterboxd_data = []
            for m in db_movies:
                name = getattr(m, 'name', None)
                year = getattr(m, 'year', None)
                ratings = getattr(m, 'ratings', None)
                letterboxd_data.append({'slug': m.slug, 'name': name, 'year': year, 'ratings': ratings})

            recommender = engine.MovieRecommender()
            recs_df = recommender.get_recommendations(letterboxd_data, n_recommendations=12, min_popularity=50)

            try:
                recommendations = recs_df.fillna('').to_dict(orient='records')
            except Exception:
                if hasattr(recs_df, 'to_dict'):
                    recommendations = recs_df.to_dict()
                else:
                    recommendations = []

        except Exception as e:
            # don't fail the whole request; surface error to template
            logger.exception('Recommender failed for username %s: %s', username, e)
            recommender_error = str(e)

        context = {
            'username': username,
            'recommendations': recommendations,
            'recommender_error': recommender_error,
        }

        print(recommendations[0])

        return render(request, 'username_form.html', context)

    # other methods not allowed
    return HttpResponseBadRequest('Method not allowed')
