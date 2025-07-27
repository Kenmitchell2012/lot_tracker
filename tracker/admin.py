from django.contrib import admin
from .models import Lot, Document, Event, Donor, SyncLog, ActivityLog, Report, SubLot, MonthlyBoard

admin.site.register(Lot)
admin.site.register(Document)
admin.site.register(Event)
admin.site.register(Donor)

@admin.register(MonthlyBoard)
class MonthlyBoardAdmin(admin.ModelAdmin):
    list_display = ('name', 'board_id', 'year', 'month', 'last_synced')
    list_filter = ('year',)
    search_fields = ('name', 'board_id')