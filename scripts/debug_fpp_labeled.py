# tracker/scripts/debug_fpp_labeled.py

from datetime import date
from collections import OrderedDict
from django.db.models import Sum
from django.utils.timezone import now
from tracker.models import Lot, SubLot

def subtract_months(dt, months):
    year = dt.year
    month = dt.month - months
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)

def run():
    today = now().date().replace(day=1)
    full_months = OrderedDict()

    for i in range(12):
        month_start = subtract_months(today, 11 - i)
        next_month = subtract_months(today, 10 - i)

        label = month_start.strftime('%b %Y')

        fpp_total = Lot.objects.filter(
            fpp_date__gte=month_start,
            fpp_date__lt=next_month
        ).aggregate(total=Sum('quantity'))['total'] or 0

        labeled_total = SubLot.objects.filter(
            labeled_date__gte=month_start,
            labeled_date__lt=next_month
        ).aggregate(total=Sum('final_quantity'))['total'] or 0

        full_months[label] = {'fpp': fpp_total, 'labeled': labeled_total}

    for label, data in full_months.items():
        print(f"{label}: FPP’d = {data['fpp']}, Labeled = {data['labeled']}")
