from django.urls import path
from . import views

app_name = 'tracker'

urlpatterns = [
    # 🔹 Main Command Center
    path('', views.command_center, name='command_center'),

    # 🔹 Donor and Lot Views
    path('donors/', views.donor_list, name='donor_list'),
    path('donor/<int:donor_id>/', views.donor_detail, name='donor_detail'),
    path('lot/<int:lot_id>/', views.lot_detail, name='lot_detail'),
    path('sub-lot/<int:sub_lot_id>/', views.sub_lot_detail, name='sub_lot_detail'),

    # 🔹 Reports
    path('reports/', views.report_list, name='report_list'),
    path('reports/<int:report_id>/', views.report_detail, name='report_detail'),
    path('reports/<int:report_id>/delete/', views.delete_report, name='delete_report'),
    path('reports/labeled-lots/', views.labeled_lot_list, name='labeled_lot_list'),
    path('reports/interactive-data/', views.interactive_report_data, name='interactive_report_data'),
    # path('reports/export/pdf/', views.export_reports_pdf, name='export_reports_pdf'),

    # 🔹 Admin Dashboard
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/upload/', views.batch_document_upload, name='batch_document_upload'),
    path('dashboard/clear/', views.clear_new_folder, name='clear_new_folder'),
    path('sync-board/<str:board_id>/', views.sync_board, name='sync_board'),
    path('manage-boards/', views.manage_boards, name='manage_boards'),
    # 🔹 Sync
    path('sync/', views.sync_with_monday, name='sync_with_monday'),

    # 🔸 Future Features
    # path('upload/', views.csv_upload, name='csv_upload'),
]
