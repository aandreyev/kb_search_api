import os
from dotenv import load_dotenv
from supabase import create_client, Client

def main():
    """Compares documents in the Supabase database table against files in Supabase Storage."""
    print("Starting storage synchronization check...")

    # 1. Load Configuration
    load_dotenv()
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    documents_table_name = os.getenv("SUPABASE_DOCUMENTS_TABLE", "documents")
    storage_bucket_name = os.getenv("SUPABASE_BUCKET_NAME")
    db_cleaned_filename_column = "cleaned_filename"
    db_original_path_column = "original_path" # Column for the SharePoint/original path
    # This prefix is WHERE the files (named by cleaned_filename) are located INSIDE the bucket.
    storage_file_prefix = "documents/" # Used for LISTING from storage.

    if not all([supabase_url, supabase_key, storage_bucket_name, documents_table_name]):
        print("Error: Supabase URL, Key, Bucket Name, or Documents Table Name not configured in .env file.")
        return

    print(f"Supabase URL: {supabase_url}")
    print(f"Documents Table: {documents_table_name} (using column: '{db_cleaned_filename_column}' with prefix '{storage_file_prefix}')")
    print(f"Storage Bucket: {storage_bucket_name}")

    # 2. Initialize Supabase Client
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        print("Supabase client initialized successfully.")
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")
        return

    # 3. Fetch All Document Records from the Database Table
    db_document_info = {} # Store {cleaned_filename: {'id': id, 'original_path': original_path}}
    print(f"Fetching document details from table '{documents_table_name}'...")
    db_debug_printed_count = 0
    try:
        offset = 0
        limit = 1000 # Process all records
        while True:
            select_statement = f"id, {db_cleaned_filename_column}, {db_original_path_column}"
            response = supabase.table(documents_table_name)\
                               .select(select_statement)\
                               .range(offset, offset + limit - 1)\
                               .execute()
            
            if response.data:
                for record in response.data:
                    filename = record.get(db_cleaned_filename_column)
                    record_id = record.get("id")
                    original_path = record.get(db_original_path_column)

                    if filename:
                        # Use filename as is (only strip slashes for consistency)
                        clean_filename_key = filename.strip('/') 
                        db_document_info[clean_filename_key] = {
                            'id': record_id,
                            'original_path': original_path
                        }
                        if db_debug_printed_count < 5:
                            print(f"  DEBUG (DB Record {db_debug_printed_count + 1}): '{db_cleaned_filename_column}': '{filename}', ID: {record_id}, Original Path: '{original_path}', Key for Set: '{clean_filename_key}'")
                            db_debug_printed_count += 1
                
                if len(response.data) < limit:
                    break # Reached the end of actual data
                offset += limit
            else:
                if hasattr(response, 'error') and response.error:
                    print(f"Supabase query error: {response.error}")
                break # No more data or error
        print(f"Found {len(db_document_info)} unique storage paths in the database table.")

    except Exception as e:
        print(f"Error fetching document paths from database: {e}")
        return

    # 4. List All Files in Supabase Storage Bucket
    storage_file_paths = set() # This will store just the names from storage, relative to prefix
    print(f"Listing files in Supabase Storage bucket '{storage_bucket_name}' at prefix '{storage_file_prefix}'...")
    storage_debug_printed_count = 0
    try:
        offset = 0
        limit_storage = 100 # Supabase storage list limit
        while True:
            list_path_prefix = storage_file_prefix.strip('/')
            res = supabase.storage.from_(storage_bucket_name).list(path=list_path_prefix ,options={"limit": limit_storage, "offset": offset})
            
            if res:
                for file_object in res:
                    filename_from_storage = file_object['name'] 
                    if filename_from_storage: 
                        # Use filename as is (only strip slashes for consistency)
                        clean_filename_storage_key = filename_from_storage.strip('/')
                        if storage_debug_printed_count < 5:
                            print(f"  DEBUG (Storage Item {storage_debug_printed_count + 1}): Storage object name: '{filename_from_storage}', Key for Set: '{clean_filename_storage_key}'")
                            storage_debug_printed_count += 1
                        storage_file_paths.add(clean_filename_storage_key) 
                
                if len(res) < limit_storage:
                    break # Reached the end of actual data
                offset += limit_storage
            else:
                if hasattr(res, 'error') and res.error:
                    print(f"Supabase storage listing error: {res.error}")
                break # No more data or error
        print(f"Found {len(storage_file_paths)} unique storage paths in the storage bucket.")

    except Exception as e:
        print(f"Error listing files from Supabase Storage: {e}")
        # Check if it's an auth error, which can sometimes manifest this way with storage
        if "JWT" in str(e) or "Unauthorized" in str(e):
            print("Hint: This might be an authentication issue or RLS policy on storage buckets.")
        return

    # 5. Compare the two sets
    report_lines = ["--- Storage Synchronization Report ---"]
    print("\n--- Comparison Results ---") # Keep printing to console as well

    # Files in DB but not in Storage
    db_filenames_set = set(db_document_info.keys())
    db_only_filenames = db_filenames_set - storage_file_paths

    report_lines.append(f"\n=== '{db_cleaned_filename_column}' values from DB Not Found as filenames in Storage (at prefix '{storage_file_prefix}') ({len(db_only_filenames)}) ===")
    if db_only_filenames:
        print(f"\nWARNING: {len(db_only_filenames)} '{db_cleaned_filename_column}' values from DB NOT found as direct filenames in Storage at prefix '{storage_file_prefix}':")
        # Add a header line for the CSV-like format in the report for this section
        report_lines.append("DB_ID,Original_Path") 
        for filename_key in sorted(list(db_only_filenames)):
            doc_info = db_document_info.get(filename_key, {'id': 'N/A', 'original_path': 'N/A'})
            # Detailed line for console
            console_line = f"  - Filename (from DB '{db_cleaned_filename_column}'): {filename_key} (DB ID: {doc_info['id']}, DB Original Path: {doc_info['original_path']})"
            print(console_line)
            
            # CSV-like format for the report file: ID,Original_Path
            report_id = doc_info.get('id', 'N/A')
            report_original_path = doc_info.get('original_path', 'N/A')
            report_lines.append(f"{report_id},{report_original_path}")
    else:
        msg = "\nINFO: All '{db_cleaned_filename_column}' entries in DB appear to have a matching filename in Storage at the specified prefix.".format(db_cleaned_filename_column=db_cleaned_filename_column)
        print(msg)
        report_lines.append(msg)

    # Files in Storage but not in DB (orphaned files)
    storage_only_filenames = storage_file_paths - db_filenames_set
    report_lines.append(f"\n=== Filenames in Storage (at prefix '{storage_file_prefix}') Not Found as '{db_cleaned_filename_column}' in DB ({len(storage_only_filenames)}) ===")
    if storage_only_filenames:
        print(f"\nWARNING: {len(storage_only_filenames)} filenames found in Storage (at prefix '{storage_file_prefix}') but NOT in database table as '{db_cleaned_filename_column}':")
        for storage_filename_key in sorted(list(storage_only_filenames)):
            # Construct full path for report, as this is what's truly in storage
            full_path_in_storage = storage_file_prefix.strip('/') + '/' + storage_filename_key if storage_file_prefix.strip('/') else storage_filename_key
            line_for_report = f"  - {full_path_in_storage}"
            print(line_for_report)
            report_lines.append(line_for_report)
    else:
        msg = "\nINFO: All files in the Storage bucket (at the specified prefix) appear to have corresponding database records via '{db_cleaned_filename_column}'.".format(db_cleaned_filename_column=db_cleaned_filename_column)
        print(msg)
        report_lines.append(msg)

    if not db_only_filenames and not storage_only_filenames:
        success_msg = "\nSUCCESS: Database records ('{db_cleaned_filename_column}') and Storage filenames (at prefix '{storage_file_prefix}') appear to be in sync!".format(db_cleaned_filename_column=db_cleaned_filename_column, storage_file_prefix=storage_file_prefix)
        print(success_msg)
        report_lines.append(success_msg)
    
    # Write report to file
    report_file_name = "storage_sync_report.txt"
    try:
        with open(report_file_name, "w") as f:
            for line in report_lines:
                f.write(line + "\n")
        print(f"\nReport written to {report_file_name}")
    except Exception as e:
        print(f"\nERROR: Could not write report to file: {e}")

    print("\nStorage synchronization check finished.")

if __name__ == "__main__":
    main() 