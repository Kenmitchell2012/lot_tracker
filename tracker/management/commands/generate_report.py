from django.core.management.base import BaseCommand
from django.db.models import Sum
from tracker.models import Lot, SubLot, Report

class Command(BaseCommand):
    help = 'Generates the monthly production report and saves it to the database.'

    def add_arguments(self, parser):
        parser.add_argument('month', type=int, help='The month number (1-12)')
        parser.add_argument('year', type=int, help='The year (e.g., 2025)')

    def handle(self, *args, **options):
        month, year = options['month'], options['year']
        self.stdout.write(f"--- Generating report for {month}/{year} ---")

        # 1. Grafts Produced (based on Lot's packaged_date)
        grafts_produced = Lot.objects.filter(
            packaged_date__year=year,
            packaged_date__month=month
        ).values('product_type').annotate(total=Sum('quantity')).order_by('product_type')

        # 2. Grafts Sent to Irradiation (based on Lot's irr_out_date)
        grafts_irradiated = Lot.objects.filter(
            irr_out_date__year=year,
            irr_out_date__month=month
        ).values('product_type').annotate(total=Sum('quantity')).order_by('product_type')
        
        # --- THIS IS THE FIX ---
        # 3. Grafts Labeled (based on SubLot's labeled_date)
        # This query now starts from the SubLot model and looks up to the parent Lot
        grafts_labeled = SubLot.objects.filter(
            labeled_date__year=year,
            labeled_date__month=month
        ).values('parent_lot__product_type').annotate(total=Sum('parent_lot__quantity')).order_by('parent_lot__product_type')
        # --------------------

        # To make the data consistent, we rename the key for the labeled grafts
        # from 'parent_lot__product_type' to 'product_type'
        grafts_labeled_cleaned = [
            {'product_type': item['parent_lot__product_type'], 'total': item['total']} 
            for item in grafts_labeled
        ]

        # Compile the final data into a dictionary
        report_data = {
            'produced': list(grafts_produced),
            'irradiated': list(grafts_irradiated),
            'labeled': grafts_labeled_cleaned,
        }

        # Save the report to the database
        report_obj, created = Report.objects.update_or_create(
            month=month,
            year=year,
            defaults={'report_data': report_data}
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"Successfully created new report for {month}/{year}."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully updated existing report for {month}/{year}."))