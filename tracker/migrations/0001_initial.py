from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Donor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('donor_id', models.CharField(max_length=200, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='SyncLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_sync_time', models.DateTimeField(auto_now=True)),
                ('notes', models.CharField(default='Data synced from Monday.com', max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='Lot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lot_id', models.CharField(max_length=255, unique=True)),
                ('product_type', models.CharField(blank=True, max_length=100)),
                ('packaged_by', models.CharField(blank=True, max_length=255, null=True)),
                ('packaged_date', models.DateField(blank=True, null=True)),
                ('quantity', models.IntegerField(blank=True, null=True)),
                ('fpp_date', models.DateField(blank=True, null=True)),
                ('irr_run_number', models.CharField(blank=True, max_length=100, null=True)),
                ('irr_out_date', models.DateField(blank=True, null=True)),
                ('qc_out_number', models.CharField(blank=True, max_length=100, null=True)),
                ('qc_out_reason', models.TextField(blank=True, null=True)),
                ('donor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lots', to='tracker.donor')),
            ],
        ),
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(max_length=100)),
                ('event_date', models.DateTimeField()),
                ('technician', models.CharField(blank=True, max_length=100, null=True)),
                ('lot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='tracker.lot')),
            ],
        ),
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('document_type', models.CharField(max_length=100)),
                ('file', models.FileField(upload_to='donor_documents/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('donor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='tracker.donor')),
            ],
        ),
    ]