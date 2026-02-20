from collections import defaultdict
from pathlib import Path
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.http import HttpResponseForbidden
from .models import Pool, Entry, Episode, Contestant
from django.http import JsonResponse, HttpResponseBadRequest
from .services.scoring import build_cumulative_eliminations, calculate_total_points
from .forms import JoinPoolForm, EntryPicksForm
from .services_first_out import generate_first_out_lottery
from .decorators import require_picks
# ============================================================
# LEADERBOARD (DO NOT REMOVE — ROUTED FROM pools/urls.py)
# ============================================================

@require_picks
@login_required
def leaderboard(request, join_code: str):
    pool = get_object_or_404(Pool, join_code=join_code)

    weeks = build_cumulative_eliminations(pool.season)

    # Final cumulative set of eliminated contestant IDs (may be empty)
    final_eliminated = set(weeks[-1]) if weeks else set()

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

        # Determine whether each pick has been eliminated already
        first_out_eliminated = (entry.first_out_id in final_eliminated) if entry.first_out_id else False
        winner_1_eliminated = (entry.winner_1_id in final_eliminated) if entry.winner_1_id else False
        winner_2_eliminated = (entry.winner_2_id in final_eliminated) if entry.winner_2_id else False

        rows.append({
            "user": entry.user,
            "entry": entry,
            "score": bd.total,
            "last_week": bd.weekly_points,
            "first_out_eliminated": first_out_eliminated,
            "winner_1_eliminated": winner_1_eliminated,
            "winner_2_eliminated": winner_2_eliminated,
        })

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
# CONTESTANTS CATALOG (Flipbook)
# ============================================================

@login_required
def contestants(request, join_code: str):
    """Contestant flipbook/catalog for a given pool's season.

    URL: /pools/<join_code>/contestants/
    """
    pool = get_object_or_404(Pool, join_code=join_code)
    season = pool.season

    contestants_qs = (
        Contestant.objects
        .filter(season=season)
        .annotate(
            is_eliminated=Exists(
                Episode.objects.filter(season=season, eliminated=OuterRef("pk"))
            )
        )
        .order_by("name")
    )

    # Turn into a list so we can attach per-instance attributes (field_notes)
    contestants_list = list(contestants_qs)

    # Folder: media/cast/season-50/bios
    # (You said this is where the .txt files live)
    bios_dir = (Path(settings.MEDIA_ROOT) / "cast" / "season-50" / "bios").resolve()

    for c in contestants_list:
        c.field_notes = None  # default fallback

        # Only try if contestant has a photo file
        photo_field = getattr(c, "photo", None)
        if not photo_field:
            continue

        try:
            # Use the *basename* of the image to find the .txt
            # e.g. "Venus.png" -> "Venus.txt"
            photo_basename = Path(photo_field.name).name     # relative to MEDIA_ROOT
            stem = Path(photo_basename).stem
            bio_path = (bios_dir / f"{stem}.txt").resolve()

            # Safety: ensure we only read inside bios_dir
            if bios_dir not in bio_path.parents:
                continue

            if bio_path.exists() and bio_path.is_file():
                c.field_notes = bio_path.read_text(encoding="utf-8", errors="replace").strip()

        except Exception:
            # If anything goes wrong, keep placeholder
            c.field_notes = None

    # Allow selecting picks from the catalog only when the current user has an
    # Entry for this pool and has not yet set any picks (first_out/winner_1/winner_2).
    can_pick_on_catalog = False
    if request.user.is_authenticated:
        try:
            entry = Entry.objects.get(pool=pool, user=request.user)
            if not entry.first_out and not entry.winner_1 and not entry.winner_2:
                can_pick_on_catalog = True
        except Entry.DoesNotExist:
            can_pick_on_catalog = False

    return render(request, "pools/contestants.html", {
        "pool": pool,
        "contestants": contestants_list,  # IMPORTANT: list, not qs
        "can_pick_on_catalog": can_pick_on_catalog,
    })


@login_required
def catalog_pick(request, join_code: str):
    """AJAX endpoint: set a pick (first_out, winner_1, winner_2) for the
    current user's Entry based on a contestant selected from the catalog.
    Only allowed if the Entry exists and currently has no picks set.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    pool = get_object_or_404(Pool, join_code=join_code)

    pick_type = request.POST.get("pick_type") or request.headers.get("X-PICK-TYPE")
    contestant_id = request.POST.get("contestant_id") or request.headers.get("X-CONTESTANT-ID")

    if pick_type not in ("first_out", "winner_1", "winner_2"):
        return JsonResponse({"error": "invalid pick_type"}, status=400)

    try:
        contestant = Contestant.objects.get(pk=int(contestant_id), season=pool.season)
    except Exception:
        return JsonResponse({"error": "invalid contestant"}, status=400)

    entry, _ = Entry.objects.get_or_create(pool=pool, user=request.user)
    # Only allow if no picks are set yet
    if entry.first_out or entry.winner_1 or entry.winner_2:
        return JsonResponse({"error": "picks already set"}, status=400)

    setattr(entry, pick_type, contestant)
    entry.save()

    return JsonResponse({"success": True, "pick_type": pick_type, "contestant": contestant.name})



# ============================================================
# DASHBOARD (now used ONLY for data, template in accounts/)
# ============================================================

@login_required
def dashboard(request):
    """
    Global dashboard at /dashboard/.
    If the user has ANY Entry with incomplete required picks, redirect them to
    that pool's picks page.
    """

    # ------------------------------------------------------------
    # 1) Enforce picks completion (Option B)
    # ------------------------------------------------------------
    # Recommended for your setup: require winners only (first_out may be drafted later).
    incomplete_entry = (
        Entry.objects
        .select_related("pool")
        .filter(user=request.user)
        .filter(Q(winner_1__isnull=True) | Q(winner_2__isnull=True))
        .order_by("created_at")  # deterministic: oldest incomplete first
        .first()
    )

    # If you DO want to require first_out immediately, use this instead:
    # .filter(Q(winner_1__isnull=True) | Q(winner_2__isnull=True) | Q(first_out__isnull=True))

    if incomplete_entry:
        return redirect("make_picks", join_code=incomplete_entry.pool.join_code)

    # ------------------------------------------------------------
    # 2) Normal dashboard logic (unchanged, just no join_code param)
    # ------------------------------------------------------------
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

        rows.sort(key=lambda r: (-r["score"], r["user_id"]))

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

def rules(request):
    """Placeholder rules page; currently just displays static text."""
    # for now we don't need any special context - could add season/pool if desired
    return render(request, "pools/rules.html")


@login_required
def join_pool(request):
    # If the user already belongs to a pool we can pass that along so the
    # template has something to anchor the fixed buttons against.  This
    # mirrors the behaviour of the dashboard/leaderboard pages where the pool
    # context is always available.
    current_pool = None
    entry = Entry.objects.filter(user=request.user).select_related("pool").first()
    if entry:
        current_pool = entry.pool

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

    context = {"form": form}
    if current_pool:
        context["pool"] = current_pool
    return render(request, "pools/join_pool.html", context)


@login_required
def rules(request):
    """Placeholder rules page; currently just displays static text."""
    # no special context yet
    return render(request, "pools/rules.html")


@login_required
def make_picks(request, join_code):

    pool = get_object_or_404(Pool, join_code=join_code)

    entry, _ = Entry.objects.get_or_create(pool=pool, user=request.user)

    # -----------------------------------
    # Determine draft state
    # -----------------------------------

    draft_generated = pool.first_out_draft_generated
    draft_open = pool.first_out_draft_open

    turn_entry = None
    is_my_turn = False

    if draft_generated and draft_open:

        turn_entry = (
            Entry.objects
            .filter(pool=pool, first_out__isnull=True)
            .order_by("first_out_pick_order", "created_at")
            .select_related("user")
            .first()
        )

        if turn_entry and turn_entry.user_id == request.user.id:
            is_my_turn = True

    # -----------------------------------
    # POST
    # -----------------------------------

    if request.method == "POST":

        form = EntryPicksForm(
            request.POST,
            instance=entry,
            season=pool.season,
            pool=pool,
        )

        if form.is_valid():

            # enforce First Out turn order
            submitted_first_out = form.cleaned_data.get("first_out")

            if submitted_first_out:

                # draft must exist
                if not draft_generated:
                    form.add_error(
                        "first_out",
                        "First Out draft has not been generated yet."
                    )

                # draft must be open
                elif not draft_open:
                    form.add_error(
                        "first_out",
                        "First Out draft is closed."
                    )

                # must be user's turn
                elif not is_my_turn:
                    if turn_entry:
                        form.add_error(
                            "first_out",
                            f"It is currently {turn_entry.user.username}'s turn to select First Out."
                        )
                    else:
                        form.add_error(
                            "first_out",
                            "First Out draft is complete."
                        )

                # prevent editing after locking
                elif entry.first_out_id and entry.first_out_id != submitted_first_out.id:
                    form.add_error(
                        "first_out",
                        "Your First Out pick is already locked."
                    )

            # only save if no errors added above
            if not form.errors:

                try:
                    with transaction.atomic():

                        saved_entry = form.save()

                        # mark timestamp when first_out locked
                        if submitted_first_out and not entry.first_out_picked_at:

                            saved_entry.first_out_picked_at = timezone.now()
                            saved_entry.save(update_fields=["first_out_picked_at"])

                    return redirect("dashboard")

                except IntegrityError:

                    form.add_error(
                        "first_out",
                        "That First Out pick was just taken by someone else."
                    )

    # -----------------------------------
    # GET
    # -----------------------------------

    else:

        form = EntryPicksForm(
            instance=entry,
            season=pool.season,
            pool=pool,
        )

    # -----------------------------------
    # Render
    # -----------------------------------

    return render(request, "pools/make_picks.html", {
        "pool": pool,
        "form": form,
        "entry": entry,

        # useful for template UI
        "draft_generated": draft_generated,
        "draft_open": draft_open,
        "turn_user": turn_entry.user if turn_entry else None,
        "is_my_turn": is_my_turn,
        "my_order": entry.first_out_pick_order,
    })

@login_required
def run_first_out_lottery(request, join_code):
    pool = get_object_or_404(Pool, join_code=join_code)

    # Replace this with your own "is commissioner" logic
    if not request.user.is_staff:
        return HttpResponseForbidden("Only the commissioner can run the lottery.")

    generate_first_out_lottery(pool)
    return redirect("dashboard")