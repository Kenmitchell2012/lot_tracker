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

# Setup logger
logger = logging.getLogger(__name__)

# --- Main Views ---

def donor_list(request):
    """
    Displays a paginated list of all Donors and handles search functionality.
    """
    query = request.GET.get('query', '')
    all_donors = Donor.objects.all().order_by('donor_id')

    if query:
        all_donors = all_donors.filter(donor_id__icontains=query)

    # --- PAGINATION LOGIC ---
    # 1. Create a Paginator object, showing 25 donors per page
    paginator = Paginator(all_donors, 25) 
    
    # 2. Get the current page number from the URL's query parameters (e.g., /?page=2)
    page_number = request.GET.get('page')
    
    # 3. Get the Page object for the current page
    donors_page = paginator.get_page(page_number)
    # --- END PAGINATION LOGIC ---

    try:
        last_sync = SyncLog.objects.latest('last_sync_time')
    except SyncLog.DoesNotExist:
        last_sync = None

    context = {
        'donors': donors_page, # <-- Pass the 'Page' object to the template
        'query': query,
        'last_sync': last_sync,
    }
    return render(request, 'tracker/donor_list.html', context)


# donor detail view

from .forms import DocumentForm # <-- Import the new form

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


def lot_detail(request, lot_id):
    """
    Displays a detailed timeline for a single Lot, combining
    all related documents and events in chronological order.
    """
    lot = get_object_or_404(Lot, id=lot_id)
    
    documents = lot.documents.all()
    events = lot.events.all()

    timeline_items = []
    for doc in documents:
        timeline_items.append({'item_type': 'Document', 'date': doc.uploaded_at, 'details': doc})
    
    for event in events:
        timeline_items.append({'item_type': 'Event', 'date': event.event_date, 'details': event})

    # Sort the combined list chronologically, with the most recent items first
    sorted_timeline = sorted(timeline_items, key=lambda x: x['date'], reverse=True)

    context = {
        'lot': lot,
        'timeline_items': sorted_timeline,
    }
    return render(request, 'tracker/lot_detail.html', context)


def sync_with_monday(request):
    if request.method == 'POST':
        API_URL = "https://api.monday.com/v2"
        API_TOKEN = settings.MONDAY_API_TOKEN
        headers = {"Authorization": API_TOKEN, "Content-Type": "application/json"}
        board_id = "8120988708" 
        date_column = "date4"

        # --- Pagination Setup ---
        limit = 100  # Fetch 100 items per API call
        cursor = None 
        items_synced = 0
        page_count = 1
        # ----------------------

        try:
            print("--- Starting Pagination Sync ---")
            
            while True:
                print(f"\n--- Fetching Page {page_count} ---")
                print(f"Using cursor: {cursor}")

                query = f'''
                    query ($limit: Int, $cursor: String) {{
                        boards(ids: {board_id}) {{
                            items_page(limit: $limit, cursor: $cursor) {{
                                cursor
                                items {{
                                    id
                                    name
                                    column_values(ids: ["{date_column}"]) {{
                                        id
                                        text
                                    }}
                                }}
                            }}
                        }}
                    }}
                '''
                variables = {'limit': limit, 'cursor': cursor}
                data = {'query': query, 'variables': variables}

                response = requests.post(API_URL, headers=headers, json=data)
                response.raise_for_status()
                results = response.json()
                
                # Safely get the items and the next cursor
                items_page = results.get('data', {}).get('boards', [{}])[0].get('items_page', {})
                items = items_page.get('items', [])
                
                print(f"API returned {len(items)} items on this page.")

                if not items:
                    print("No more items returned from API. Ending sync.")
                    break

                for item in items:
                    full_lot_id = item.get('name')
                    if not full_lot_id:
                        continue
                    
                    donor_id_str = full_lot_id[:9].strip()
                    product_type_str = full_lot_id[9:].strip().lstrip('- ')
                    
                    donor_object, _ = Donor.objects.get_or_create(donor_id=donor_id_str)
                    
                    # Use defaults to prevent overwriting existing data
                    Lot.objects.get_or_create(
                        lot_id=full_lot_id,
                        defaults={'donor': donor_object, 'product_type': product_type_str}
                    )
                    items_synced += 1
                
                # Get the cursor for the next page
                cursor = items_page.get('cursor')
                print(f"Next cursor: {cursor}")

                if not cursor:
                    print("API returned no next cursor. Ending sync.")
                    break
                
                page_count += 1
            
            SyncLog.objects.update_or_create(id=1)
            messages.success(request, f"Successfully processed {items_synced} items from Monday.com.")

        except Exception as e:
            logging.error("ERROR IN SYNC VIEW:", exc_info=True)
            messages.error(request, f"An error occurred during sync: {e}")

    return redirect('tracker:donor_list')