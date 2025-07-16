from django.db import models
from django.contrib.auth.models import User

class Donor(models.Model):
    donor_id = models.CharField(max_length=200, unique=True)
    def __str__(self):
        return self.donor_id

class Lot(models.Model):
    """Represents a single lot with all of its data."""
    DATA_SOURCE_CHOICES = [
        ('PRIMARY_SYNC', 'Primary Sync'),
        ('PLACEHOLDER', 'Placeholder'),
    ]

    donor = models.ForeignKey(Donor, related_name='lots', on_delete=models.CASCADE)
    lot_id = models.CharField(max_length=255, unique=True)
    product_type = models.CharField(max_length=100, blank=True)
    
    # --- All Data Fields ---
    packaged_by = models.CharField(max_length=255, blank=True, null=True)
    packaged_date = models.DateField(blank=True, null=True)
    quantity = models.IntegerField(blank=True, null=True)
    fpp_date = models.DateField(blank=True, null=True) 
    irr_out_date = models.DateField(blank=True, null=True)
    
    data_source = models.CharField(
        max_length=20, 
        choices=DATA_SOURCE_CHOICES, 
        default='PRIMARY_SYNC'
    )

    def __str__(self):
        return self.lot_id

class SubLot(models.Model):
    """Represents a final LABELED lot (e.g., CRT999999-DCM-AR) and links to its parent."""
    parent_lot = models.ForeignKey(Lot, related_name='sub_lots', on_delete=models.CASCADE)
    sub_lot_id = models.CharField(max_length=255, unique=True)
    labeled_by = models.CharField(max_length=255, blank=True, null=True)
    labeled_date = models.DateField(blank=True, null=True)
    final_quantity = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.sub_lot_id

class Document(models.Model):
    """Represents a file (NCR, etc.) associated with a specific Donor."""
    # Change this ForeignKey to point to Donor
    donor = models.ForeignKey(Donor, related_name='documents', on_delete=models.CASCADE)
    document_type = models.CharField(max_length=100)
    file = models.FileField(upload_to='donor_documents/') # Changed upload path
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.document_type} for {self.donor.donor_id}"

class Event(models.Model):
    """Tracks a milestone for a specific Lot."""
    lot = models.ForeignKey(Lot, related_name='events', on_delete=models.CASCADE)
    event_type = models.CharField(max_length=100)
    event_date = models.DateTimeField()
    technician = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.event_type} for {self.lot.lot_id}"
    
class SyncLog(models.Model):
    """A simple model to log the timestamp of the last successful sync."""
    last_sync_time = models.DateTimeField(auto_now=True)
    notes = models.CharField(max_length=255, default="Data synced from Monday.com")

    def __str__(self):
        return f"Last synced on {self.last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}"



class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action_type = models.CharField(max_length=255)
    details = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-timestamp',)

    def __str__(self):
        return f'{self.action_type} by {self.user.username if self.user else "System"} at {self.timestamp}'
    
class Report(models.Model):
    """Stores the generated data from a monthly report."""
    month = models.IntegerField()
    year = models.IntegerField()
    generated_at = models.DateTimeField(auto_now_add=True)
    report_data = models.JSONField()

    class Meta:
        # Ensures you can't have two reports for the same month and year
        unique_together = ('month', 'year')
        ordering = ('-year', '-month')

    def __str__(self):
        return f"Report for {self.month}/{self.year}"