from django.urls import path
from .views import import_letterboxd_view

urlpatterns = [
    path("", import_letterboxd_view, name="letterboxd"),
]
