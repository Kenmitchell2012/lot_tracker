# tracker/management/commands/delete_placeholders.py

from django.core.management.base import BaseCommand
from tracker.models import Lot

class Command(BaseCommand):
    help = 'Deletes all Lot objects created as placeholders by the labeling sync.'

    def handle(self, *args, **options):
        # Find all lots that were marked as placeholders
        placeholders_to_delete = Lot.objects.filter(data_source='PLACEHOLDER')
        count = placeholders_to_delete.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('No placeholder lots found to delete.'))
            return

        # Ask for confirmation before deleting, as a safety measure
        confirm = input(f'This will delete {count} placeholder lots. Are you sure? (yes/no): ')

        if confirm.lower() != 'yes':
            self.stdout.write(self.style.ERROR('Deletion cancelled.'))
            return

        # Delete the objects
        placeholders_to_delete.delete()
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} placeholder lots.'))