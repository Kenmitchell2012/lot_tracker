# tracker/urls.py
from django.urls import path
from . import views

app_name = 'tracker'

urlpatterns = [
    # Main page: lists all donors
    path('', views.donor_list, name='donor_list'),
    
    # Page for a single donor (shows all their lots)
    # This path captures the ID as 'donor_id' to match the view
    path('donor/<int:donor_id>/', views.donor_detail, name='donor_detail'),
    
    # Page for a single lot (shows its timeline)
    # This path correctly captures the ID as 'lot_id'
    path('lot/<int:lot_id>/', views.lot_detail, name='lot_detail'),
    
    # Action URLs
    path('sync/', views.sync_with_monday, name='sync_with_monday'),
    # path('upload/', views.csv_upload, name='csv_upload'),

    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/upload/', views.batch_document_upload, name='batch_document_upload'),
    path('dashboard/clear/', views.clear_new_folder, name='clear_new_folder'),
    path('reports/', views.report_list, name='report_list'),
    path('reports/<int:report_id>/', views.report_detail, name='report_detail'),
    path('dashboard/sync-labels/', views.sync_labeling_data_view, name='sync_labeling_data'),
    path('reports/labeled-lots/', views.labeled_lot_list, name='labeled_lot_list'),
    path('sub-lot/<int:sub_lot_id>/', views.sub_lot_detail, name='sub_lot_detail')
]