from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.db.models import Q, F


class Season(models.Model):
    """
    A Survivor season (e.g., 'Survivor 50').
    """
    name = models.CharField(max_length=100, unique=True)   # "Survivor 50"
    slug = models.SlugField(max_length=120, unique=True)   # "survivor-50"
    created_at = models.DateTimeField(auto_now_add=True)

    sole_survivor = models.ForeignKey(
        "pools.Contestant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="won_seasons",
    )

    def save(self, *args, **kwargs):
        # Auto-fill slug from name if not provided
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Contestant(models.Model):
    """
    A contestant in a given season.
    """
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="contestants")
    name = models.CharField(max_length=100)

    tribe = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)

    # Keep your existing "active" flag
    active = models.BooleanField(default=True)

    # Explicit eliminated flag (your template expects this)
    eliminated = models.BooleanField(default=False)

    # Photo stored under: media/cast/season-50/<filename>
    photo = models.ImageField(upload_to="cast/season-50/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("season", "name")

    def __str__(self):
        return f"{self.name}"

    @property
    def photo_url(self):
        """
        Backwards-compatible: lets templates use {{ c.photo_url }}.
        """
        if self.photo and hasattr(self.photo, "url"):
            return self.photo.url
        return ""


class Episode(models.Model):
    """
    One episode/week within a Season.
    Admin sets who was eliminated.
    """
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="episodes")
    number = models.PositiveIntegerField()  # 1, 2, 3, ...
    
    eliminated = models.ManyToManyField(Contestant,
                                        blank=True,
                                        related_name="eliminated_in_episodes",)

    class Meta:
        unique_together = ("season", "number")
        ordering = ["season", "number"]

    def __str__(self):
        return f"{self.season.name} — Episode {self.number}"


class Pool(models.Model):
    """
    A Pool is a single Survivor pool that users can join.
    """
    name = models.CharField(max_length=100)
    join_code = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="pools")

    # --- First Out lottery / draft ---
    # When True, the "first out" selection is currently underway
    first_out_draft_open = models.BooleanField(default=False)
    # When True, draft order has been generated and stored on Entry.first_out_pick_order
    first_out_draft_generated = models.BooleanField(default=False)

    # Winner of last year's pool gets to pick First Out first (if they are in this pool)
    previous_winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="previous_pool_winner_for",
    )

    def __str__(self):
        return self.name


class Entry(models.Model):
    """
    An Entry represents a user participating in a specific pool.
    """
    pool = models.ForeignKey(
        Pool,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # --- Picks (set once per season/pool) ---
    first_out = models.ForeignKey(
        Contestant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="first_out_entries",
    )
    winner_1 = models.ForeignKey(
        Contestant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="winner1_entries",
    )
    winner_2 = models.ForeignKey(
        Contestant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="winner2_entries",
    )

    # --- First Out draft position ---
    # Determined by lottery (previous winner gets #1), then randomized for others
    first_out_pick_order = models.PositiveIntegerField(null=True, blank=True)
    # Timestamp when the user successfully locked their first_out pick (optional but useful)
    first_out_picked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            # One entry per user per pool
            models.UniqueConstraint(fields=["pool", "user"], name="uniq_user_per_pool"),

            # Unique first-out per pool (ignore nulls)
            models.UniqueConstraint(
                fields=["pool", "first_out"],
                condition=Q(first_out__isnull=False),
                name="uniq_first_out_per_pool",
            ),

            # Unique draft order per pool (ignore nulls)
            models.UniqueConstraint(
                fields=["pool", "first_out_pick_order"],
                condition=Q(first_out_pick_order__isnull=False),
                name="uniq_first_out_order_per_pool",
            ),

            # Winner picks must be distinct (when both set)
            models.CheckConstraint(
                check=Q(winner_1__isnull=True) | Q(winner_2__isnull=True) | ~Q(winner_1=F("winner_2")),
                name="chk_winners_distinct",
            ),

            # First-out can't equal a winner (when set)
            models.CheckConstraint(
                check=Q(first_out__isnull=True) | Q(winner_1__isnull=True) | ~Q(first_out=F("winner_1")),
                name="chk_firstout_not_winner1",
            ),
            models.CheckConstraint(
                check=Q(first_out__isnull=True) | Q(winner_2__isnull=True) | ~Q(first_out=F("winner_2")),
                name="chk_firstout_not_winner2",
            ),
        ]

    def __str__(self):
        return f"{self.user} in {self.pool}"
