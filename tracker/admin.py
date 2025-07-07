from django.contrib import admin
from .models import Lot, Document, Event, Donor, SyncLog

admin.site.register(Lot)
admin.site.register(Document)
admin.site.register(Event)
admin.site.register(Donor)