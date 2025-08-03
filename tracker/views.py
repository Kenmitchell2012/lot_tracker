import logging
import requests
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from .models import Donor, Lot, Document, Event, SyncLog, ActivityLog, Report, SubLot, MonthlyBoard
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum, Max
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
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.timezone import now
from django.template.loader import render_to_string
import tempfile
# from .tasks import sync_labeling_data_task
# from background_task.models import Task


# admin imports
import os
from datetime import datetime, date
from django.conf import settings
from django.core.management import call_command
from django.contrib.auth.decorators import user_passes_test
import io
import shutil
import dateutil.parser
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import F, ExpressionWrapper, FloatField
from django.urls import reverse
from django.db.models import Q

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
        # Call the parent method first to complete the login process.
        response = super().form_valid(form)
        
        # Now that the user is logged in, you can access their details.
        user_name = self.request.user.get_full_name() or self.request.user.username
        messages.success(self.request, f"Welcome back, {user_name}!")
        
        return response


# NEW custom logout view to add a success message
@login_required
def custom_logout(request):
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('login')

@login_required
def command_center(request):
    today = datetime.today().date()
    this_month = today.month
    this_year = today.year

    total_donors = Donor.objects.count()
    total_grafts_month = Lot.objects.filter(fpp_date__year=this_year, fpp_date__month=this_month).aggregate(total=Sum('quantity'))['total'] or 0
    total_labeled_month = SubLot.objects.filter(labeled_date__year=this_year, labeled_date__month=this_month).aggregate(total=Sum('final_quantity'))['total'] or 0
    total_irradiated_month = Lot.objects.filter(irr_out_date__year=this_year, irr_out_date__month=this_month).aggregate(total=Sum('quantity'))['total'] or 0
    lots_req_attn = SubLot.objects.filter(status='REQ ATTN').order_by('-due_date')[:10]  # Get the 10 most recent lots that require attention

    try:
        current_board = MonthlyBoard.objects.get(month=this_month, year=this_year)
    except MonthlyBoard.DoesNotExist:
        current_board = None

    context = {
        'total_donors': total_donors,
        'total_grafts_month': total_grafts_month,
        'total_labeled_month': total_labeled_month,
        'total_irradiated_month': total_irradiated_month,
        'current_board': current_board,
        'lots_req_attn': lots_req_attn,
    }
    return render(request, 'tracker/command_center.html', context)

def global_search(request):
    query = request.GET.get('q', '').strip()
    results = []
    
    # Add a print statement for debugging
    print(f"--- Global search received query: '{query}' ---")
    
    # UPDATED: Lowered the search minimum to 2 characters
    if len(query) >= 2:
        try:
            donors = Donor.objects.filter(donor_id__icontains=query)[:5]
            results.extend([
                {'type': 'Donor', 'text': d.donor_id, 'url': reverse('tracker:donor_detail', args=[d.id])} 
                for d in donors
            ])
        except Exception as e:
            print(f"Error during global search for Donors: {e}")

        try:
            lots = Lot.objects.filter(lot_id__icontains=query)[:5]
            results.extend([
                {'type': 'Lot', 'text': l.lot_id, 'url': reverse('tracker:lot_detail', args=[l.id])} 
                for l in lots
            ])
        except Exception as e:
            print(f"Error during global search for Lots: {e}")

        try:
            sub_lots = SubLot.objects.filter(sub_lot_id__icontains=query)[:5]
            results.extend([
                {'type': 'Sub-Lot', 'text': s.sub_lot_id, 'url': reverse('tracker:sub_lot_detail', args=[s.id])} 
                for s in sub_lots
            ])
        except Exception as e:
            print(f"Error during global search for Sub-Lots: {e}")
        
        try:
            documents = Document.objects.filter(
                Q(document_type__icontains=query) | 
                Q(file__icontains=query) | 
                Q(donor__donor_id__icontains=query)
            ).select_related('donor')[:5]
            results.extend([
                {
                    'type': 'Document', 
                    'text': f"{d.document_type} ({d.donor.donor_id})", 
                    'url': reverse('tracker:donor_detail', args=[d.donor.id])
                } 
                for d in documents
            ])
        except Exception as e:
            print(f"Error during global search for Documents: {e}")
        
    return JsonResponse({'results': results})

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




# --- Main Views ---@login_required

@login_required
def donor_list(request):
    """
    Displays a paginated list of all Donors.
    Supports HTMX live search via donor_id.
    Each donor is annotated with lot stats and latest packaged date.
    """
    query = request.GET.get('query', '').strip()
    donor_list_query = Donor.objects.all().order_by('donor_id')

    if query:
        donor_list_query = donor_list_query.filter(donor_id__icontains=query)

    # Total grafts from all lots
    total_grafts = Lot.objects.aggregate(total=Sum('quantity'))['total'] or 0

    # Paginate
    paginator = Paginator(donor_list_query, 24)
    page_number = request.GET.get('page')
    donors_page = paginator.get_page(page_number)

    # Annotate donors with custom stats
    for donor in donors_page:
        donor.lot_count = donor.lots.count()
        donor.released_count = donor.lots.filter(irr_out_date__isnull=False).count()
        donor.latest_lot_date = donor.lots.aggregate(latest=Max('packaged_date'))['latest']

    # # Return just the donor cards for HTMX requests
    # if request.headers.get('HX-Request'):
    #     return render(request, 'tracker/_donor_card_partial.html', {
    #         'donors': donors_page
    #     })

    # Normal full-page render
    try:
        last_sync = SyncLog.objects.latest('timestamp')
    except SyncLog.DoesNotExist:
        last_sync = None

    return render(request, 'tracker/donor_list.html', {
        'donors': donors_page,
        'query': query,
        'last_sync': last_sync,
        'total_grafts': total_grafts,
    })




# donor detail view
@login_required
def donor_detail(request, donor_id):
    donor = get_object_or_404(Donor, id=donor_id)
    
    # # Handle the document upload form submission
    # if request.method == 'POST':
    #     form = DocumentForm(request.POST, request.FILES)
    #     if form.is_valid():
    #         document = form.save(commit=False)
    #         document.donor = donor # Associate the document with the current donor
    #         document.save()

    #         # Create a log entry
    #         ActivityLog.objects.create(
    #             user=request.user,
    #             action_type="Document Uploaded",
    #             details=f"Uploaded '{document.file.name}' to Donor '{donor.donor_id}'"
    #         )

    #         messages.success(request, 'Document uploaded successfully.')
    #         return redirect('tracker:donor_detail', donor_id=donor.id)
    # else:
    #     form = DocumentForm()

    # Fetch existing data for display
    lots = donor.lots.all().order_by('lot_id')
    documents = donor.documents.all().order_by('-uploaded_at')
    # get all sublots for this donor by querying through the lots
    sub_lots = SubLot.objects.filter(parent_lot__donor=donor).order_by('sub_lot_id')

    context = {
        'donor': donor,
        'lots': lots,
        'documents': documents, # Pass documents to the template
        # 'form': form,           # Pass the form to the template
        'sub_lots': sub_lots,   # Pass sub-lots to the template
    }
    return render(request, 'tracker/donor_detail.html', context)

@login_required
def lot_detail(request, lot_id):
    """
    Displays a detailed timeline for a single Lot, showing
    all related Events in chronological order.
    """
    lot = get_object_or_404(Lot, id=lot_id)

    context = {
        'lot': lot,
    }
    return render(request, 'tracker/lot_detail.html', context)

# Full labeled_lot_list view for clarity

@login_required
def labeled_lot_list(request):
    # This redirect logic for the "today" button is still correct
    if request.GET.get('date_filter') == 'today':
        q = request.GET.copy()
        q['due_date'] = timezone.localdate().strftime('%Y-%m-%d')
        if 'date_filter' in q: del q['date_filter']
        return redirect(f"{request.path}?{q.urlencode()}")

    # Get all filter parameters, using hidden fields as fallbacks
    status_filter = request.GET.get('status', request.GET.get('current_status', 'All'))
    month_filter = request.GET.get('month_filter', request.GET.get('current_month_filter'))
    query = request.GET.get('query', '')
    due_date_specific = request.GET.get('due_date')

    # Apply filters
    queryset = SubLot.objects.all().order_by('-due_date')

    if status_filter and status_filter != "All":
        queryset = queryset.filter(status=status_filter)
    if query:
        queryset = queryset.filter(sub_lot_id__icontains=query)

    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            queryset = queryset.filter(due_date__year=year, due_date__month=month)
        except (ValueError, TypeError): pass
    elif due_date_specific:
        try:
            selected_date = datetime.strptime(due_date_specific, '%Y-%m-%d').date()
            queryset = queryset.filter(due_date=selected_date)
        except (ValueError, TypeError): pass

    # Build the filter description string for the UI
    filter_description_parts = [f"Status: {status_filter}"]
    if month_filter:
        year, month = map(int, month_filter.split('-'))
        filter_description_parts.append(f"Month: {date(year, month, 1).strftime('%B %Y')}")
    elif due_date_specific:
        filter_description_parts.append(f"Date: {due_date_specific}")
    filter_description = " | ".join(filter_description_parts)
            
    # Get available months for the filter buttons
    available_months_qs = MonthlyBoard.objects.values('year', 'month').order_by('-year', '-month')
    available_months = [{'year': item['year'], 'month': item['month'], 'date_obj': date(item['year'], item['month'], 1), 'month_value': f"{item['year']}-{item['month']:02d}"} for item in available_months_qs]
            
    paginator = Paginator(queryset, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    last_sync = SyncLog.objects.order_by('-timestamp').first()

    try:
        local_today = timezone.localdate()
        current_board = MonthlyBoard.objects.get(month=local_today.month, year=local_today.year)
    except MonthlyBoard.DoesNotExist:
        current_board = None

    context = {
        'sub_lots': page_obj, 'query': query,
        'status_filter': status_filter, 'last_sync': last_sync,
        'due_date_specific': due_date_specific,
        'current_board': current_board,
        'month_filter': month_filter,
        'available_months': available_months,
        'filter_description': filter_description,
    }

    # The view now has only ONE return statement. It always renders the full page.
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
        # --- CONFIGURATION (from MAIN Lot Tracker Board) ---
        API_URL = "https://api.monday.com/v2"
        API_TOKEN = settings.MONDAY_API_TOKEN
        headers = {"Authorization": API_TOKEN}
        board_id = "8120988708"
        
        # --- Column IDs ---
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
@login_required
def sync_board(request, board_id):
    board_to_sync = get_object_or_404(MonthlyBoard, board_id=board_id)
    
    # --- SECTION 1: CONFIGURATION ---
    API_URL = "https://api.monday.com/v2"
    API_TOKEN = settings.MONDAY_API_TOKEN
    headers = {"Authorization": API_TOKEN, "API-Version": "2023-10"}
    labeling_board_id = board_to_sync.board_id
    
    product_type_col = "dropdown__1"
    labeled_by_col = "text5"
    labeled_date_col = "date43"
    due_date_col = "po_due_date"
    final_qty_col = "numbers"
    chart_status_col = "status"

    # --- SECTION 2: GRAPHQL QUERY ---
    query = f'''
        query ($limit: Int, $cursor: String) {{
            boards(ids: {labeling_board_id}) {{
                items_page(limit: $limit, cursor: $cursor) {{
                    cursor
                    items {{
                        id, name
                        column_values(ids: [
                            "{product_type_col}", "{labeled_by_col}", "{labeled_date_col}",
                            "{due_date_col}", "{final_qty_col}", "{chart_status_col}"
                        ]) {{
                            id, text
                        }}
                    }}
                }}
            }}
        }}
    '''

    # --- SECTION 3: SYNC LOGIC ---
    limit, cursor = 100, None
    created_count, updated_count, skipped_count = 0, 0, 0
    total_lots_processed = 0
    total_grafts_processed = 0

    try:
        while True:
            variables = {'limit': limit, 'cursor': cursor}
            data = {'query': query, 'variables': variables}
            response = requests.post(API_URL, headers=headers, json=data)
            response.raise_for_status()
            results = response.json()

            if 'errors' in results and results['errors']:
                raise Exception(f"Monday.com API Error: {results['errors'][0]['message']}")

            items_page = results.get('data', {}).get('boards', [{}])[0].get('items_page', {})
            items = items_page.get('items', [])
            if not items:
                break

            for item in items:
                full_sublot_id = item.get('name')
                
                sublot_product_type, labeled_by, labeled_date_str, due_date_str, final_qty, status = None, None, None, None, None, None
                for col in item['column_values']:
                    col_text = col.get('text')
                    if col['id'] == product_type_col: sublot_product_type = col_text
                    elif col['id'] == labeled_by_col: labeled_by = col_text
                    elif col['id'] == labeled_date_col: labeled_date_str = col_text
                    elif col['id'] == due_date_col: due_date_str = col_text
                    elif col['id'] == final_qty_col: final_qty = int(col_text) if col_text and col_text.isdigit() else None
                    elif col['id'] == chart_status_col: status = col_text
                
                if not full_sublot_id:
                    skipped_count += 1
                    continue

                donor_id_str = full_sublot_id.split('-')[0]
                donor_obj, created_donor = Donor.objects.get_or_create(donor_id=donor_id_str)
                
                parent_lot_obj = Lot.objects.filter(donor=donor_obj).order_by('packaged_date').first()
                
                if not parent_lot_obj:
                    placeholder_lot_id = f"{donor_id_str}-INITIAL"
                    parent_lot_obj, created_lot = Lot.objects.get_or_create(
                        lot_id=placeholder_lot_id,
                        defaults={
                            'donor': donor_obj,
                            'product_type': "Pending Main Sync",
                            'data_source': 'PLACEHOLDER'
                        }
                    )

                latest_comment_body = None
                if status == 'REQ ATTN':
                    item_id = item.get('id')
                    updates_query = f'query {{ items(ids: [{item_id}]) {{ updates(limit: 1) {{ body }} }} }}'
                    updates_response = requests.post(API_URL, headers=headers, json={'query': updates_query})
                    updates_data = updates_response.json()
                    updates = updates_data.get('data', {}).get('items', [{}])[0].get('updates', [])
                    if updates:
                        latest_comment_body = updates[0].get('body')

                due_date_obj = datetime.strptime(due_date_str.split(' - ')[0].strip(), '%Y-%m-%d').date() if due_date_str else None
                labeled_date_obj = datetime.strptime(labeled_date_str.split(' - ')[0].strip(), '%Y-%m-%d').date() if labeled_date_str else None

                sublot, created = SubLot.objects.update_or_create(
                    sub_lot_id=full_sublot_id,
                    defaults={
                        'parent_lot': parent_lot_obj,
                        'source_board': board_to_sync,
                        'product_type': sublot_product_type,
                        'labeled_by': labeled_by,
                        'labeled_date': labeled_date_obj,
                        'due_date': due_date_obj,
                        'final_quantity': final_qty,
                        'status': status,
                        'latest_comment': latest_comment_body,
                    }
                )

                total_lots_processed += 1
                if sublot.final_quantity:
                    total_grafts_processed += sublot.final_quantity

                if created: created_count += 1
                else: updated_count += 1

            cursor = items_page.get('cursor')
            if not cursor:
                break
        
        details_str = (f"Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}. "
                       f"Processed: {total_lots_processed} lots totaling {total_grafts_processed:,} grafts.")
        board_to_sync.last_synced = timezone.now()
        board_to_sync.save()
        SyncLog.objects.create(board_id=labeling_board_id, status='Success', details=details_str)
        ActivityLog.objects.create(user=request.user, action_type="Board Data Synced", details=f"Synced board '{board_to_sync.name}'. {details_str}")
        messages.success(request, f"Successfully synced board: {board_to_sync.name} ({details_str})")

    except Exception as e:
        messages.error(request, f"An error occurred while syncing '{board_to_sync.name}': {e}")
    
    return redirect('tracker:manage_boards')


@user_passes_test(lambda u: u.is_staff)
@login_required
def manage_boards(request):
    if request.method == 'POST':
        # Logic to handle a form for adding a new MonthlyBoard
        # For simplicity, you can start by adding them via the Django Admin
        pass

    all_boards = MonthlyBoard.objects.all()
    context = {'boards': all_boards}
    return render(request, 'tracker/manage_boards.html', context)

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
        {'num': '01', 'name': 'January'}, {'num': '02', 'name': 'February'},
        {'num': '03', 'name': 'March'}, {'num': '04', 'name': 'April'},
        {'num': '05', 'name': 'May'}, {'num': '06', 'name': 'June'},
        {'num': '07', 'name': 'July'}, {'num': '08', 'name': 'August'},
        {'num': '09', 'name': 'September'}, {'num': '10', 'name': 'October'},
        {'num': '11', 'name': 'November'}, {'num': '12', 'name': 'December'},
    ]
    if request.method == 'POST':
        try:
            call_command('generate_report')
            messages.success(request, "Successfully updated the monthly report data.")
        except Exception as e:
            messages.error(request, f"Failed to generate report: {e}")
        return redirect('tracker:report_list')

    # --- Date calculations for the 12-month window ---
    today = timezone.localdate()
    current_year = today.year
    current_month = today.month
    start_of_this_month = today.replace(day=1)

    def subtract_months(dt, months_to_subtract):
        year, month = dt.year, dt.month - months_to_subtract
        while month <= 0:
            month += 12
            year -= 1
        return date(year, month, 1)

    thirteen_months_ago_start = subtract_months(start_of_this_month, 12)

    # --- Create labels and placeholder data for the last 12 months ---
    full_months = OrderedDict()
    for i in range(13):
        month_date = subtract_months(start_of_this_month, 12 - i)
        label = month_date.strftime('%b %Y')
        full_months[label] = {'label': label, 'fpp_total': 0, 'labeled_total': 0, 'irradiated_total': 0}

    # --- Queries for Summary Cards (based on last 12 months from today) ---
    packaged_summary_data = Lot.objects.filter(packaged_date__gte=thirteen_months_ago_start).values('product_type').annotate(total=Sum('quantity')).order_by('-total')
    # This summary card still uses labeled_date, as its title is "Labeled (Last 12 Months)"
    labeled_summary_query = SubLot.objects.filter(labeled_date__gte=thirteen_months_ago_start).values('product_type').annotate(total=Sum('final_quantity')).order_by('-total')
    fpp_summary_data = Lot.objects.filter(fpp_date__gte=thirteen_months_ago_start).values('product_type').annotate(total=Sum('quantity')).order_by('-total')
    excluded_families_data = Lot.objects.filter(packaged_date__gte=thirteen_months_ago_start).exclude(product_type__in=["CGG", "CGP"]).values('product_type').annotate(total=Sum('quantity')).order_by('-total')
    
    # --- Queries for Monthly Trend Chart ---
    # FPP and Irradiated trends are still based on their respective dates
    fpp_by_month = Lot.objects.filter(fpp_date__isnull=False, fpp_date__gte=thirteen_months_ago_start).annotate(month=TruncMonth('fpp_date')).values('month').annotate(total=Sum('quantity'))
    irradiated_by_month = Lot.objects.filter(irr_out_date__isnull=False, irr_out_date__gte=thirteen_months_ago_start).annotate(month=TruncMonth('irr_out_date')).values('month').annotate(total=Sum('quantity'))

    # THIS IS THE CORRECTED QUERY: It groups by the source_board's month and year
    labeled_by_board = SubLot.objects.filter(
        source_board__isnull=False,
        source_board__year__gte=thirteen_months_ago_start.year
    ).values(
        'source_board__year', 'source_board__month'
    ).annotate(
        total=Sum('final_quantity')
    ).order_by('source_board__year', 'source_board__month')

    # --- Populate the monthly data dictionary ---
    for item in fpp_by_month:
        label = item['month'].strftime('%b %Y')
        if label in full_months: full_months[label]['fpp_total'] = item['total'] or 0
    
    # This loop is now updated to use the new board-based query
    for item in labeled_by_board:
        month_date = date(item['source_board__year'], item['source_board__month'], 1)
        label = month_date.strftime('%b %Y')
        if label in full_months:
            full_months[label]['labeled_total'] = item['total'] or 0

    for item in irradiated_by_month:
        label = item['month'].strftime('%b %Y')
        if label in full_months: full_months[label]['irradiated_total'] = item['total'] or 0

    monthly_graft_data = list(full_months.values())
    
    # --- Final data assembly for the template ---
    reports = Report.objects.all().order_by('-year', '-month')
    all_product_types = Lot.objects.values_list('product_type', flat=True).distinct().order_by('product_type')
    years = range(current_year - 5, current_year + 1)

    chart_cards = [
        {"title": "📦 Packaged (Last 12 Months)", "canvas_id": "packagedChart", "color": "rgba(16, 185, 129, 0.8)", "data": json.dumps(list(packaged_summary_data))},
        {"title": "🏷️ Labeled (Last 12 Months)", "canvas_id": "labeledChart", "color": "rgba(59, 130, 246, 0.8)", "data": json.dumps(list(labeled_summary_query))},
        {"title": "🔍 FPP Inspected (Last 12 Months)", "canvas_id": "fppChart", "color": "rgba(168, 85, 247, 0.8)", "data": json.dumps(list(fpp_summary_data))},
        {"title": "📦 Packaged Grafts (Excl. CGG & CGP)", "canvas_id": "excludedPackagedChart", "color": "rgba(236, 72, 153, 0.8)", "data": json.dumps(list(excluded_families_data))},
    ]

    context = {
        'reports': reports,
        'chart_cards': chart_cards,
        'monthly_graft_data': json.dumps(monthly_graft_data),
        'all_product_types': all_product_types,
        'years': years,
        'months': months,
        'current_year': current_year,
        'current_month': current_month,
    }

    return render(request, 'tracker/report_list.html', context)


@login_required
def yield_report(request):
    # Get all lots that have an initial quantity
    lots_with_yield = Lot.objects.filter(
        quantity__gt=0, 
        data_source='PRIMARY_SYNC'
    ).annotate(
        # Sum the final quantity of all its children sub-lots
        total_labeled_quantity=Sum('sub_lots__final_quantity')
    ).annotate(
        # Calculate the yield percentage
        yield_percentage=ExpressionWrapper(
            (F('total_labeled_quantity') * 100.0 / F('quantity')),
            output_field=FloatField()
        )
    ).order_by('-yield_percentage')

    context = {'lots_with_yield': lots_with_yield}
    return render(request, 'tracker/yield_report.html', context)

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

    # --- ADD THIS DATE CALCULATION LOGIC ---
    # This is the same logic from your main reports page
    today = timezone.localdate()
    start_of_this_month = today.replace(day=1)

    def subtract_months(dt, months_to_subtract):
        year, month = dt.year, dt.month - months_to_subtract
        while month <= 0:
            month += 12
            year -= 1
        return date(year, month, 1)

    thirteen_months_ago_start = subtract_months(start_of_this_month, 12)
    # --- END OF ADDITION ---

    # --- UPDATE THE QUERIES TO USE THE DATE FILTER ---
    # 1. 13-Month Packaged Grafts
    packaged_summary_data = Lot.objects.filter(
        packaged_date__gte=thirteen_months_ago_start
    ).values('product_type').annotate(total=Sum('quantity')).order_by('-total')

    # 2. 13-Month Labeled Grafts
    # This now uses the sub-lot's own product_type for consistency
    labeled_summary_query = SubLot.objects.filter(
        labeled_date__gte=thirteen_months_ago_start
    ).values('product_type').annotate(total=Sum('final_quantity')).order_by('-total')
    
    # 3. 13-Month FPP Inspected Grafts
    fpp_summary_data = Lot.objects.filter(
        fpp_date__isnull=False,
        fpp_date__gte=thirteen_months_ago_start
    ).values('product_type').annotate(total=Sum('quantity')).order_by('-total')

    context = {
        'report': report,
        'packaged_chart_data': json.dumps(list(packaged_summary_data)),
        'labeled_chart_data': json.dumps(list(labeled_summary_query)), # No longer needs cleaning
        'fpp_chart_data': json.dumps(list(fpp_summary_data)),
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