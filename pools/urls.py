from django.urls import path
from . import views

urlpatterns = [
    path("pools/<str:join_code>/leaderboard/", views.leaderboard, name="leaderboard"),
]
