# tracker/management/commands/process_docs.py

import os
import shutil
from django.core.management.base import BaseCommand
from django.core.files import File
from django.conf import settings
from tracker.models import Donor, Document

class Command(BaseCommand):
    help = 'Scans a directory for new documents, associates them with donors, and moves them.'

    def handle(self, *args, **options):
        # Define the paths for your "hot folder"
        hot_folder_path = os.path.join(settings.BASE_DIR, 'scanned_documents', 'new')
        processed_folder_path = os.path.join(settings.BASE_DIR, 'scanned_documents', 'processed')

        self.stdout.write(f"Scanning for new documents in: {hot_folder_path}")

        # Get a list of all files in the 'new' directory
        try:
            document_files = [f for f in os.listdir(hot_folder_path) if f.lower().endswith('.pdf')]
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"Directory not found: {hot_folder_path}. Please create it."))
            return

        if not document_files:
            self.stdout.write("No new documents found.")
            return

        # Process each file found
        for filename in document_files:
            # Assumes filename format is "DONORID_DOCTYPE.pdf" e.g., "CRT241002_Irradiation.pdf"
            try:
                donor_id_str, doc_type = os.path.splitext(filename)[0].split('-', 1)
            except ValueError:
                self.stdout.write(self.style.WARNING(f"Skipping '{filename}': incorrect format. Expected 'DONORID_DOCTYPE.pdf'."))
                continue

            # Find the corresponding donor in the database
            try:
                donor = Donor.objects.get(donor_id=donor_id_str.strip())
            except Donor.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Skipping '{filename}': Donor '{donor_id_str}' not found in database."))
                continue

            # Create the Document record
            file_path = os.path.join(hot_folder_path, filename)
            with open(file_path, 'rb') as f:
                django_file = File(f)
                
                # Check if this exact document already exists for this donor
                if Document.objects.filter(donor=donor, document_type=doc_type).exists():
                    self.stdout.write(self.style.NOTICE(f"Skipping '{filename}': A document of this type already exists for this donor."))
                else:
                    doc = Document()
                    doc.donor = donor
                    doc.document_type = doc_type.replace('_', ' ').title() # Makes 'processing_ppw' into 'Processing Ppw'
                    doc.file.save(filename, django_file, save=True)
                    self.stdout.write(self.style.SUCCESS(f"Successfully associated '{filename}' with Donor '{donor.donor_id}'."))

            # Move the processed file to the 'processed' directory
            shutil.move(file_path, os.path.join(processed_folder_path, filename))

        self.stdout.write("Document processing complete.")