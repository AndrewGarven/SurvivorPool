from functools import wraps
from django.shortcuts import redirect, get_object_or_404
from django.urls import resolve
from .models import Pool, Entry

def require_picks(view_func):
    @wraps(view_func)
    def wrapper(request, join_code, *args, **kwargs):
        pool = get_object_or_404(Pool, join_code=join_code)

        entry = Entry.objects.filter(pool=pool, user=request.user).first()
        if entry is None:
            return redirect("dashboard")  # or join_pool

        # If first_out is drafted later, you may want to NOT require it here.
        picks_complete = (
            entry.winner_1_id is not None and
            entry.winner_2_id is not None and
            entry.first_out_id is not None
        )

        if not picks_complete and resolve(request.path_info).url_name != "make_picks":
            return redirect("make_picks", join_code=join_code)

        return view_func(request, join_code, *args, **kwargs)

    return wrapper