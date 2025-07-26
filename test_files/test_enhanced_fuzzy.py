#!/usr/bin/env python3
"""
Test script for enhanced fuzzy search functions
Run this AFTER executing the SQL in enhanced_fuzzy_functions.sql
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

def test_enhanced_keyword_search(client: Client):
    """Test the enhanced keyword search function"""
    
    print("🔍 Testing Enhanced Keyword Search Function...")
    
    test_cases = [
        {
            'name': 'Normal search - taxpayer',
            'query': 'taxpayer',
            'fuzzy': False,
            'threshold': 0.3
        },
        {
            'name': 'Fuzzy search - taxpayer (same query)',
            'query': 'taxpayer',
            'fuzzy': True,
            'threshold': 0.3
        },
        {
            'name': 'Fuzzy search - taxpayeer (typo)',
            'query': 'taxpayeer',
            'fuzzy': True,
            'threshold': 0.3
        },
        {
            'name': 'Fuzzy search - taxpayeer (strict threshold)',
            'query': 'taxpayeer',
            'fuzzy': True,
            'threshold': 0.8
        },
        {
            'name': 'Fuzzy search - taxpayeer (loose threshold)',
            'query': 'taxpayeer',
            'fuzzy': True,
            'threshold': 0.1
        }
    ]
    
    for test in test_cases:
        print(f"\n📋 {test['name']}")
        try:
            result = client.rpc('search_documents_keyword_enhanced', {
                'search_query': test['query'],
                'result_limit': 3,
                'fuzzy_enabled': test['fuzzy'],
                'similarity_threshold': test['threshold']
            }).execute()
            
            if result.data and len(result.data) > 0:
                print(f"  ✅ Found {len(result.data)} results")
                print(f"  📄 Best score: {result.data[0]['score']:.4f}")
                print(f"  📝 Sample: {result.data[0]['snippet'][:80]}...")
            else:
                print(f"  ❌ No results found")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")

def test_comparison_function(client: Client):
    """Test the comparison function that shows fuzzy vs normal results side by side"""
    
    print("\n🔍 Testing Fuzzy vs Normal Comparison...")
    
    try:
        result = client.rpc('test_fuzzy_search', {
            'test_query': 'taxpayer',
            'test_typo': 'taxpayeer'
        }).execute()
        
        if result.data and len(result.data) > 0:
            print("  ✅ Comparison results:")
            for row in result.data:
                print(f"    📊 {row['test_type']} search with '{row['query_used']}': {row['result_count']} results, best score: {row['first_result_score']:.4f}")
        else:
            print("  ❌ No comparison data")
            
    except Exception as e:
        print(f"  ❌ Error in comparison test: {e}")

def test_enhanced_hybrid_search(client: Client):
    """Test the enhanced hybrid search function"""
    
    print("\n🔍 Testing Enhanced Hybrid Search Function...")
    
    try:
        # First get an embedding for testing
        print("  📡 Getting embedding for test query...")
        # We'll use a simple embedding for testing - in practice this would come from the embedding service
        test_embedding = [0.1] * 1024  # Simple test embedding
        
        result = client.rpc('search_documents_hybrid_enhanced', {
            'search_query': 'taxpayeer',  # Typo to test fuzzy
            'query_embedding': test_embedding,
            'vector_weight': 0.7,
            'keyword_weight': 0.3,
            'result_limit': 3,
            'rrf_k': 60,
            'fuzzy_enabled': True,
            'similarity_threshold': 0.3
        }).execute()
        
        if result.data and len(result.data) > 0:
            print(f"  ✅ Enhanced hybrid search found {len(result.data)} results")
            first_result = result.data[0]
            print(f"  📊 Scores - Vector: {first_result['vector_score']:.4f}, Keyword: {first_result['keyword_score']:.4f}, Hybrid: {first_result['hybrid_score']:.4f}")
            print(f"  🔗 Match sources: {first_result['match_sources']}")
        else:
            print(f"  ❌ No hybrid results found")
            
    except Exception as e:
        print(f"  ❌ Error in hybrid test: {e}")

def test_function_availability(client: Client):
    """Test if the enhanced functions are available"""
    
    print("🔍 Testing Function Availability...")
    
    functions_to_test = [
        'search_documents_keyword_enhanced',
        'search_documents_hybrid_enhanced',
        'test_fuzzy_search'
    ]
    
    available_functions = []
    
    for func_name in functions_to_test:
        try:
            # Try calling with minimal parameters to see if function exists
            if func_name == 'search_documents_keyword_enhanced':
                result = client.rpc(func_name, {
                    'search_query': 'test',
                    'result_limit': 1,
                    'fuzzy_enabled': False
                }).execute()
            elif func_name == 'search_documents_hybrid_enhanced':
                result = client.rpc(func_name, {
                    'search_query': 'test',
                    'query_embedding': [0.1] * 1024,
                    'result_limit': 1,
                    'fuzzy_enabled': False
                }).execute()
            elif func_name == 'test_fuzzy_search':
                result = client.rpc(func_name, {
                    'test_query': 'test'
                }).execute()
            
            print(f"  ✅ {func_name} - Available")
            available_functions.append(func_name)
            
        except Exception as e:
            if "Could not find the function" in str(e):
                print(f"  ❌ {func_name} - Not found")
            else:
                print(f"  ⚠️  {func_name} - Available but error: {e}")
                available_functions.append(func_name)
    
    return available_functions

def main():
    """Test enhanced fuzzy search functions"""
    print("🧪 Testing Enhanced Fuzzy Search Functions")
    print("=" * 50)
    print("⚠️  Make sure you've executed enhanced_fuzzy_functions.sql first!")
    print()
    
    # Initialize client
    client = get_supabase_client()
    if not client:
        return
    
    # Test function availability
    available_functions = test_function_availability(client)
    
    if not available_functions:
        print("\n❌ No enhanced functions found!")
        print("📋 Please execute the SQL in enhanced_fuzzy_functions.sql first")
        return
    
    # Test enhanced keyword search
    if 'search_documents_keyword_enhanced' in available_functions:
        test_enhanced_keyword_search(client)
    
    # Test comparison function
    if 'test_fuzzy_search' in available_functions:
        test_comparison_function(client)
    
    # Test enhanced hybrid search
    if 'search_documents_hybrid_enhanced' in available_functions:
        test_enhanced_hybrid_search(client)
    
    print("\n📋 Next Steps:")
    print("1. ✅ Enhanced functions tested")
    print("2. 🔄 Update application to use enhanced functions")
    print("3. 🔄 Pass fuzzy parameters from UI to database")

if __name__ == "__main__":
    main() 