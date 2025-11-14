from django.contrib import admin

from .models import Movie

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ['slug', 'name', 'users_rating', 'total_views', 'total_likes']
