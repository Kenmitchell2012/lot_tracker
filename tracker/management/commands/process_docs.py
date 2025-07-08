# tracker/management/commands/process_docs.py

import os
from django.core.management.base import BaseCommand
from django.core.files import File
from django.conf import settings
from tracker.models import Donor, Document

class Command(BaseCommand):
    help = 'Scans a directory for new documents and associates them with donors.'

    def handle(self, *args, **options):
        hot_folder_path = os.path.join(settings.BASE_DIR, 'scanned_documents', 'new')
        self.stdout.write(f"Scanning for new documents in: {hot_folder_path}")

        try:
            document_files = [f for f in os.listdir(hot_folder_path) if f.lower().endswith('.pdf')]
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"Directory not found: {hot_folder_path}"))
            return

        if not document_files:
            self.stdout.write("No new documents found.")
            return

        for filename in document_files:
            try:
                donor_id_str, doc_type = os.path.splitext(filename)[0].split('-', 1)
            except ValueError:
                self.stdout.write(self.style.WARNING(f"Skipping '{filename}': incorrect format."))
                continue

            try:
                donor = Donor.objects.get(donor_id=donor_id_str.strip())
            except Donor.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Skipping '{filename}': Donor '{donor_id_str}' not found."))
                continue

            if Document.objects.filter(donor=donor, document_type=doc_type.replace('_', ' ').title()).exists():
                 self.stdout.write(self.style.NOTICE(f"Skipping '{filename}': Document of this type already exists."))
                 continue

            file_path = os.path.join(hot_folder_path, filename)
            with open(file_path, 'rb') as f:
                doc = Document(
                    donor=donor,
                    document_type=doc_type.replace('_', ' ').title()
                )
                # Django's FileField will automatically save this to 'media/donor_documents/'
                doc.file.save(filename, File(f), save=True)
                self.stdout.write(self.style.SUCCESS(f"Successfully associated '{filename}' with Donor '{donor.donor_id}'."))
            
            # Delete the original file from the 'new' folder
            os.remove(file_path)

        self.stdout.write("Document processing complete.")