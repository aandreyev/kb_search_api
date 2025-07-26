#!/usr/bin/env python3
"""
Investigate the actual database schema to fix the fuzzy search functions
"""

import os
from supabase import create_client, Client

def get_supabase_client():
    """Initialize Supabase client"""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not supabase_url or not supabase_key:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables required")
        return None
        
    return create_client(supabase_url, supabase_key)

def investigate_working_functions(client: Client):
    """Investigate the structure of working functions by examining their output"""
    
    print("🔍 Investigating Working Functions...")
    
    # Test existing keyword search to see the schema
    print("\n📋 Testing existing keyword search structure:")
    try:
        result = client.rpc('search_documents_keyword', {
            'search_query': 'taxpayer',
            'result_limit': 1
        }).execute()
        
        if result.data and len(result.data) > 0:
            print(f"  ✅ Keyword search returns:")
            row = result.data[0]
            for key, value in row.items():
                print(f"    📄 {key}: {type(value).__name__} = {value}")
        else:
            print("  ❌ No data returned")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Test existing hybrid search to see the schema
    print("\n📋 Testing existing hybrid search structure:")
    try:
        # Use correct 1024 dimensions
        test_embedding = [0.1] * 1024
        result = client.rpc('search_documents_hybrid', {
            'search_query': 'taxpayer',
            'query_embedding': test_embedding,
            'vector_weight': 0.7,
            'keyword_weight': 0.3,
            'result_limit': 1,
            'rrf_k': 60
        }).execute()
        
        if result.data and len(result.data) > 0:
            print(f"  ✅ Hybrid search returns:")
            row = result.data[0]
            for key, value in row.items():
                print(f"    📄 {key}: {type(value).__name__} = {value}")
        else:
            print("  ❌ No data returned")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")

def investigate_table_names(client: Client):
    """Try to find the correct table names"""
    
    print("\n🔍 Investigating Table Names...")
    
    # Common table name variations to try
    possible_table_names = [
        'chunks', 'chunk', 'document_chunks', 'content_chunks',
        'documents', 'document', 'files', 'content'
    ]
    
    print("\n📋 Testing possible table names with simple queries:")
    for table_name in possible_table_names:
        try:
            # Try a simple count query
            result = client.table(table_name).select("*", count="exact").limit(1).execute()
            print(f"  ✅ {table_name}: Found {result.count} rows")
            
            # If we found data, show some column info
            if result.data and len(result.data) > 0:
                columns = list(result.data[0].keys())
                print(f"    📄 Columns: {', '.join(columns[:10])}{'...' if len(columns) > 10 else ''}")
                
        except Exception as e:
            if "does not exist" in str(e).lower():
                print(f"  ❌ {table_name}: Does not exist")
            else:
                print(f"  ❓ {table_name}: Error - {e}")

def analyze_function_signatures(client: Client):
    """Analyze what function signatures actually exist"""
    
    print("\n🔍 Analyzing Function Signatures...")
    
    # Test the original functions with different parameter types
    print("\n📋 Testing original function parameter types:")
    
    # Test if the hybrid function expects different types
    test_cases = [
        {
            'name': 'float weights',
            'params': {
                'search_query': 'test',
                'query_embedding': [0.1] * 1024,
                'vector_weight': 0.7,  # float
                'keyword_weight': 0.3,  # float  
                'result_limit': 1,
                'rrf_k': 60
            }
        },
        {
            'name': 'int weights',
            'params': {
                'search_query': 'test',
                'query_embedding': [0.1] * 1024,
                'vector_weight': 1,  # int
                'keyword_weight': 0,  # int
                'result_limit': 1,
                'rrf_k': 60
            }
        }
    ]
    
    for test in test_cases:
        try:
            result = client.rpc('search_documents_hybrid', test['params']).execute()
            print(f"  ✅ {test['name']}: Works")
        except Exception as e:
            print(f"  ❌ {test['name']}: {e}")

def main():
    """Investigate database schema"""
    print("🔍 Database Schema Investigation")
    print("=" * 40)
    
    # Initialize client
    client = get_supabase_client()
    if not client:
        return
    
    # Investigate working functions
    investigate_working_functions(client)
    
    # Find correct table names
    investigate_table_names(client)
    
    # Analyze function signatures
    analyze_function_signatures(client)
    
    print("\n📋 Next Steps:")
    print("1. Use the correct table names found above")
    print("2. Fix data types in the SQL functions")
    print("3. Re-execute the corrected SQL")
    print("4. Test again")

if __name__ == "__main__":
    main() 