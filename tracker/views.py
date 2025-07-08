import logging
import requests
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from .models import Donor, Lot, Document, Event, SyncLog
from django.utils import timezone
from datetime import datetime
from django.core.paginator import Paginator
from django.db.models import Count
from django.contrib.auth.decorators import login_required
from .forms import DocumentForm, SignUpForm, LoginForm
from django.contrib.auth.views import LoginView
from django.contrib.auth import logout
from django.contrib.auth import login, authenticate
from django.shortcuts import render, redirect

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

# This decorator ensures only staff/admins can access the view
# tracker/views.py
@user_passes_test(lambda u: u.is_staff)
def admin_dashboard(request):
    new_docs_path = os.path.join(settings.BASE_DIR, 'scanned_documents', 'new')
    
    # Handle the button press to run the script
    if request.method == 'POST':
        try:
            # Create an in-memory text buffer to capture the command's output
            output_buffer = io.StringIO()
            
            # Run the command, redirecting its output to our buffer
            call_command('process_docs', stdout=output_buffer)
            
            # Get the captured output from the buffer
            command_output = output_buffer.getvalue()
            
            # Add each line of the output as a separate message
            for line in command_output.strip().split('\n'):
                if "Successfully" in line:
                    messages.success(request, line)
                elif "Skipping" in line or "WARNING" in line:
                    messages.warning(request, line)
                else:
                    messages.info(request, line)

        except Exception as e:
            messages.error(request, f"An error occurred while running the script: {e}")
        
        return redirect('tracker:admin_dashboard')

    # For a normal page load, count the files
    try:
        files_to_process_count = len([f for f in os.listdir(new_docs_path) if f.lower().endswith('.pdf')])
    except FileNotFoundError:
        files_to_process_count = 0
        messages.warning(request, f"The directory '{new_docs_path}' was not found.")

    context = {
        'files_to_process_count': files_to_process_count,
    }
    return render(request, 'tracker/admin_dashboard.html', context)

@user_passes_test(lambda u: u.is_staff)
def clear_new_folder(request):
    """
    On POST, moves all files from the 'new' folder to an 'errors'
    folder for manual review.
    """
    if request.method == 'POST':
        new_folder_path = os.path.join(settings.BASE_DIR, 'scanned_documents', 'new')
        errors_folder_path = os.path.join(settings.BASE_DIR, 'scanned_documents', 'errors')
        
        files_cleared = 0
        try:
            # Get a list of all files in the 'new' directory
            files_to_clear = [f for f in os.listdir(new_folder_path) if f.lower().endswith('.pdf')]
            
            for filename in files_to_clear:
                source_path = os.path.join(new_folder_path, filename)
                destination_path = os.path.join(errors_folder_path, filename)
                shutil.move(source_path, destination_path)
                files_cleared += 1
            
            if files_cleared > 0:
                messages.warning(request, f"Cleared {files_cleared} un-processed files to the 'errors' folder.")
            else:
                messages.info(request, "No files to clear.")

        except Exception as e:
            messages.error(request, f"An error occurred while clearing files: {e}")

    return redirect('tracker:admin_dashboard')




# --- Main Views ---
@login_required
def donor_list(request):
    query = request.GET.get('query', '')
    all_donors = Donor.objects.all().order_by('donor_id')

    # Use annotate() to get the count of lots for each donor
    all_donors = Donor.objects.annotate(lot_count=Count('lots')).order_by('donor_id')


    if query:
        all_donors = all_donors.filter(donor_id__icontains=query)

    paginator = Paginator(all_donors, 25) 
    page_number = request.GET.get('page')
    donors_page = paginator.get_page(page_number)

    # --- THIS IS THE NEW LOGIC ---
    # If the request is from HTMX, render only the partial template
    if 'HX-Request' in request.headers:
        return render(request, 'tracker/_donor_rows_partial.html', {'donors': donors_page})
    # ---------------------------

    # For a normal page load, fetch the last sync time and render the full page
    try:
        last_sync = SyncLog.objects.latest('last_sync_time')
    except SyncLog.DoesNotExist:
        last_sync = None

    context = {
        'donors': donors_page,
        'query': query,
        'last_sync': last_sync,
    }
    return render(request, 'tracker/donor_list.html', context)



# donor detail view

from .forms import DocumentForm # <-- Import the new form
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
    
    # Only fetch events that are directly related to this lot
    events = lot.events.all().order_by('-event_date')

    context = {
        'lot': lot,
        'events': events, # Pass the events queryset directly
    }
    return render(request, 'tracker/lot_detail.html', context)



def sync_with_monday(request):
    """
    On POST, fetches all data from a Monday.com board using pagination,
    parses it, and creates/updates Lot records in the database.
    """
    if request.method == 'POST':
        # --- Configuration ---
        API_URL = "https://api.monday.com/v2"
        API_TOKEN = settings.MONDAY_API_TOKEN
        headers = {"Authorization": API_TOKEN, "Content-Type": "application/json"}
        board_id = "8120988708"
        
        # Corrected Column IDs from your board
        packaged_by_col = "dropdown_mkkm4k43"
        packaged_date_col = "date_1_mkkmph2x"
        quantity_col = "numbers_mkkm2g2a"
        fpp_date_col = "date4"
        irr_run_col = "text_mkm0f36c"
        irr_out_col = "date_mkkmrc5j"
        qc_out_num_col = "numbers_mkkndb04"
        qc_out_reason_col = "status_1_mkkn165p"
        # --- End Configuration ---

        query = f'''
            query ($limit: Int, $cursor: String) {{
                boards(ids: {board_id}) {{
                    items_page(limit: $limit, cursor: $cursor) {{
                        cursor
                        items {{
                            id
                            name
                            column_values(ids: [
                                "{packaged_by_col}", "{packaged_date_col}", "{quantity_col}",
                                "{fpp_date_col}", "{irr_run_col}", "{irr_out_col}",
                                "{qc_out_num_col}", "{qc_out_reason_col}"
                            ]) {{
                                id
                                text
                            }}
                        }}
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
                
                # This section correctly defines 'items' before it is used
                items_page = results.get('data', {}).get('boards', [{}])[0].get('items_page', {})
                items = items_page.get('items', [])
                
                if not items:
                    break

                for item in items:
                    full_lot_id = item.get('name')
                    if not full_lot_id or len(full_lot_id) < 9:
                        continue

                    donor_id_str = full_lot_id[:9].strip()
                    product_type_str = full_lot_id[9:].strip().lstrip('- ')
                    
                    donor_object, _ = Donor.objects.get_or_create(donor_id=donor_id_str)
                    
                    lot_object, created = Lot.objects.get_or_create(
                        lot_id=full_lot_id,
                        defaults={'donor': donor_object, 'product_type': product_type_str}
                    )

                    for col in item['column_values']:
                        col_text = col.get('text')
                        if col['id'] == packaged_by_col:
                            lot_object.packaged_by = col_text
                        elif col['id'] == packaged_date_col:
                            lot_object.packaged_date = col_text if col_text else None
                        elif col['id'] == quantity_col:
                            lot_object.quantity = int(col_text) if col_text and col_text.isdigit() else None
                        elif col['id'] == fpp_date_col:
                            lot_object.fpp_date = col_text if col_text else None
                        elif col['id'] == irr_run_col:
                            lot_object.irr_run_number = col_text
                        elif col['id'] == irr_out_col:
                            lot_object.irr_out_date = col_text if col_text else None
                        elif col['id'] == qc_out_num_col:
                            lot_object.qc_out_number = col_text
                        elif col['id'] == qc_out_reason_col:
                            lot_object.qc_out_reason = col_text
                    
                    lot_object.save()
                    items_synced += 1

                cursor = items_page.get('cursor')
                if not cursor:
                    break
            
            SyncLog.objects.update_or_create(id=1)
            messages.success(request, f"Successfully synced {items_synced} items from Monday.com.")

        except Exception as e:
            logging.error("ERROR IN SYNC VIEW:", exc_info=True)
            messages.error(request, f"An error occurred during sync: {e}")

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
