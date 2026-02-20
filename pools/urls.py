from django.urls import path
from . import views

urlpatterns = [
    path("pools/join/", views.join_pool, name="join_pool"),
    path("pools/<str:join_code>/picks/", views.make_picks, name="make_picks"),
    path("pools/<str:join_code>/leaderboard/", views.leaderboard, name="leaderboard"),

    # Contestant catalog (flipbook) for a pool's season
    path("pools/<str:join_code>/contestants/", views.contestants, name="contestants"),
    path("pools/<str:join_code>/catalog-pick/", views.catalog_pick, name="catalog_pick"),

    # static informational pages
    path("rules/", views.rules, name="rules"),
]
