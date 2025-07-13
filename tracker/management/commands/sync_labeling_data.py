import requests
import json
from django.core.management.base import BaseCommand
from django.conf import settings
from tracker.models import Lot, SubLot, Donor

class Command(BaseCommand):
    help = 'Creates or updates SubLots, creating placeholder parent Lots if necessary.'

    def handle(self, *args, **options):
        # --- CONFIGURATION (Use your real Column IDs from the LABELING board) ---
        API_URL = "https://api.monday.com/v2"
        API_TOKEN = settings.MONDAY_API_TOKEN
        headers = {"Authorization": API_TOKEN}
        
        labeling_board_id = "9440164519"
        
        labeled_by_col = "text5"
        labeled_date_col = "date43"
        final_qty_col = "numbers"
        chart_status_col = "status"
        # --- END CONFIGURATION ---

        query = f'''
            query ($limit: Int, $cursor: String) {{ 
                boards(ids: {labeling_board_id}) {{ 
                    items_page(limit: $limit, cursor: $cursor) {{ 
                        cursor
                        items {{
                            name
                            column_values(ids: [
                                "{labeled_by_col}", "{labeled_date_col}",
                                "{final_qty_col}", "{chart_status_col}"
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
        created_count = 0
        updated_count = 0
        skipped_count = 0
        total_fetched = 0
        page_count = 1

        self.stdout.write(f"--- Starting Sub-Lot Sync from board {labeling_board_id} ---")
        
        try:
            while True:
                self.stdout.write(f"\nFetching Page {page_count}...")
                variables = {'limit': limit, 'cursor': cursor}
                data = {'query': query, 'variables': variables}
                
                response = requests.post(API_URL, headers=headers, json=data)
                response.raise_for_status()
                results = response.json()

                if 'errors' in results and results['errors']:
                    self.stdout.write(self.style.ERROR(f"API Error: {results['errors'][0]['message']}"))
                    return

                items_page = results.get('data', {}).get('boards', [{}])[0].get('items_page', {})
                items = items_page.get('items', [])
                
                if not items:
                    self.stdout.write("No more items returned from API.")
                    break
                
                total_fetched += len(items)

                for item in items:
                    full_sublot_id = item.get('name')
                    self.stdout.write(f"-> Processing: '{full_sublot_id}'")

                    if not full_sublot_id:
                        self.stdout.write(self.style.WARNING("  SKIPPED: Item has no name."))
                        skipped_count += 1
                        continue

                    parts = full_sublot_id.split('-')
                    parent_id = '-'.join(parts[:-1]) if len(parts) > 2 else full_sublot_id
                    
                    try:
                        parent_lot_obj = Lot.objects.get(lot_id=parent_id)
                    except Lot.DoesNotExist:
                        # If the parent lot doesn't exist, create a placeholder for it
                        self.stdout.write(self.style.NOTICE(f"  Parent lot '{parent_id}' not found. Creating placeholder..."))
                        
                        donor_id_str = parent_id.split('-')[0]
                        product_type_str = parent_id.split('-')[1] if len(parent_id.split('-')) > 1 else ''
                        
                        donor_obj, _ = Donor.objects.get_or_create(donor_id=donor_id_str)
                        
                        parent_lot_obj, _ = Lot.objects.get_or_create(
                            lot_id=parent_id,
                            defaults={
                                'donor': donor_obj,
                                'product_type': product_type_str,
                                'data_source': 'PLACEHOLDER'
                            }
                        )

                    # Now that parent_lot_obj is guaranteed to exist, create or update the SubLot
                    labeled_by, labeled_date_str, final_qty, status = None, None, None, None
                    for col in item['column_values']:
                        col_text = col.get('text')
                        if col['id'] == labeled_by_col: labeled_by = col_text
                        elif col['id'] == labeled_date_col: labeled_date_str = col_text
                        elif col['id'] == final_qty_col: final_qty = int(col_text) if col_text and col_text.isdigit() else None
                        elif col['id'] == chart_status_col: status = col_text

                    if labeled_date_str and ' - ' in labeled_date_str:
                        labeled_date_str = labeled_date_str.split(' - ')[0]
                    
                    sublot, created = SubLot.objects.update_or_create(
                        sub_lot_id=full_sublot_id,
                        defaults={
                            'parent_lot': parent_lot_obj,
                            'labeled_by': labeled_by,
                            'labeled_date': labeled_date_str if labeled_date_str else None,
                            'final_quantity': final_qty,
                            'status': status,
                        }
                    )
                    
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                
                cursor = items_page.get('cursor')
                self.stdout.write(f"Page {page_count} processed. Next cursor: {cursor}")
                if not cursor:
                    break
                page_count += 1
            
            self.stdout.write(self.style.SUCCESS(f"\n--- SYNC COMPLETE ---"))
            self.stdout.write(f"Total Items Fetched: {total_fetched}")
            self.stdout.write(f"Sub-Lots Created: {created_count}")
            self.stdout.write(f"Sub-Lots Updated: {updated_count}")
            self.stdout.write(f"Items Skipped: {skipped_count}")

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"A script error occurred: {e}"))