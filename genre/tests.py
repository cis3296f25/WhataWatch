from django.test import TestCase
from django.urls import reverse
from django.core.cache import cache

from .models import Genre


class GenreListViewTests(TestCase):

    def setUp(self):
        cache.clear()  # clear cache before each test
        Genre.objects.create(name="Rock")
        Genre.objects.create(name="Jazz")
        Genre.objects.create(name="Classical")

    def test_view_status_code(self):
        """View returns 200 OK"""
        response = self.client.get(reverse('genre-list'))
        self.assertEqual(response.status_code, 200)

    def test_correct_template_used(self):
        """View uses genre_list.html"""
        response = self.client.get(reverse('genre-list'))
        self.assertTemplateUsed(response, 'genre_list.html')

    def test_context_contains_genres(self):
        """View passes 'genres' in context"""
        response = self.client.get(reverse('genre-list'))
        self.assertIn('genres', response.context)

    def test_genres_are_ordered_by_name(self):
        """Genres are alphabetically ordered"""
        response = self.client.get(reverse('genre-list'))
        genres = response.context['genres']
        names = [g.name for g in genres]
        self.assertEqual(names, sorted(names))

    def test_view_is_cached(self):
        """View output is cached"""
        response1 = self.client.get(reverse('genre-list'))
        # Add a new genre AFTER the first request
        Genre.objects.create(name="Z-Test")
        response2 = self.client.get(reverse('genre-list'))

        # Cached view should NOT include Z-Test
        self.assertEqual(response1.content, response2.content)

