from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView

from .models import Movie
from genre.models import Genre


class MovieListView(ListView):
    model = Movie
    template_name = 'movie_list.html'
    context_object_name = 'movies'
    paginate_by = 20

    def get_queryset(self):
        qs = (
            Movie.objects.all()
            .prefetch_related('genres', 'directors')
        )

        # Search
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(directors__name__icontains=q)).distinct()

        genre = self.request.GET.get('genre')
        if genre:
            qs = qs.filter(genres__name__iexact=genre).distinct()

        # Ordering
        order = (self.request.GET.get('order') or '').lower()
        if order == 'rating':
            qs = qs.order_by('-ratings', '-total_views', 'name')
        elif order == 'views':
            qs = qs.order_by('-total_views', '-ratings', 'name')
        elif order == 'likes':
            qs = qs.order_by('-total_likes', '-ratings', 'name')
        elif order == 'name':
            qs = qs.order_by('name')
        else:
            # default ordering: popular first (by rating then views)
            qs = qs.order_by('-ratings', '-total_views', 'name')

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['current_genre'] = self.request.GET.get('genre', '')
        ctx['current_order'] = self.request.GET.get('order', '')
        ctx['genres'] = Genre.objects.all()
        return ctx


class MovieDetailView(DetailView):
    model = Movie
    template_name = 'movie_detail.html'
    context_object_name = 'movie'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Movie.objects.all().prefetch_related('genres', 'directors')

    def get_object(self, queryset=None):
        queryset = queryset or self.get_queryset()
        obj = get_object_or_404(queryset, **{self.slug_field: self.kwargs.get(self.slug_url_kwarg)})
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['directors'] = self.object.directors.all()
        ctx['genres'] = self.object.genres.all()
        return ctx
