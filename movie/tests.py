from django.test import TestCase
from django.urls import reverse
from django.core.cache import cache

from movie.models import Movie
from genre.models import Genre
from person.models import Director  # adjust if your app name differs


class MovieListViewTests(TestCase):

    def setUp(self):
        cache.clear()

        # Create genres
        self.genre1 = Genre.objects.create(name="Action")
        self.genre2 = Genre.objects.create(name="Drama")

        # Create directors
        self.dir1 = Director.objects.create(name="Nolan")
        self.dir2 = Director.objects.create(name="Tarantino")

        # Create movies
        self.m1 = Movie.objects.create(
            name="Movie A",
            ratings=8.5,
            total_views=500,
            total_likes=200,
            slug="movie-a"
        )
        self.m1.genres.add(self.genre1)
        self.m1.directors.add(self.dir1)

        self.m2 = Movie.objects.create(
            name="Movie B",
            ratings=9.0,
            total_views=800,
            total_likes=300,
            slug="movie-b"
        )
        self.m2.genres.add(self.genre2)
        self.m2.directors.add(self.dir2)

    def test_status_code(self):
        response = self.client.get(reverse('movie-list'))
        self.assertEqual(response.status_code, 200)

    def test_correct_template(self):
        response = self.client.get(reverse('movie-list'))
        self.assertTemplateUsed(response, 'movie_list.html')

    def test_pagination(self):
        response = self.client.get(reverse('movie-list'))
        self.assertTrue('is_paginated' in response.context)
        self.assertEqual(response.context['paginator'].per_page, 20)

    def test_search_filter(self):
        response = self.client.get(reverse('movie-list'), {'q': 'Movie A'})
        movies = response.context['movies']
        self.assertEqual(movies.count(), 1)
        self.assertEqual(movies[0], self.m1)

    def test_genre_filter(self):
        response = self.client.get(reverse('movie-list'), {'genre': 'Drama'})
        movies = response.context['movies']
        self.assertEqual(movies.count(), 1)
        self.assertEqual(movies[0], self.m2)

    def test_ordering_rating(self):
        response = self.client.get(reverse('movie-list'), {'order': 'rating'})
        movies = list(response.context['movies'])
        self.assertEqual(movies[0], self.m2)  # higher rating first

    def test_ordering_views(self):
        response = self.client.get(reverse('movie-list'), {'order': 'views'})
        movies = list(response.context['movies'])
        self.assertEqual(movies[0], self.m2)  # more views first

    def test_ordering_likes(self):
        response = self.client.get(reverse('movie-list'), {'order': 'likes'})
        movies = list(response.context['movies'])
        self.assertEqual(movies[0], self.m2)  # more likes first

    def test_ordering_name(self):
        response = self.client.get(reverse('movie-list'), {'order': 'name'})
        movies = list(response.context['movies'])
        self.assertEqual([m.name for m in movies], ["Movie A", "Movie B"])

    def test_context_values(self):
        response = self.client.get(reverse('movie-list'), {'q': 'abc', 'genre': 'Drama', 'order': 'views'})
        self.assertEqual(response.context['q'], 'abc')
        self.assertEqual(response.context['current_genre'], 'Drama')
        self.assertEqual(response.context['current_order'], 'views')
        self.assertIn(self.genre1, response.context['genres'])
        self.assertIn(self.genre2, response.context['genres'])


class MovieDetailViewTests(TestCase):

    def setUp(self):
        cache.clear()

        self.genre = Genre.objects.create(name="Sci-Fi")
        self.director = Director.objects.create(name="James Cameron")

        self.movie = Movie.objects.create(
            name="Avatar",
            slug="avatar",
            ratings=8.0,
            total_views=1000,
            total_likes=500
        )
        self.movie.genres.add(self.genre)
        self.movie.directors.add(self.director)

    def test_status_code(self):
        response = self.client.get(reverse('movie-detail', kwargs={'slug': 'avatar'}))
        self.assertEqual(response.status_code, 200)

    def test_correct_template(self):
        response = self.client.get(reverse('movie-detail', kwargs={'slug': 'avatar'}))
        self.assertTemplateUsed(response, 'movie_detail.html')

    def test_movie_is_correct(self):
        response = self.client.get(reverse('movie-detail', kwargs={'slug': 'avatar'}))
        self.assertEqual(response.context['movie'], self.movie)

    def test_context_includes_directors_and_genres(self):
        response = self.client.get(reverse('movie-detail', kwargs={'slug': 'avatar'}))
        self.assertIn(self.director, response.context['directors'])
        self.assertIn(self.genre, response.context['genres'])

    def test_caching(self):
        response1 = self.client.get(reverse('movie-detail', kwargs={'slug': 'avatar'}))

        # Change something that *would* appear
        self.movie.name = "Avatar Updated"
        self.movie.save()

        response2 = self.client.get(reverse('movie-detail', kwargs={'slug': 'avatar'}))

        # Cached output should NOT change
        self.assertEqual(response1.content, response2.content)
