import logging
import requests
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from .models import Donor, Lot, Document, Event, SyncLog, ActivityLog, Report, SubLot
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.contrib.auth.decorators import login_required
from .forms import DocumentForm, SignUpForm, LoginForm
from django.contrib.auth.views import LoginView
from django.contrib.auth import logout
from django.contrib.auth import login, authenticate
from django.shortcuts import render, redirect
from .forms import DocumentForm # <-- Import the new form
from django.db.models import Sum, Case, When, IntegerField
from django.db.models.functions import TruncMonth
from django.utils.dateformat import DateFormat
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from django.template.loader import render_to_string
import tempfile



# admin imports
import os
from django.conf import settings
from django.core.management import call_command
from django.contrib.auth.decorators import user_passes_test
import io
import shutil

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# Setup logger
logger = logging.getLogger(__name__)


# Set rolling 12-month window
today = now().date()
one_year_ago = today - timedelta(days=365)

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Welcome, {user.username}! Your account was created successfully.")
            # Automatically log in the user after signup
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
            else:
                messages.error(request, 'There was an error logging you in after signup. Please try logging in manually.')
            return redirect('tracker:donor_list')  # Redirect to donor list after signup
    else:
        form = SignUpForm()

    return render(request, 'core/signup.html', {'form': form})

class CustomLoginView(LoginView):
    authentication_form = LoginForm
    template_name = 'core/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        # This method is called after a user successfully logs in
        messages.success(self.request, f"Welcome back, {self.request.user.username}!")
        return super().form_valid(form)


# NEW custom logout view to add a success message
@login_required
def custom_logout(request):
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('login')

@user_passes_test(lambda u: u.is_staff)
def admin_dashboard(request):
    """
    Displays an admin dashboard with a file count, an activity log,
    and buttons to process or clear the document upload folder.
    """
    new_docs_path = os.path.join(settings.BASE_DIR, 'scanned_documents', 'new')
    
    # This block handles the "Run Processing Script" button press
    if request.method == 'POST':
        try:
            # Create an in-memory text buffer to capture the command's output
            output_buffer = io.StringIO()
            
            # Run the command, redirecting its output to our buffer
            call_command('process_docs', stdout=output_buffer)
            
            # Get the captured output from the buffer
            command_output = output_buffer.getvalue()
            
            # Add each line of the output as a separate message
            output_lines = command_output.strip().split('\n')
            for line in output_lines:
                if "Successfully" in line:
                    messages.success(request, line)
                elif "Skipping" in line or "WARNING" in line or "NOTICE" in line:
                    messages.warning(request, line)
                else:
                    messages.info(request, line)
            
            # --- This is the new ActivityLog entry ---
            # Only create a log if the script actually did something
            if len(output_lines) > 1: # More than just the initial "Scanning..." message
                ActivityLog.objects.create(
                    user=request.user,
                    action_type="Bulk Process Triggered",
                    details=f"Ran the document processing script. Result: {output_lines[-1]}"
                )
            # -----------------------------------------

        except Exception as e:
            messages.error(request, f"An error occurred while running the script: {e}")
        
        return redirect('tracker:admin_dashboard')

    # For a normal page load, get the file count and activity logs
    try:
        files_to_process_count = len([f for f in os.listdir(new_docs_path) if f.lower().endswith('.pdf')])
    except FileNotFoundError:
        files_to_process_count = 0
        messages.warning(request, f"The directory '{new_docs_path}' was not found.")

    activity_logs = ActivityLog.objects.all()[:15] # Get the 15 most recent logs

    context = {
        'files_to_process_count': files_to_process_count,
        'activity_logs': activity_logs,
    }
    return render(request, 'tracker/admin_dashboard.html', context)

@user_passes_test(lambda u: u.is_staff)
def clear_new_folder(request):
    """
    On POST, moves all files from the 'new' folder to an 'errors'
    folder and creates an activity log entry.
    """
    if request.method == 'POST':
        new_folder_path = os.path.join(settings.BASE_DIR, 'scanned_documents', 'new')
        errors_folder_path = os.path.join(settings.BASE_DIR, 'scanned_documents', 'errors')
        
        files_cleared = 0
        try:
            files_to_clear = [f for f in os.listdir(new_folder_path) if f.lower().endswith('.pdf')]
            
            # Only proceed if there are files to clear
            if files_to_clear:
                for filename in files_to_clear:
                    source_path = os.path.join(new_folder_path, filename)
                    destination_path = os.path.join(errors_folder_path, filename)
                    shutil.move(source_path, destination_path)
                    files_cleared += 1
                
                # --- ADD THE LOGGING LOGIC HERE ---
                if files_cleared > 0:
                    details_message = f"Moved {files_cleared} unprocessed files to the errors folder."
                    ActivityLog.objects.create(
                        user=request.user,
                        action_type="Cleared New Folder",
                        details=details_message
                    )
                    messages.warning(request, details_message)
                # ------------------------------------
            else:
                messages.info(request, "No files to clear.")

        except Exception as e:
            messages.error(request, f"An error occurred while clearing files: {e}")

    return redirect('tracker:admin_dashboard')




# --- Main Views ---
@login_required
def donor_list(request):
    """
    Displays a paginated list of all Donors. For each donor on the current
    page, it calculates the lot counts to display on the card.
    """
    query = request.GET.get('query', '')
    donor_list_query = Donor.objects.all().order_by('donor_id')

    if query:
        donor_list_query = donor_list_query.filter(donor_id__icontains=query)

    total_grafts_data = Lot.objects.aggregate(total=Sum('quantity'))
    total_grafts = total_grafts_data['total'] or 0

    paginator = Paginator(donor_list_query, 24)
    page_number = request.GET.get('page')
    donors_page = paginator.get_page(page_number)

    # --- THIS IS THE FIX ---
    # The loop that adds the counts now runs for every request,
    # ensuring the data is ready for both the full page and the HTMX partial.
    for donor in donors_page:
        donor.lot_count = donor.lots.count()
        donor.released_count = donor.lots.filter(irr_out_date__isnull=False).count()
    # -----------------------
    
    # This block now receives the fully prepared donors_page object
    if 'HX-Request' in request.headers:
        return render(request, 'tracker/_donor_card_partial.html', {'donors': donors_page})

    try:
        last_sync = SyncLog.objects.latest('last_sync_time')
    except SyncLog.DoesNotExist:
        last_sync = None

    context = {
        'donors': donors_page, # Pass the paginated donors to the template
        'query': query, # Pass the search query to the template
        'last_sync': last_sync, # Pass the last sync log to the template
        'total_grafts': total_grafts,  # Pass the total grafts count to the template
    }
    return render(request, 'tracker/donor_list.html', context)




# donor detail view
@login_required
def donor_detail(request, donor_id):
    donor = get_object_or_404(Donor, id=donor_id)
    
    # Handle the document upload form submission
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.donor = donor # Associate the document with the current donor
            document.save()

            # Create a log entry
            ActivityLog.objects.create(
                user=request.user,
                action_type="Document Uploaded",
                details=f"Uploaded '{document.file.name}' to Donor '{donor.donor_id}'"
            )

            messages.success(request, 'Document uploaded successfully.')
            return redirect('tracker:donor_detail', donor_id=donor.id)
    else:
        form = DocumentForm()

    # Fetch existing data for display
    lots = donor.lots.all().order_by('lot_id')
    documents = donor.documents.all().order_by('-uploaded_at')

    context = {
        'donor': donor,
        'lots': lots,
        'documents': documents, # Pass documents to the template
        'form': form,           # Pass the form to the template
    }
    return render(request, 'tracker/donor_detail.html', context)

@login_required
def lot_detail(request, lot_id):
    """
    Displays a detailed timeline for a single Lot, showing
    all related Events in chronological order.
    """
    lot = get_object_or_404(Lot, id=lot_id)
    
    # Get all "child" sub-lots associated with this lot
    sub_lots = lot.sub_lots.all().order_by('sub_lot_id')

    context = {
        'lot': lot,
        'sub_lots': sub_lots,
    }
    return render(request, 'tracker/lot_detail.html', context)

@login_required
def labeled_lot_list(request):
    """
    Displays a paginated list of all SubLot records.
    """
    query = request.GET.get('query', '')
    # This query now correctly starts from the SubLot model
    # and filters for records that have a labeled_date.
    sub_lots_query = SubLot.objects.all().order_by('-id')

    # If there is a search query, filter the list
    if query:
        sub_lots_query = sub_lots_query.filter(sub_lot_id__icontains=query)

    paginator = Paginator(sub_lots_query, 25)
    page_number = request.GET.get('page')
    sub_lots_page = paginator.get_page(page_number)

    context = {
        'sub_lots': sub_lots_page,
        'query': query,
    }
    return render(request, 'tracker/labeled_lot_list.html', context)

@login_required
def sub_lot_detail(request, sub_lot_id):
    """
    Displays the specific details for a single SubLot record.
    """
    sub_lot = get_object_or_404(SubLot, id=sub_lot_id)
    context = {
        'sub_lot': sub_lot,
    }
    return render(request, 'tracker/sub_lot_detail.html', context)


def sync_with_monday(request):
    if request.method == 'POST':
        # --- CONFIGURATION (from your MAIN Lot Tracker Board) ---
        API_URL = "https://api.monday.com/v2"
        API_TOKEN = settings.MONDAY_API_TOKEN
        headers = {"Authorization": API_TOKEN}
        board_id = "8120988708"
        
        # --- Using your real Column IDs ---
        product_family_col = "label_mkkmvaff"
        packaged_by_col = "dropdown_mkkm4k43"
        packaged_date_col = "date_1_mkkmph2x"
        quantity_col = "numbers_mkkm2g2a"
        fpp_date_col = "date4"
        irr_out_col = "date_mkkmrc5j"
        # --- END CONFIGURATION ---

        query = f'''
            query ($limit: Int, $cursor: String) {{
                boards(ids: {board_id}) {{
                    items_page(limit: $limit, cursor: $cursor) {{
                        cursor, items {{ name, column_values(ids: [
                            "{product_family_col}", "{packaged_by_col}", "{packaged_date_col}",
                            "{quantity_col}", "{fpp_date_col}", "{irr_out_col}"
                        ]) {{ id, text }} }}
                    }}
                }}
            }}
        '''
        
        limit = 100
        cursor = None
        items_synced = 0

        try:
            while True:
                variables = {'limit': limit, 'cursor': cursor}
                data = {'query': query, 'variables': variables}
                response = requests.post(API_URL, headers=headers, json=data)
                response.raise_for_status()
                results = response.json()

                items_page = results.get('data', {}).get('boards', [{}])[0].get('items_page', {})
                items = items_page.get('items', [])
                
                if not items:
                    break

                for item in items:
                    # Debugging output to see the raw item data
                    print("Raw Monday Item:", item)

                    full_lot_id = item.get('name')
                    if not full_lot_id:
                        continue

                    donor_id_str = full_lot_id.split('-')[0].strip()
                    donor_object, _ = Donor.objects.get_or_create(donor_id=donor_id_str)

                    # --- Robust Product Type Parsing ---
                    product_type_str = None
                    for col in item['column_values']:
                        if col['id'] == product_family_col:
                            product_type_str = col.get('text')

                    if not product_type_str and len(full_lot_id.split('-')) > 1:
                        product_type_str = full_lot_id.split('-')[1].strip()
                    # --- End Parsing ---

                    # Use update_or_create to handle both new and existing lots
                    lot_object, created = Lot.objects.update_or_create(
                        lot_id=full_lot_id,
                        defaults={
                            'donor': donor_object,
                            'product_type': product_type_str if product_type_str else "",
                            'data_source': 'PRIMARY_SYNC'  # Mark as a full record
                        }
                    )

                    # Update other fields like quantity, dates, etc.
                    for col in item['column_values']:
                        col_text = col.get('text')
                        if col['id'] == packaged_by_col:
                            lot_object.packaged_by = col_text
                        elif col['id'] == packaged_date_col:
                            if col_text:
                                try:
                                    lot_object.packaged_date = datetime.strptime(col_text, '%Y-%m-%d').date()
                                except ValueError:
                                    lot_object.packaged_date = None
                            else:
                                lot_object.packaged_date = None
                        elif col['id'] == quantity_col:
                            lot_object.quantity = int(col_text) if col_text and col_text.isdigit() else None
                        elif col['id'] == irr_out_col:
                            if col_text:
                                try:
                                    lot_object.irr_out_date = datetime.strptime(col_text, '%Y-%m-%d').date()
                                except ValueError:
                                    lot_object.irr_out_date = None
                            else:
                                lot_object.irr_out_date = None
                        elif col['id'] == fpp_date_col:
                            if col_text:
                                try:
                                    lot_object.fpp_date = datetime.strptime(col_text, '%Y-%m-%d').date()
                                except ValueError:
                                    lot_object.fpp_date = None
                            else:
                                lot_object.fpp_date = None
                    # Debugging output to see the final lot object before saving
                    print(f"Saving Lot {full_lot_id}: qty={lot_object.quantity}, fpp_date={lot_object.fpp_date}")

                    lot_object.save()
                    items_synced += 1

                cursor = items_page.get('cursor')
                if not cursor:
                    break
            
            ActivityLog.objects.create(user=request.user, action_type="Primary Data Synced", details=f"Synced {items_synced} lots.")
            SyncLog.objects.update_or_create(id=1)
            messages.success(request, f"Successfully synced {items_synced} items from Monday.com.")

        except Exception as e:
            logging.error("ERROR IN SYNC VIEW:", exc_info=True)
            messages.error(request, f"An error occurred during sync: {e}")

    return redirect('tracker:donor_list')

@user_passes_test(lambda u: u.is_staff)
def sync_labeling_data_view(request):
    """Triggers the sync_labeling_data management command."""
    if request.method == 'POST':
        try:
            call_command('sync_labeling_data')
            messages.success(request, "Labeling data sync has been started.")
        except Exception as e:
            messages.error(request, f"An error occurred: {e}")
    return redirect('tracker:donor_list')

# -- receive the uploaded files and save them to your scanned_documents/new/ folder. --
@csrf_exempt
@user_passes_test(lambda u: u.is_staff)
def batch_document_upload(request):
    if request.method == 'POST':
        try:
            file = request.FILES['file']
            filename = file.name

            # Check the state of the overwrite checkbox from the form data
            should_overwrite = request.POST.get('overwrite') == 'true'

            # Define paths
            new_path = os.path.join(settings.BASE_DIR, 'scanned_documents', 'new', filename)
            processed_path = os.path.join(settings.BASE_DIR, 'scanned_documents', 'processed', filename)

            # --- DUPLICATE CHECK LOGIC ---
            if not should_overwrite and (os.path.exists(new_path) or os.path.exists(processed_path)):
                # If overwrite is OFF and the file exists, skip it.
                return JsonResponse({'message': f"Skipped: '{filename}' already exists."}, status=202)
            # ---------------------------

            # If the file doesn't exist or if overwrite is ON, save the file.
            with open(new_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            
            return JsonResponse({'message': f"Success: '{filename}' uploaded."})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

def interactive_report_data(request): 
    product_type = request.GET.get('product_type', 'all')
    year = request.GET.get('year', 'all')
    month = request.GET.get('month', 'all')

    queryset = Lot.objects.all()

    # Filter by selected product type if specified
    if product_type != 'all':
        queryset = queryset.filter(product_type=product_type)

    # Filter by selected year using fpp_date
    if year != 'all':
        queryset = queryset.filter(fpp_date__year=year)

    # Filter by selected month using fpp_date
    if month != 'all':
        queryset = queryset.filter(fpp_date__month=month)

    total_grafts = queryset.aggregate(total=Sum('quantity'))['total'] or 0
    total_lots = queryset.count()

    return JsonResponse({
        'total_grafts': total_grafts,
        'total_lots': total_lots,
    })

from collections import OrderedDict
from datetime import date

@login_required
def report_list(request):
    months = [
        {'num': '01', 'name': 'January'},
        {'num': '02', 'name': 'February'},
        {'num': '03', 'name': 'March'},
        {'num': '04', 'name': 'April'},
        {'num': '05', 'name': 'May'},
        {'num': '06', 'name': 'June'},
        {'num': '07', 'name': 'July'},
        {'num': '08', 'name': 'August'},
        {'num': '09', 'name': 'September'},
        {'num': '10', 'name': 'October'},
        {'num': '11', 'name': 'November'},
        {'num': '12', 'name': 'December'},
    ]
    if request.method == 'POST':
        try:
            call_command('generate_report')
            messages.success(request, "Successfully updated the monthly report data.")
        except Exception as e:
            messages.error(request, f"Failed to generate report: {e}")
        return redirect('tracker:report_list')

    # --- Filters for UI ---
    all_product_types = Lot.objects.values_list('product_type', flat=True).distinct().order_by('product_type')
    current_year = datetime.now().year
    years = range(current_year - 5, current_year + 1)

    def subtract_months(dt, months):
        year = dt.year
        month = dt.month - months
        while month <= 0:
            month += 12
            year -= 1
        return date(year, month, 1)

    # --- Labels for 12 months ---
    today = datetime.today().date().replace(day=1)
    full_months = OrderedDict()
    for i in range(12):
        month_date = subtract_months(today, 11 - i)
        label = month_date.strftime('%b %Y')
        full_months[label] = {
            'label': label,
            'fpp_total': 0,
            'labeled_total': 0
        }

    one_year_ago = subtract_months(today, 12)

    # --- Summary Charts ---
    packaged_summary_data = Lot.objects.filter(packaged_date__gte=one_year_ago) \
        .values('product_type') \
        .annotate(total=Sum('quantity')) \
        .order_by('-total')

    labeled_summary_query = SubLot.objects.filter(labeled_date__gte=one_year_ago) \
        .values('parent_lot__product_type') \
        .annotate(total=Sum('final_quantity')) \
        .order_by('-total')

    labeled_summary_cleaned = [
        {'product_type': item['parent_lot__product_type'], 'total': item['total']}
        for item in labeled_summary_query if item['parent_lot__product_type']
    ]

    fpp_summary_data = Lot.objects.filter(fpp_date__gte=one_year_ago) \
        .values('product_type') \
        .annotate(total=Sum('quantity')) \
        .order_by('-total')

    # --- Monthly Breakdown ---
    fpp_by_month = Lot.objects.filter(fpp_date__isnull=False, fpp_date__gte=one_year_ago) \
        .annotate(month=TruncMonth('fpp_date')) \
        .values('month') \
        .annotate(total=Sum('quantity'))

    labeled_by_month = SubLot.objects.filter(labeled_date__isnull=False, labeled_date__gte=one_year_ago) \
        .annotate(month=TruncMonth('labeled_date')) \
        .values('month') \
        .annotate(total=Sum('final_quantity'))
    
    # --- Irradiated Grafts by Month ---
    irradiated_by_month = Lot.objects.filter(irr_out_date__isnull=False, irr_out_date__gte=one_year_ago) \
        .annotate(month=TruncMonth('irr_out_date')) \
        .values('month') \
        .annotate(total=Sum('quantity'))

    for item in fpp_by_month:
        label = item['month'].strftime('%b %Y')
        if label in full_months:
            full_months[label]['fpp_total'] = item['total'] or 0

    for item in labeled_by_month:
        label = item['month'].strftime('%b %Y')
        if label in full_months:
            full_months[label]['labeled_total'] = item['total'] or 0

    for item in irradiated_by_month:
        label = item['month'].strftime('%b %Y')
        if label in full_months:
            full_months[label]['irradiated_total'] = item['total'] or 0

    monthly_graft_data = list(full_months.values())

    # --- Exclude CGG/CGP Packaged ---
    excluded_families_data = (
        Lot.objects
        .filter(packaged_date__gte=one_year_ago)
        .exclude(product_type__in=["CGG", "CGP"])
        .values('product_type')
        .annotate(total=Sum('quantity'))
        .order_by('-total')
    )

    # --- Table of Existing Reports ---
    reports = Report.objects.all().order_by('-year', '-month')

    # --- All Chart Cards ---
    chart_cards = [
        {
            "title": "📦 Packaged (Last 12 Months)",
            "canvas_id": "packagedChart",
            "color": "rgba(16, 185, 129, 0.8)",
            "data": json.dumps(list(packaged_summary_data))
        },
        {
            "title": "🏷️ Labeled (Last 12 Months)",
            "canvas_id": "labeledChart",
            "color": "rgba(59, 130, 246, 0.8)",
            "data": json.dumps(labeled_summary_cleaned)
        },
        {
            "title": "🔍 FPP Inspected (Last 12 Months)",
            "canvas_id": "fppChart",
            "color": "rgba(168, 85, 247, 0.8)",
            "data": json.dumps(list(fpp_summary_data))
        },
        {
            "title": "📦 Packaged Grafts (Excl. CGG & CGP)",
            "canvas_id": "excludedPackagedChart",
            "color": "rgba(236, 72, 153, 0.8)",  # Tailwind rose-500
            "data": json.dumps(list(excluded_families_data))
        },

    ]

    # --- Final Context ---
    context = {
        'reports': reports,
        'packaged_chart_data': json.dumps(list(packaged_summary_data)),
        'labeled_chart_data': json.dumps(labeled_summary_cleaned),
        'fpp_chart_data': json.dumps(list(fpp_summary_data)),
        'monthly_graft_data': json.dumps(monthly_graft_data),
        'all_product_types': all_product_types,
        'years': years,
        'full_months': full_months,
        'chart_cards': chart_cards,
        'months': months,
        'current_year': current_year,
        'current_month': datetime.now().month
    }

    return render(request, 'tracker/report_list.html', context)

# def export_reports_pdf(request):
#     reports = Report.objects.all().order_by('-generated_at')  # or however you fetch them
#     html_string = render_to_string('tracker/reports_pdf_template.html', {'reports': reports})

#     with tempfile.NamedTemporaryFile(delete=True, suffix=".pdf") as temp:
#         HTML(string=html_string).write_pdf(temp.name)

#         with open(temp.name, 'rb') as f:
#             pdf = f.read()

#     response = HttpResponse(pdf, content_type='application/pdf')
#     response['Content-Disposition'] = 'attachment; filename="all_reports.pdf"'
#     return response

@login_required
def report_detail(request, report_id):
    report = get_object_or_404(Report, id=report_id)

    # --- Calculate data for all three summary charts ---
    # 1. All-Time Packaged Grafts
    packaged_summary_data = Lot.objects.values('product_type')\
        .annotate(total=Sum('quantity')).order_by('-total')

    # 2. All-Time Labeled Grafts
    labeled_summary_query = SubLot.objects.values('parent_lot__product_type')\
        .annotate(total=Sum('final_quantity')).order_by('-total')
    
    labeled_summary_cleaned = [
        {'product_type': item['parent_lot__product_type'], 'total': item['total']}
        for item in labeled_summary_query if item['parent_lot__product_type']
    ]
    
    # 3. All-Time FPP Inspected Grafts
    fpp_summary_data = Lot.objects.filter(fpp_date__isnull=False)\
        .values('product_type').annotate(total=Sum('quantity')).order_by('-total')

    context = {
        'report': report,
        'packaged_chart_data': json.dumps(list(packaged_summary_data)),
        'labeled_chart_data': json.dumps(labeled_summary_cleaned),
        'fpp_chart_data': json.dumps(list(fpp_summary_data)), # Add new data
    }
    return render(request, 'tracker/report_detail.html', context)

@user_passes_test(lambda u: u.is_staff)
def delete_report(request, report_id):
    # This view only accepts POST requests for safety
    if request.method == 'POST':
        report = get_object_or_404(Report, id=report_id)
        report.delete()
        messages.success(request, "Report was successfully deleted.")
    
    return redirect('tracker:report_list')