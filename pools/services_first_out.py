import random
from django.utils import timezone
from django.db import transaction

from .models import Entry


@transaction.atomic
def generate_first_out_lottery(pool):
    """
    Sets Entry.first_out_pick_order for everyone in the pool.

    Rule:
      - previous_winner (if present AND in this pool) gets order=1
      - everyone else randomized after
    """
    entries = list(Entry.objects.select_for_update().filter(pool=pool).select_related("user"))

    if not entries:
        pool.first_out_draft_generated = True
        pool.save(update_fields=["first_out_draft_generated"])
        return []

    # Find the previous winner entry (only if they are actually in the pool)
    winner_entry = None
    rest = []

    for e in entries:
        if pool.previous_winner_id and e.user_id == pool.previous_winner_id:
            winner_entry = e
        else:
            rest.append(e)

    random.shuffle(rest)

    ordered = ([winner_entry] if winner_entry else []) + rest

    for idx, e in enumerate(ordered, start=1):
        e.first_out_pick_order = idx
        e.save(update_fields=["first_out_pick_order"])

    pool.first_out_draft_generated = True
    pool.first_out_draft_open = True
    pool.save(update_fields=["first_out_draft_generated", "first_out_draft_open"])

    return ordered


def get_current_first_out_turn_entry(pool):
    """
    Returns the Entry whose turn it is to pick first_out, or None if draft complete/closed.
    """
    if not pool.first_out_draft_open:
        return None

    qs = Entry.objects.filter(pool=pool).order_by("first_out_pick_order", "created_at")

    for e in qs:
        if e.first_out is None:
            return e
    return None


@transaction.atomic
def submit_first_out_pick(pool, user, contestant):
    """
    Enforces turn order + saves first_out for the user's Entry.
    """
    entry = Entry.objects.select_for_update().get(pool=pool, user=user)

    # Draft must be generated/open
    if not pool.first_out_draft_open or not pool.first_out_draft_generated:
        raise ValueError("First Out draft is not open.")

    # Must be this user's turn
    current = get_current_first_out_turn_entry(pool)
    if not current or current.user_id != user.id:
        raise PermissionError("Not your turn to pick First Out.")

    # Must not already have a first_out
    if entry.first_out_id is not None:
        raise ValueError("You already selected your First Out.")

    # Enforce same-season contestant (safety)
    if contestant.season_id != pool.season_id:
        raise ValueError("That contestant is not in this pool's season.")

    # DB constraint already enforces uniqueness, but we can pre-check for nicer error
    if Entry.objects.filter(pool=pool, first_out=contestant).exists():
        raise ValueError("That contestant has already been chosen as a First Out pick.")

    entry.first_out = contestant
    entry.first_out_picked_at = timezone.now()
    entry.save(update_fields=["first_out", "first_out_picked_at"])

    # If everyone has picked, close draft
    if not Entry.objects.filter(pool=pool, first_out__isnull=True).exists():
        pool.first_out_draft_open = False
        pool.save(update_fields=["first_out_draft_open"])

    return entry
