from django import forms
from .models import Entry, Contestant


class JoinPoolForm(forms.Form):
    join_code = forms.CharField(
        max_length=20,
        label="Join code",
        widget=forms.TextInput(attrs={
            "placeholder": "Enter join code",
            "autocomplete": "off",
        })
    )


class EntryPicksForm(forms.ModelForm):
    class Meta:
        model = Entry
        fields = ["winner_1", "winner_2", "first_out"]

    def __init__(self, *args, season=None, pool=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool = pool  # needed for first_out uniqueness check

        qs = Contestant.objects.none()
        if season is not None:
            qs = Contestant.objects.filter(season=season, active=True).order_by("name")

        for f in ["winner_1", "winner_2", "first_out"]:
            self.fields[f].queryset = qs
            self.fields[f].required = True

        self.fields["winner_1"].empty_label = "Select Winner 1"
        self.fields["winner_2"].empty_label = "Select Winner 2"
        self.fields["first_out"].empty_label = "Select First Out"

    def clean(self):
        cleaned = super().clean()
        w1 = cleaned.get("winner_1")
        w2 = cleaned.get("winner_2")
        fo = cleaned.get("first_out")

        if w1 and w2 and w1 == w2:
            self.add_error("winner_2", "Winner 2 must be different from Winner 1.")

        if fo and w1 and fo == w1:
            self.add_error("first_out", "First out cannot be the same as Winner 1.")

        if fo and w2 and fo == w2:
            self.add_error("first_out", "First out cannot be the same as Winner 2.")

        # ✅ Enforce "unique first_out per pool" BEFORE saving
        if self.pool and fo:
            exists = (
                Entry.objects
                .filter(pool=self.pool, first_out=fo)
                .exclude(pk=self.instance.pk)  # allow editing your own entry
                .exists()
            )
            if exists:
                self.add_error(
                    "first_out",
                    "That contestant has already been taken as First Out in this pool. Pick someone else."
                )

        return cleaned