from django.db import models

from director.models import Director
from genre.models import Genre


class Movie(models.Model):
    movie_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100)
    ratings = models.DecimalField(max_digits=2, decimal_places=1, blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    total_views = models.IntegerField(blank=True, null=True)
    total_likes = models.IntegerField(blank=True, null=True)
    in_lists = models.IntegerField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    directors = models.ManyToManyField(Director, related_name='movies', blank=True)
    length = models.IntegerField(blank=True, null=True)
    poster_url = models.URLField(blank=True, null=True)
    genres = models.ManyToManyField(Genre, related_name='movies', blank=True)

    def __str__(self):
        return f'{self.name}'
