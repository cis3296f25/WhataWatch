from django.views.generic import ListView
from .models import Genre

class GenreListView(ListView):
    model = Genre
    template_name = 'genre_list.html'
    context_object_name = 'genres'
    ordering = ['name']
