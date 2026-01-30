from django.contrib import admin
from .models import Season, Pool, Entry, Contestant, Episode

@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    list_display = ("name", "join_code", "created_at")

@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ("user", "pool", "first_out", "winner_1", "winner_2", "created_at")
    list_filter = ("pool",)
    search_fields = ("user__username", "pool__name")

@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sole_survivor", "created_at")
    list_filter = ("sole_survivor",)

@admin.register(Contestant)
class ContestantAdmin(admin.ModelAdmin):
    list_display = ("name", "season", "active", "created_at")
    list_filter = ("season", "active")
    search_fields = ("name",)

@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ("season", "number", "eliminated")
    list_filter = ("season",)
    search_fields = ("season__name",)

