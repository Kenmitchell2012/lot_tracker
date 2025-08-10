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
    product_code = models.CharField(max_length=100, blank=True, null=True)
    graft_id_number = models.TextField(blank=True, null=True)
    
    # --- Processing Status Fields ---
    status = models.CharField(max_length=100, blank=True, null=True)
    sterilization = models.CharField(max_length=100, blank=True, null=True)
    qc_out_number = models.IntegerField(blank=True, null=True)
    qc_out_reason = models.CharField(max_length=255, blank=True, null=True)
    da_val = models.BooleanField(default=False, help_text="Represents the 'DA / VAL' checkbox")
    
    # --- Packaging and Quantity Fields ---
    packaged_by = models.CharField(max_length=255, blank=True, null=True)
    packaged_date = models.DateField(blank=True, null=True)
    quantity = models.IntegerField(blank=True, null=True)

    # --- Release Date Fields ---
    fpp_by = models.CharField(max_length=255, blank=True, null=True)
    fpp_date = models.DateField(blank=True, null=True) 
    irr_out_date = models.DateField(blank=True, null=True)
    irr_run_number = models.CharField(max_length=255, blank=True, null=True)
    irr_return_date = models.DateField(blank=True, null=True)
    
    data_source = models.CharField(
        max_length=20, 
        choices=DATA_SOURCE_CHOICES, 
        default='PRIMARY_SYNC'
    )

    def __str__(self):
        return self.lot_id
    
class MonthlyBoard(models.Model):
    board_id = models.CharField(max_length=20, unique=True, help_text="The ID of the Monday.com board.")
    name = models.CharField(max_length=100, help_text="e.g., 'Labeling - July 2025'")
    month = models.IntegerField()
    year = models.IntegerField()
    last_synced = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-year', '-month']
        unique_together = ('month', 'year') # Ensure only one board per month/year combo

    def __str__(self):
        return self.name

class SubLot(models.Model):
    """Represents a final LABELED lot (e.g., CRT999999-DCM-AR) and links to its parent."""
    parent_lot = models.ForeignKey(Lot, related_name='sub_lots', on_delete=models.CASCADE)
    source_board = models.ForeignKey(MonthlyBoard, related_name='sub_lots', on_delete=models.SET_NULL, null=True, blank=True)
    sub_lot_id = models.CharField(max_length=255, unique=True)
    product_type = models.CharField(max_length=100, blank=True, null=True)
    
    labeled_by = models.CharField(max_length=255, blank=True, null=True)
    labeled_date = models.DateField(blank=True, null=True)
    final_quantity = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=100, blank=True, null=True, help_text="Corresponds to 'Chart Status'")
    due_date = models.DateField(blank=True, null=True, help_text="Corresponds to 'Release Date'")
    latest_comment = models.TextField(blank=True, null=True, help_text="Stores the latest update/comment from Monday.com for this item.")
    
    product_descriptions = models.TextField(blank=True, null=True)
    create_date = models.DateField(blank=True, null=True)
    initial_quantity = models.IntegerField(blank=True, null=True, help_text="Corresponds to the 'QTY' column")
    labeling_progress = models.IntegerField(blank=True, null=True)
    labeling_status = models.CharField(max_length=100, blank=True, null=True, help_text="Corresponds to the 'Labeling' status")
    qc_status = models.CharField(max_length=100, blank=True, null=True, help_text="Corresponds to the 'QC' status")
    days_to_label = models.CharField(max_length=50, blank=True, null=True)
    days_to_release = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.sub_lot_id
    
    @property
    def calculated_days_to_label(self):
        if self.parent_lot and self.parent_lot.packaged_date and self.labeled_date:
            return (self.labeled_date - self.parent_lot.packaged_date).days
        return None

    @property
    def calculated_days_to_release(self):
        if self.create_date and self.due_date:
            return (self.due_date - self.create_date).days
        return None

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
    """Logs the outcome of a data sync operation."""
    timestamp = models.DateTimeField(auto_now_add=True)
    # Add null=True to the new fields
    board_id = models.CharField(max_length=20, null=True)
    status = models.CharField(max_length=50, null=True)
    details = models.TextField(blank=True, null=True) # Also good to add null=True here

    def __str__(self):
        # Updated to handle possible null board_id
        return f"Sync for board {self.board_id or 'N/A'} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"



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
    
