from django.urls import path
from .views import recommender_view

urlpatterns = [
    path('', recommender_view, name='recommender'),
]
