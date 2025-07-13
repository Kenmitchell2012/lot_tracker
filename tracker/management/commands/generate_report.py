import datetime
from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from tracker.models import Lot, SubLot, Report

class Command(BaseCommand):
    help = 'Generates a summary report for all labeled and packaged grafts, grouped by month.'

    def handle(self, *args, **options):
        self.stdout.write("--- Generating Full History Trend Report ---")

        today = datetime.date.today()

        # --- THIS IS THE FIX ---
        # The queries no longer filter for only the last 12 months.
        # They now look at all data in your database.

        # Query 1: Packaged Grafts (from Lot model)
        packaged_by_month = Lot.objects.filter(packaged_date__isnull=False)\
            .annotate(month=TruncMonth('packaged_date')).values('month')\
            .annotate(total=Sum('quantity')).order_by('month')

        # Query 2: Labeled Grafts (from SubLot model)
        labeled_by_month = SubLot.objects.filter(labeled_date__isnull=False)\
            .annotate(month=TruncMonth('labeled_date')).values('month')\
            .annotate(total=Sum('final_quantity')).order_by('month')

        # Query 3: FPP Inspected Grafts (from Lot model)
        fpp_by_month = Lot.objects.filter(fpp_date__isnull=False)\
            .annotate(month=TruncMonth('fpp_date')).values('month')\
            .annotate(total=Sum('quantity')).order_by('month')
        # --- END FIX ---

        # Format the data for JSON
        report_data = {
            'packaged_trend': [{'month': item['month'].strftime('%Y-%m-%d'), 'total': item['total']} for item in packaged_by_month],
            'labeled_trend': [{'month': item['month'].strftime('%Y-%m-%d'), 'total': item['total']} for item in labeled_by_month],
            'fpp_trend': [{'month': item['month'].strftime('%Y-%m-%d'), 'total': item['total']} for item in fpp_by_month],
        }

        # Always save to a single report object with a fixed ID
        Report.objects.update_or_create(
            id=1, 
            defaults={
                'month': today.month, 'year': today.year,
                'report_data': report_data
            }
        )
        self.stdout.write(self.style.SUCCESS("Successfully created/updated the Full History Trend Report."))