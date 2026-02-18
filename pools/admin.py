from django.contrib import admin
from .models import Season, Pool, Entry, Contestant, Episode


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    list_display = ("name", "join_code", "season", "created_at")
    list_filter = ("season",)
    search_fields = ("name", "join_code")


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ("user", "pool", "first_out", "winner_1", "winner_2", "created_at")
    list_filter = ("pool",)
    search_fields = ("user__username", "pool__name")


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sole_survivor", "created_at")
    list_filter = ("sole_survivor",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Contestant)
class ContestantAdmin(admin.ModelAdmin):
    list_display = ("name", "season", "tribe", "active", "eliminated", "created_at")
    list_filter = ("season", "tribe", "active", "eliminated")
    search_fields = ("name", "tribe")
    autocomplete_fields = ("season",)

    # Makes the edit form nicer: image + bio in a big box
    fields = (
        "season",
        "name",
        "tribe",
        "photo",
        "bio",
        "active",
        "eliminated",
    )


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ("season", "number", "eliminated")
    list_filter = ("season",)
    search_fields = ("season__name",)
    ordering = ("season", "number")
    autocomplete_fields = ("season", "eliminated")
