from pathlib import Path

from django.core.management.base import BaseCommand

from imports.services import import_archive


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("archive_dir", nargs="?", default="/data")

    def handle(self, *args, **options):
        batch = import_archive(Path(options["archive_dir"]))
        self.stdout.write(self.style.SUCCESS(f"Import batch {batch.pk}: {batch.status}"))
