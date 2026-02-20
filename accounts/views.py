from collections import defaultdict

from django.contrib.auth.decorators import login_required

from pools.models import Entry, Episode
from pools.services.scoring import build_cumulative_eliminations, calculate_total_points
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from .forms import SignupForm


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("dashboard")
    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})


@login_required
def dashboard(request):
    my_entries = (
        Entry.objects
        .filter(user=request.user)
        .select_related(
            "pool", "pool__season",
            "pool__previous_winner",  # NEW
            "first_out", "winner_1", "winner_2",
        )
        .order_by("pool__season__name", "pool__name")
    )

    # Per-season caches
    weeks_by_season_id = {}
    eliminated_ids_by_season_id = {}

    by_season = defaultdict(list)

    for my_entry in my_entries:
        pool = my_entry.pool
        season = pool.season

        # Cache elimination-by-week structure (for scoring)
        if season.id not in weeks_by_season_id:
            weeks_by_season_id[season.id] = build_cumulative_eliminations(season)

        # Cache eliminated contestant ids (for strike-through)
        if season.id not in eliminated_ids_by_season_id:
            eliminated_ids_by_season_id[season.id] = set(
                Episode.objects
                .filter(season=season, eliminated__isnull=False)
                .values_list("eliminated_id", flat=True)
            )

        weeks = weeks_by_season_id[season.id]
        eliminated_ids = eliminated_ids_by_season_id[season.id]

        # Compute rank within this pool
        all_entries = (
            Entry.objects
            .filter(pool=pool)
            .select_related("user", "first_out", "winner_1", "winner_2")
        )

        scored = []
        for e in all_entries:
            bd = calculate_total_points(
                e,
                eliminated_each_week=weeks,
                sole_survivor_id=season.sole_survivor_id,
            )
            scored.append({"user_id": e.user_id, "score": bd.total})

        scored.sort(key=lambda r: r["score"], reverse=True)
        total_players = len(scored)

        rank = None
        for i, r in enumerate(scored, start=1):
            if r["user_id"] == request.user.id:
                rank = i
                break

        # Flags for strike-through
        winner_1_out = bool(my_entry.winner_1_id and my_entry.winner_1_id in eliminated_ids)
        winner_2_out = bool(my_entry.winner_2_id and my_entry.winner_2_id in eliminated_ids)
        first_out_out = bool(my_entry.first_out_id and my_entry.first_out_id in eliminated_ids)

        # ----------------------------
        # NEW: First Out lottery status
        # ----------------------------
        draft_generated = bool(pool.first_out_draft_generated)
        draft_open = bool(pool.first_out_draft_open)

        # Whose turn is it? (first entry by pick order that still has no first_out)
        turn_entry = (
            Entry.objects
            .filter(pool=pool, first_out__isnull=True)
            .order_by("first_out_pick_order", "created_at")
            .select_related("user")
            .first()
            if draft_open and draft_generated
            else None
        )

        my_pick_order = my_entry.first_out_pick_order
        is_my_turn = bool(turn_entry and turn_entry.user_id == request.user.id)

        by_season[season].append({
            "pool": pool,
            "rank": rank,
            "total_players": total_players,
            "entry": my_entry,

            "winner_1_out": winner_1_out,
            "winner_2_out": winner_2_out,
            "first_out_out": first_out_out,

            # NEW fields for template
            "draft_generated": draft_generated,
            "draft_open": draft_open,
            "my_pick_order": my_pick_order,
            "turn_user": turn_entry.user if turn_entry else None,
            "is_my_turn": is_my_turn,
        })

    seasons = [(season, items) for season, items in by_season.items()]

    # Provide a `pool` context (first pool) so base template can show pool-scoped controls
    first_entry = my_entries.first()
    pool_context = first_entry.pool if first_entry else None

    return render(
        request,
        "accounts/dashboard.html",
        {"seasons": seasons, "pool": pool_context}
    )