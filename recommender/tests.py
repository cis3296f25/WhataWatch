from unittest.mock import patch, AsyncMock
from django.test import TestCase
from django.urls import reverse
from django.http import HttpResponseBadRequest


class RecommenderViewTests(TestCase):

    def test_get_request_renders_form(self):
        """GET should return the template with no scraping done."""
        response = self.client.get(reverse('recommender'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'recommender.html')

    def test_post_missing_username_returns_400(self):
        """POST without username → 400 Bad Request."""
        response = self.client.post(reverse('recommender'), {'username': ''})
        self.assertEqual(response.status_code, 400)
        self.assertIsInstance(response, HttpResponseBadRequest)

    @patch("movie.views.engine.MovieRecommender.get_recommendations")
    @patch("movie.views.get_movies_from_db_by_ids")
    @patch("movie.views.scrape_all_watched")
    def test_post_successful_flow(self, mock_scrape, mock_db_fetch, mock_recs):
        """
        Full POST flow:
        - scrape_all_watched returns fake film list
        - DB fetch returns fake Movie objects
        - recommender returns fake recommendations
        """

        # 1) Fake scraped films
        mock_scrape.return_value = AsyncMock()
        mock_scrape.return_value = ([{'id': '123', 'slug': 'test-film'}], 1)

        # 2) Fake movie objects from DB
        class FakeMovie:
            slug = 'test-film'
            name = 'Fake Movie'
            year = 2020
            ratings = 4.2

        mock_db_fetch.return_value = AsyncMock()
        mock_db_fetch.return_value = [FakeMovie()]

        # 3) Fake recommendation DataFrame-like object
        mock_recs.return_value = AsyncMock()
        mock_recs.return_value.fillna.return_value.to_dict.return_value = [
            {'slug': 'recommended-1', 'name': 'Recommended Movie'}
        ]

        response = self.client.post(reverse('recommender'), {'username': 'john'})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'recommender.html')

        ctx = response.context

        # View must pass username back
        self.assertEqual(ctx['username'], 'john')

        # Recommendations should be exactly what our mock returned
        self.assertEqual(len(ctx['recommendations']), 1)
        self.assertEqual(ctx['recommendations'][0]['slug'], 'recommended-1')

        # No error should be present
        self.assertIsNone(ctx['recommender_error'])

        # Ensure mocked functions were called correctly
        mock_scrape.assert_called_once_with('john', concurrency=6)
        mock_db_fetch.assert_awaited()
        mock_recs.assert_called_once()
