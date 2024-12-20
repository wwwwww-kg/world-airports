from django.urls import path
from main.views import *


urlpatterns = [
    path('', index, name='index'),
    path('search', search, name='search'),
    path('airport/<str:airport_iri>', airport_detail, name='airport_detail'),
    path('country/<str:country_iri>', country_detail, name='country_detail'),
]