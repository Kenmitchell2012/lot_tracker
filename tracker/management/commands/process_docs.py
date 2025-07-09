import os
import shutil
import re
from django.core.management.base import BaseCommand
from django.core.files import File
from django.conf import settings
from tracker.models import Donor, Document

class Command(BaseCommand):
    help = 'Scans a directory for new documents and associates them with donors.'

    def handle(self, *args, **options):
        hot_folder_path = os.path.join(settings.BASE_DIR, 'scanned_documents', 'new')
        # This logic assumes you are using the 'processed' folder workflow
        processed_folder_path = os.path.join(settings.BASE_DIR, 'scanned_documents', 'processed')

        self.stdout.write(f"Scanning for new documents in: {hot_folder_path}")

        try:
            document_files = [f for f in os.listdir(hot_folder_path) if f.lower().endswith('.pdf')]
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"Directory not found: {hot_folder_path}."))
            return

        if not document_files:
            self.stdout.write("No new documents found.")
            return

        for filename in document_files:
            basename = os.path.splitext(filename)[0]

            try:
                # === UPDATED PARSING LOGIC ===
                # This now correctly handles your filename format like 'CRT250011 MS FRZ-ST'
                parts = re.split('([A-Z]{3}\\d+)', basename, 1)
                if len(parts) < 3:
                    raise ValueError("Filename does not match expected format.")
                
                donor_id_str = parts[1] # e.g., 'CRT250011'
                doc_type = parts[2].strip() # e.g., 'MS FRZ-ST'
                # ===========================
            except (ValueError, IndexError):
                self.stdout.write(self.style.WARNING(f"Skipping '{filename}': incorrect format."))
                continue

            try:
                donor = Donor.objects.get(donor_id=donor_id_str.strip())
            except Donor.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Skipping '{filename}': Donor '{donor_id_str}' not found in database."))
                continue

            file_path = os.path.join(hot_folder_path, filename)
            with open(file_path, 'rb') as f:
                django_file = File(f)
                
                doc_type_cleaned = doc_type.replace('_', ' ').replace('-', ' ').title()
                if Document.objects.filter(donor=donor, document_type=doc_type_cleaned).exists():
                    self.stdout.write(self.style.NOTICE(f"Skipping '{filename}': Document of this type already exists for this donor."))
                else:
                    doc = Document(
                        donor=donor,
                        document_type=doc_type_cleaned
                    )
                    doc.file.save(filename, django_file, save=True)
                    self.stdout.write(self.style.SUCCESS(f"Successfully associated '{filename}' with Donor '{donor.donor_id}'."))
            
            # Move the file to the processed folder
            shutil.move(file_path, os.path.join(processed_folder_path, filename))

        self.stdout.write("Document processing complete.")