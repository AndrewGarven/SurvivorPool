from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect

from .models import Pool, Entry
from .services.scoring import build_cumulative_eliminations, calculate_total_points
from django.http import HttpResponse
from django.contrib import messages
from .forms import JoinPoolForm
from django.db import IntegrityError, transaction
from .forms import EntryPicksForm


# ============================================================
# LEADERBOARD (DO NOT REMOVE — ROUTED FROM pools/urls.py)
# ============================================================

@login_required
def leaderboard(request, join_code: str):
    pool = get_object_or_404(Pool, join_code=join_code)

    weeks = build_cumulative_eliminations(pool.season)

    rows = []
    for entry in (
        Entry.objects
        .filter(pool=pool)
        .select_related("user", "first_out", "winner_1", "winner_2")
    ):
        sole_survivor_id = pool.season.sole_survivor_id
        bd = calculate_total_points(
            entry,
            eliminated_each_week=weeks,
            sole_survivor_id=sole_survivor_id,
        )

        rows.append({
            "user": entry.user,
            "entry": entry,
            "score": bd.total,
            "last_week": bd.weekly_points,
        })

    # Sort by score (high → low)
    # Sort by score (high → low). Secondary sort is optional, just for stable display.
    rows.sort(key=lambda r: (-r["score"], r["user"].username.lower()))
    
    # Assign COMPETITION ranks (1,1,3,4...)
    prev_score = None
    prev_rank = 0
    
    for i, r in enumerate(rows, start=1):
        score = r["score"]
        if prev_score is None or score != prev_score:
            rank = i           # new score group → rank equals position
        else:
            rank = prev_rank   # tie → same rank as previous
    
        r["rank"] = rank
        prev_score = score
        prev_rank = rank
    

    return render(
        request,
        "pools/leaderboard.html",
        {
            "pool": pool,
            "rows": rows,
        },
    )


# ============================================================
# DASHBOARD (now used ONLY for data, template in accounts/)
# ============================================================

@login_required
def dashboard(request):
    entries = (
        Entry.objects
        .filter(user=request.user)
        .select_related("pool", "pool__season")
    )

    by_season = defaultdict(list)

    for entry in entries:
        pool = entry.pool
        season = pool.season

        # Calculate leaderboard for rank
        weeks = build_cumulative_eliminations(season)

        rows = []
        for e in pool.entries.select_related(
            "user", "first_out", "winner_1", "winner_2"
        ):
            bd = calculate_total_points(
                e,
                eliminated_each_week=weeks,
                sole_survivor_id=season.sole_survivor_id,
            )
            rows.append({
                "user_id": e.user_id,
                "score": bd.total,
            })

        rows.sort(key=lambda r: (-r["score"], r["user_id"]))  # stable ordering, ranking still by score only

        rank = None
        prev_score = None
        prev_rank = 0
        
        for i, r in enumerate(rows, start=1):
            score = r["score"]
            if prev_score is None or score != prev_score:
                cur_rank = i
            else:
                cur_rank = prev_rank
        
            if r["user_id"] == request.user.id:
                rank = cur_rank
                break
        
            prev_score = score
            prev_rank = cur_rank
        
        
        by_season[season].append({
            "pool": pool,
            "rank": rank,
            "total_players": len(rows),
        })

    seasons = [(season, pools) for season, pools in by_season.items()]

    return render(
        request,
        "accounts/dashboard.html",
        {"seasons": seasons},
    )

@login_required
def join_pool(request):
    if request.method == "POST":
        form = JoinPoolForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["join_code"].strip()
            pool = get_object_or_404(Pool, join_code=code)

            # Create the Entry if it doesn't exist
            Entry.objects.get_or_create(pool=pool, user=request.user)

            # Redirect to picks page (or dashboard if you want)
            return redirect("make_picks", join_code=pool.join_code)
    else:
        form = JoinPoolForm()

    return render(request, "pools/join_pool.html", {"form": form})


@login_required
def make_picks(request, join_code):
    pool = get_object_or_404(Pool, join_code=join_code)

    # get or create the user's entry for this pool
    entry, _ = Entry.objects.get_or_create(pool=pool, user=request.user)

    if request.method == "POST":
        # ✅ PASS pool=pool and season=pool.season
        form = EntryPicksForm(request.POST, instance=entry, season=pool.season, pool=pool)

        if form.is_valid():
            try:
                # ✅ safety net for race conditions
                with transaction.atomic():
                    form.save()
                return redirect("dashboard")

            except IntegrityError:
                # If someone took the same first_out milliseconds earlier
                form.add_error(
                    "first_out",
                    "That First Out pick was just taken by someone else. Please choose another."
                )
        # if not valid, fall through and re-render same page with errors

    else:
        # GET request
        form = EntryPicksForm(instance=entry, season=pool.season, pool=pool)

    return render(request, "pools/make_picks.html", {
        "pool": pool,
        "form": form,
        "entry": entry,
    })