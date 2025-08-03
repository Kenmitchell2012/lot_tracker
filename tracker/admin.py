from django.contrib import admin
from .models import Lot, Document, Event, Donor, SyncLog, ActivityLog, Report, SubLot, MonthlyBoard

admin.site.register(Lot)
admin.site.register(Document)
admin.site.register(Event)
admin.site.register(Donor)
admin.site.register(SubLot)

@admin.register(MonthlyBoard)
class MonthlyBoardAdmin(admin.ModelAdmin):
    list_display = ('name', 'board_id', 'year', 'month', 'last_synced')
    list_filter = ('year',)
    search_fields = ('name', 'board_id')


class SubLotAdmin(admin.ModelAdmin):
    list_display = ('sub_lot_id', 'lot', 'product_type', 'status', 'due_date')
    list_filter = ('lot', 'status')
    search_fields = ('sub_lot_id', 'lot__lot_id', 'product_type')