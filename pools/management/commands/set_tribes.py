from django.core.management.base import BaseCommand

from pools.models import Contestant


class Command(BaseCommand):
    help = "Set tribe values for contestants from a predefined mapping."

    # Mapping based on the cast layout — adjust names exactly as stored in DB
    MAPPING = {
        "Cila": [
            "Christian Hubicki",
            "Cirie Fields",
            "Emily Flippen",
            "Jenna Lewis-Dougherty",
            "Joe Hunter",
            "Ozzy Lusth",
            "Rick Devens",
            "Savannah Louie",
        ],
        "Kalo": [
            "Charlie Davis",
            "Chrissy Hofbeck",
            "Benjamin \"Coach\" Wade",
            "Dee Valladares",
            "Jonathan Young",
            "Kamilla Karthigesu",
            "Mike White",
            "Tiffany Ervin",
        ],
        "Vatu": [
            "Angelina Keeley",
            "Aubry Bracco",
            "Colby Donaldson",
            "Genevieve Mushaluk",
            "Kyle Fraser",
            "Quintavius \"Q\" Burdette",
            "Rizo Velovic",
            "Stephenie LaGrossa Kendrick",
        ],
    }

    def handle(self, *args, **options):
        # Build reverse lookup (lowercased) for robust matching
        name_to_tribe = {}
        for tribe, names in self.MAPPING.items():
            for n in names:
                name_to_tribe[n.lower()] = tribe

        updated = 0
        missing = []

        for c in Contestant.objects.all():
            key = (c.name or "").strip().lower()
            tribe = name_to_tribe.get(key)
            if tribe:
                if (c.tribe or "") != tribe:
                    c.tribe = tribe
                    c.save(update_fields=["tribe"])
                    self.stdout.write(self.style.SUCCESS(f"Updated: {c.name} -> {tribe}"))
                    updated += 1
                else:
                    self.stdout.write(f"Unchanged: {c.name} already {tribe}")
            else:
                missing.append(c.name)

        self.stdout.write(self.style.SUCCESS(f"Done. {updated} contestants updated."))
        if missing:
            self.stdout.write("No mapping for the following contestants (left unchanged):")
            for m in missing:
                self.stdout.write(f" - {m}")
