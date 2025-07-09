from django.db import models
from django.contrib.auth.models import User

class Donor(models.Model):
    """Represents the main Donor, the 'folder' for all related lots."""
    donor_id = models.CharField(max_length=200, unique=True)
    # You can add other donor-level fields here later if needed

    def __str__(self):
        return self.donor_id

class Lot(models.Model):
    """Represents a specific lot or product derived from a Donor."""
    donor = models.ForeignKey(Donor, related_name='lots', on_delete=models.CASCADE)
    lot_id = models.CharField(max_length=255, unique=True)
    product_type = models.CharField(max_length=100, blank=True)
    
    # --- NEW FIELDS ---
    packaged_by = models.CharField(max_length=255, blank=True, null=True)
    packaged_date = models.DateField(blank=True, null=True)
    quantity = models.IntegerField(blank=True, null=True)
    fpp_date = models.DateField(blank=True, null=True)
    irr_run_number = models.CharField(max_length=100, blank=True, null=True)
    irr_out_date = models.DateField(blank=True, null=True)
    qc_out_number = models.CharField(max_length=100, blank=True, null=True)
    qc_out_reason = models.TextField(blank=True, null=True)
    # --- END NEW FIELDS ---

    # We can remove these fields as they are now more specific above
    # date_processed = models.DateField(null=True, blank=True)
    # status = models.CharField(max_length=50, default='In-Process')

    def __str__(self):
        return self.lot_id

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