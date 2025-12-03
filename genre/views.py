from django.views.generic import ListView
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from .models import Genre

class GenreListView(ListView):
    model = Genre
    template_name = 'genre_list.html'
    context_object_name = 'genres'
    ordering = ['name']

    @method_decorator(cache_page(60 * 15)) # Cache for 15 minutes
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
