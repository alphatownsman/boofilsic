from django.urls import path
from .views import *

app_name = "common"
urlpatterns = [
    path("", home),
    path("api-doc/", api_doc, name="api_doc"),
    path("home/", home, name="home"),
    path("me/", me, name="me"),
]
