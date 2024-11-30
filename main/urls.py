from django.urls import path
from main.views import *


urlpatterns = [
    path('', index, name='index'),
    path('search', search, name='search'),
    path('airport/<IRI>', airport_detail, name='airport_detail'),
    path('country/<IRI>', country_detail, name='country_detail'),
]