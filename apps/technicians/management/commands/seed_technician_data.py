"""
Management command to seed skills and service regions.

Usage:
    python manage.py seed_technician_data
    python manage.py seed_technician_data --skills-only
    python manage.py seed_technician_data --regions-only
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.jobs.models import Skill
from apps.technicians.models import ServiceRegion


# ═══════════════════════════════════════════════════════════════════════════════
# SKILLS DATA
# ═══════════════════════════════════════════════════════════════════════════════

SKILLS_DATA = [
    # General Cleaning
    {
        "key": "general.basic_cleaning",
        "label": "Basic Cleaning",
        "category": "General Cleaning",
    },
    {"key": "general.dusting", "label": "Dusting", "category": "General Cleaning"},
    {"key": "general.vacuuming", "label": "Vacuuming", "category": "General Cleaning"},
    {"key": "general.mopping", "label": "Mopping & Floor Care", "category": "General Cleaning"},
    {"key": "general.surface_cleaning", "label": "Surface Cleaning", "category": "General Cleaning"},
    {"key": "general.trash_removal", "label": "Trash Removal", "category": "General Cleaning"},

    # Deep Cleaning
    {"key": "deep.full_deep_clean", "label": "Full Deep Clean", "category": "Deep Cleaning"},
    {"key": "deep.move_in_out", "label": "Move In/Out Clean", "category": "Deep Cleaning"},
    {"key": "deep.spring_clean", "label": "Spring/Seasonal Clean", "category": "Deep Cleaning"},
    {"key": "deep.post_construction", "label": "Post-Construction Clean", "category": "Deep Cleaning"},
    {"key": "deep.post_event", "label": "Post-Event Clean", "category": "Deep Cleaning"},

    # Kitchen
    {"key": "kitchen.general", "label": "Kitchen General Clean", "category": "Kitchen"},
    {"key": "kitchen.oven", "label": "Oven Cleaning", "category": "Kitchen"},
    {"key": "kitchen.refrigerator", "label": "Refrigerator Cleaning", "category": "Kitchen"},
    {"key": "kitchen.dishwasher", "label": "Dishwasher Cleaning", "category": "Kitchen"},
    {"key": "kitchen.cabinets", "label": "Cabinet Interior Cleaning", "category": "Kitchen"},
    {"key": "kitchen.countertops", "label": "Countertop Deep Clean", "category": "Kitchen"},
    {"key": "kitchen.backsplash", "label": "Backsplash & Tile Cleaning", "category": "Kitchen"},

    # Bathroom
    {"key": "bathroom.general", "label": "Bathroom General Clean", "category": "Bathroom"},
    {"key": "bathroom.deep_clean", "label": "Bathroom Deep Clean", "category": "Bathroom"},
    {"key": "bathroom.grout", "label": "Grout Cleaning", "category": "Bathroom"},
    {"key": "bathroom.shower_detail", "label": "Shower/Tub Detail", "category": "Bathroom"},
    {"key": "bathroom.toilet_sanitize", "label": "Toilet Sanitization", "category": "Bathroom"},
    {"key": "bathroom.mirror_glass", "label": "Mirror & Glass Polish", "category": "Bathroom"},

    # Laundry & Linens
    {"key": "laundry.wash_fold", "label": "Wash & Fold", "category": "Laundry & Linens"},
    {"key": "laundry.ironing", "label": "Ironing", "category": "Laundry & Linens"},
    {"key": "laundry.linen_change", "label": "Bed Linen Change", "category": "Laundry & Linens"},
    {"key": "laundry.towel_refresh", "label": "Towel Refresh", "category": "Laundry & Linens"},

    # Organization
    {"key": "org.organizing", "label": "Organizing", "category": "Organization"},
    {"key": "org.closet", "label": "Closet Organization", "category": "Organization"},
    {"key": "org.pantry", "label": "Pantry Organization", "category": "Organization"},
    {"key": "org.garage", "label": "Garage Organization", "category": "Organization"},
    {"key": "org.declutter", "label": "Decluttering", "category": "Organization"},
    {"key": "org.drawer", "label": "Drawer Organization", "category": "Organization"},
    {"key": "org.storage", "label": "Storage Space Organization", "category": "Organization"},
    {"key": "org.kids_room", "label": "Kids Room Organization", "category": "Organization"},
    {"key": "org.home_office", "label": "Home Office Organization", "category": "Organization"},

    # Windows & Glass
    {"key": "windows.interior", "label": "Interior Window Cleaning", "category": "Windows & Glass"},
    {"key": "windows.exterior_ground", "label": "Exterior Windows (Ground Level)", "category": "Windows & Glass"},
    {"key": "windows.tracks_sills", "label": "Window Tracks & Sills", "category": "Windows & Glass"},
    {"key": "windows.mirrors", "label": "Mirror Cleaning", "category": "Windows & Glass"},
    {"key": "windows.glass_doors", "label": "Glass Door Cleaning", "category": "Windows & Glass"},

    # Floors & Carpets
    {"key": "floors.hardwood", "label": "Hardwood Floor Care", "category": "Floors & Carpets"},
    {"key": "floors.tile_grout", "label": "Tile & Grout Cleaning", "category": "Floors & Carpets"},
    {"key": "floors.carpet_vacuum", "label": "Carpet Vacuuming", "category": "Floors & Carpets"},
    {"key": "floors.carpet_spot", "label": "Carpet Spot Cleaning", "category": "Floors & Carpets"},
    {"key": "floors.area_rugs", "label": "Area Rug Cleaning", "category": "Floors & Carpets"},

    # Specialty
    {"key": "specialty.pet_area", "label": "Pet Area Cleaning", "category": "Specialty"},
    {"key": "specialty.pet_hair", "label": "Pet Hair Removal", "category": "Specialty"},
    {"key": "specialty.allergen", "label": "Allergen Reduction Clean", "category": "Specialty"},
    {"key": "specialty.green_clean", "label": "Green/Eco Cleaning", "category": "Specialty"},
    {"key": "specialty.sanitization", "label": "Sanitization & Disinfection", "category": "Specialty"},
    {"key": "specialty.odor_removal", "label": "Odor Removal", "category": "Specialty"},

    # Appliances
    {"key": "appliance.microwave", "label": "Microwave Cleaning", "category": "Appliances"},
    {"key": "appliance.washer_dryer", "label": "Washer/Dryer Cleaning", "category": "Appliances"},
    {"key": "appliance.small_appliances", "label": "Small Appliance Cleaning", "category": "Appliances"},

    # Outdoor (Limited)
    {"key": "outdoor.patio", "label": "Patio/Deck Sweep", "category": "Outdoor"},
    {"key": "outdoor.furniture", "label": "Outdoor Furniture Wipe", "category": "Outdoor"},
    {"key": "outdoor.entryway", "label": "Entryway/Porch Clean", "category": "Outdoor"},
]


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE REGIONS DATA
# ═══════════════════════════════════════════════════════════════════════════════

SERVICE_REGIONS_DATA = [
    # New Jersey - Essex County
    {
        "key": "nj_essex_county",
        "name": "Essex County, NJ",
        "short_name": "Essex County",
        "state": "NJ",
        "metadata": {
            "type": "county",
            "state_full": "New Jersey",
            "notable_cities": ["Newark", "East Orange", "Orange", "Montclair", "Bloomfield", "Nutley", "West Orange", "Livingston", "Maplewood", "South Orange", "Millburn", "Caldwell"],
        },
    },
    # New Jersey - Morris County
    {
        "key": "nj_morris_county",
        "name": "Morris County, NJ",
        "short_name": "Morris County",
        "state": "NJ",
        "metadata": {
            "type": "county",
            "state_full": "New Jersey",
            "notable_cities": ["Morristown", "Parsippany", "Denville", "Randolph", "Roxbury", "Mount Olive", "Boonton", "Madison", "Chatham", "Dover", "Morris Plains", "Florham Park"],
        },
    },
]


class Command(BaseCommand):
    help = "Seed skills and service regions for technician onboarding"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skills-only",
            action="store_true",
            help="Only seed skills",
        )
        parser.add_argument(
            "--regions-only",
            action="store_true",
            help="Only seed service regions",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before seeding (use with caution)",
        )

    def handle(self, *args, **options):
        skills_only = options.get("skills_only")
        regions_only = options.get("regions_only")
        clear = options.get("clear")

        # Default to both if neither specified
        seed_skills = not regions_only
        seed_regions = not skills_only

        with transaction.atomic():
            if clear:
                if seed_skills:
                    deleted_skills = Skill.objects.all().delete()
                    self.stdout.write(f"Cleared {deleted_skills[0]} existing skills")
                if seed_regions:
                    deleted_regions = ServiceRegion.objects.all().delete()
                    self.stdout.write(f"Cleared {deleted_regions[0]} existing service regions")

            if seed_skills:
                self._seed_skills()

            if seed_regions:
                self._seed_regions()

        self.stdout.write(self.style.SUCCESS("Seeding complete!"))

    def _seed_skills(self):
        created = 0
        updated = 0

        for skill_data in SKILLS_DATA:
            skill, was_created = Skill.objects.update_or_create(
                key=skill_data["key"],
                defaults={
                    "label": skill_data["label"],
                    "category": skill_data["category"],
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(f"Skills: {created} created, {updated} updated")

        # Print categories summary
        categories = Skill.objects.filter(is_active=True).values_list(
            "category", flat=True
        ).distinct()
        self.stdout.write(f"Categories: {', '.join(sorted(categories))}")

    def _seed_regions(self):
        created = 0
        updated = 0

        for region_data in SERVICE_REGIONS_DATA:
            region, was_created = ServiceRegion.objects.update_or_create(
                key=region_data["key"],
                defaults={
                    "name": region_data["name"],
                    "short_name": region_data.get("short_name", ""),
                    "state": region_data["state"],
                    "metadata": region_data.get("metadata", {}),
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(f"Service regions: {created} created, {updated} updated")

        # Print states summary
        states = ServiceRegion.objects.filter(is_active=True).values_list(
            "state", flat=True
        ).distinct()
        self.stdout.write(f"States: {', '.join(sorted(states))}")
