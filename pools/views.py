from django.shortcuts import get_object_or_404, render

from .models import Pool, Entry
from .services.scoring import build_cumulative_eliminations, calculate_total_points


def leaderboard(request, join_code: str):
    pool = get_object_or_404(Pool, join_code=join_code)

    weeks = build_cumulative_eliminations(pool.season)

    rows = []
    for entry in Entry.objects.filter(pool=pool).select_related("user", "first_out", "winner_1", "winner_2"):
        bd = calculate_total_points(entry, eliminated_each_week=weeks, sole_survivor_id=None)
        rows.append(
            {
                "user": entry.user,
                "entry": entry,
                "score": bd.total,
                "last_week": bd.weekly_points,
            }
        )

    # sort high to low
    rows.sort(key=lambda r: r["score"], reverse=True)

    return render(request, "pools/leaderboard.html", {"pool": pool, "rows": rows})
