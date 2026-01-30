from django.urls import path
from . import views

urlpatterns = [
    path("pools/join/", views.join_pool, name="join_pool"),
    path("pools/<str:join_code>/picks/", views.make_picks, name="make_picks"),
    path("pools/<str:join_code>/leaderboard/", views.leaderboard, name="leaderboard"),
]
