from django.core.management.base import BaseCommand
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import date
from tracker.models import Lot, SubLot, Report

class Command(BaseCommand):
    help = 'Generates or updates the 13-month trend report data.'

    def handle(self, *args, **options):
        self.stdout.write('Starting 13-month trend report generation...')

        # --- Date calculations (This part is correct) ---
        today = timezone.localdate()
        start_of_this_month = today.replace(day=1)

        def subtract_months(dt, months_to_subtract):
            year, month = dt.year, dt.month - months_to_subtract
            while month <= 0:
                month += 12
                year -= 1
            return date(year, month, 1)

        thirteen_months_ago_start = subtract_months(start_of_this_month, 12)

        # --- Queries for Monthly Trend Data ---
        packaged_qs = Lot.objects.filter(
            packaged_date__isnull=False, packaged_date__gte=thirteen_months_ago_start
        ).annotate(month=TruncMonth('packaged_date')).values('month').annotate(total=Sum('quantity')).order_by('month')

        # --- THIS IS THE CORRECTED QUERY ---
        # It now uses Q objects for a precise date range filter on the source_board's year and month.
        labeled_trend_qs = SubLot.objects.filter(
            source_board__isnull=False
        ).filter(
            Q(source_board__year__gt=thirteen_months_ago_start.year) |
            Q(source_board__year=thirteen_months_ago_start.year, source_board__month__gte=thirteen_months_ago_start.month)
        ).values(
            'source_board__year', 'source_board__month'
        ).annotate(
            total=Sum('final_quantity')
        ).order_by('source_board__year', 'source_board__month')
        
        fpp_qs = Lot.objects.filter(
            fpp_date__isnull=False, fpp_date__gte=thirteen_months_ago_start
        ).annotate(month=TruncMonth('fpp_date')).values('month').annotate(total=Sum('quantity')).order_by('month')

        # Convert all date/datetime objects to strings for JSON
        packaged_trend = [{'month': item['month'].isoformat(), 'total': item['total']} for item in packaged_qs]
        
        labeled_trend = [
            {'month': date(item['source_board__year'], item['source_board__month'], 1).isoformat(), 'total': item['total']}
            for item in labeled_trend_qs
        ]
        
        fpp_trend = [{'month': item['month'].isoformat(), 'total': item['total']} for item in fpp_qs]

        # --- Save the data ---
        report_data = {
            'packaged_trend': packaged_trend,
            'labeled_trend': labeled_trend,
            'fpp_trend': fpp_trend,
        }
        
        report, created = Report.objects.update_or_create(
            id=1,
            defaults={
                'month': today.month,
                'year': today.year,
                'report_data': report_data
            }
        )
        if not created:
            report.generated_at = timezone.now()
            report.save(update_fields=['generated_at'])

        self.stdout.write(self.style.SUCCESS('Successfully generated and saved the 13-month trend report.'))