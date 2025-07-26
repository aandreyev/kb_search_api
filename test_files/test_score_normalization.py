#!/usr/bin/env python3
"""
Test score normalization implementation
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

def test_normalized_scores(client: Client):
    """Test that all search modes return normalized scores"""
    
    print("🔍 TESTING SCORE NORMALIZATION")
    print("=" * 50)
    
    test_query = "taxpayer"
    typo_query = "taxpayeer"
    
    print(f"\n🎯 Testing with: '{test_query}' and '{typo_query}'")
    
    # Test the built-in normalization test function
    print(f"\n📊 BUILT-IN NORMALIZATION TEST:")
    try:
        result = client.rpc('test_score_normalization', {
            'test_query': test_query,
            'test_typo': typo_query
        }).execute()
        
        if result.data:
            for row in result.data:
                print(f"   {row['test_type']:20} | "
                      f"Score: {row['top_score']:.6f} | "
                      f"Type: {row['score_type']:10} | "
                      f"Range: {row['score_range']}")
        else:
            print("   ❌ No test results")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

def compare_before_after_normalization(client: Client):
    """Compare scores before and after normalization"""
    
    print(f"\n📊 BEFORE/AFTER NORMALIZATION COMPARISON")
    print("-" * 50)
    
    test_query = "taxpayer"
    
    # BEFORE: Original functions (non-normalized)
    print(f"\n🔴 BEFORE NORMALIZATION:")
    try:
        # Original keyword search
        original_keyword = client.rpc('search_documents_keyword', {
            'search_query': test_query,
            'result_limit': 3
        }).execute()
        
        if original_keyword.data:
            top_score = original_keyword.data[0]['score']
            print(f"   Original keyword search: {top_score:.6f} (range: ~0.0-0.1)")
        
        # Original fuzzy search  
        original_fuzzy = client.rpc('search_documents_keyword_enhanced', {
            'search_query': test_query,
            'result_limit': 3,
            'fuzzy_enabled': True
        }).execute()
        
        if original_fuzzy.data:
            fuzzy_score = original_fuzzy.data[0]['score']
            print(f"   Original fuzzy search:   {fuzzy_score:.6f} (range: 0.0-1.0)")
            
            if 'score_type' in original_fuzzy.data[0]:
                # This means we're testing after normalization is deployed
                print(f"   ✅ Score type field present: {original_fuzzy.data[0]['score_type']}")
                
    except Exception as e:
        print(f"   ❌ Error testing original functions: {e}")
    
    # AFTER: Normalized functions
    print(f"\n🟢 AFTER NORMALIZATION:")
    try:
        # Normalized keyword search
        normalized_keyword = client.rpc('search_documents_keyword_enhanced', {
            'search_query': test_query,
            'result_limit': 3,
            'fuzzy_enabled': False
        }).execute()
        
        if normalized_keyword.data:
            norm_keyword_score = normalized_keyword.data[0]['score']
            score_type = normalized_keyword.data[0].get('score_type', 'unknown')
            print(f"   Normalized keyword search: {norm_keyword_score:.6f} (type: {score_type})")
        
        # Normalized fuzzy search
        normalized_fuzzy = client.rpc('search_documents_keyword_enhanced', {
            'search_query': test_query,
            'result_limit': 3,
            'fuzzy_enabled': True
        }).execute()
        
        if normalized_fuzzy.data:
            norm_fuzzy_score = normalized_fuzzy.data[0]['score']
            score_type = normalized_fuzzy.data[0].get('score_type', 'unknown')
            print(f"   Normalized fuzzy search:   {norm_fuzzy_score:.6f} (type: {score_type})")
            
        # Calculate score difference ratio
        if normalized_keyword.data and normalized_fuzzy.data:
            ratio = norm_fuzzy_score / norm_keyword_score if norm_keyword_score > 0 else float('inf')
            print(f"\n📊 Score ratio (fuzzy/keyword): {ratio:.2f}x")
            
            if ratio < 2.0:
                print(f"   ✅ SUCCESS: Scores are now comparable (ratio < 2x)")
            else:
                print(f"   ⚠️  WARNING: Scores still have significant difference")
                
    except Exception as e:
        print(f"   ❌ Error testing normalized functions: {e}")

def test_multi_word_normalization(client: Client):
    """Test normalization with multi-word queries"""
    
    print(f"\n📊 MULTI-WORD QUERY NORMALIZATION")
    print("-" * 50)
    
    multi_word_queries = [
        "tax deduction",
        "capital gains tax",
        "business income tax"
    ]
    
    for query in multi_word_queries:
        print(f"\n🔍 Testing: '{query}'")
        
        try:
            # Normal search (normalized)
            normal_result = client.rpc('search_documents_keyword_enhanced', {
                'search_query': query,
                'result_limit': 3,
                'fuzzy_enabled': False
            }).execute()
            
            # Fuzzy search (normalized)
            fuzzy_result = client.rpc('search_documents_keyword_enhanced', {
                'search_query': query,
                'result_limit': 3,
                'fuzzy_enabled': True
            }).execute()
            
            normal_score = normal_result.data[0]['score'] if normal_result.data else 0
            fuzzy_score = fuzzy_result.data[0]['score'] if fuzzy_result.data else 0
            
            print(f"   Normal: {normal_score:.6f}")
            print(f"   Fuzzy:  {fuzzy_score:.6f}")
            
            if normal_score > 0 and fuzzy_score > 0:
                ratio = max(fuzzy_score, normal_score) / min(fuzzy_score, normal_score)
                print(f"   Ratio:  {ratio:.2f}x")
                
                if ratio < 3.0:
                    print(f"   ✅ Good: Comparable scores")
                else:
                    print(f"   ⚠️  High ratio - may need adjustment")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")

def validate_score_ranges(client: Client):
    """Validate that all scores are in 0.0-1.0 range"""
    
    print(f"\n📊 SCORE RANGE VALIDATION")
    print("-" * 50)
    
    test_queries = ["taxpayer", "tax deduction", "capital gains tax"]
    
    for query in test_queries:
        print(f"\n🔍 Testing: '{query}'")
        
        try:
            # Test both normal and fuzzy modes
            for fuzzy_enabled in [False, True]:
                mode = "fuzzy" if fuzzy_enabled else "normal"
                
                result = client.rpc('search_documents_keyword_enhanced', {
                    'search_query': query,
                    'result_limit': 5,
                    'fuzzy_enabled': fuzzy_enabled
                }).execute()
                
                if result.data:
                    scores = [row['score'] for row in result.data]
                    min_score = min(scores)
                    max_score = max(scores)
                    
                    print(f"   {mode:6} mode: {min_score:.6f} - {max_score:.6f}")
                    
                    # Validate range
                    if min_score >= 0.0 and max_score <= 1.0:
                        print(f"   ✅ {mode:6} scores in valid range [0.0-1.0]")
                    else:
                        print(f"   ❌ {mode:6} scores OUTSIDE valid range!")
                        
        except Exception as e:
            print(f"   ❌ Error: {e}")

def summarize_normalization_status(client: Client):
    """Summarize the current normalization status"""
    
    print(f"\n{'='*60}")
    print("📋 NORMALIZATION STATUS SUMMARY")
    print(f"{'='*60}")
    
    # Check if normalized functions exist
    functions_exist = True
    try:
        # Test if enhanced function with score_type exists
        result = client.rpc('search_documents_keyword_enhanced', {
            'search_query': 'test',
            'result_limit': 1,
            'fuzzy_enabled': False
        }).execute()
        
        if result.data and 'score_type' in result.data[0]:
            print("✅ Normalized functions are deployed")
            print("✅ Score type field is present")
        else:
            print("⚠️  Functions exist but score_type field missing")
            print("   Normalization may be partially deployed")
            
    except Exception as e:
        if "does not exist" in str(e) or "not found" in str(e):
            print("❌ Enhanced functions not yet deployed")
            functions_exist = False
        else:
            print(f"⚠️  Error testing functions: {e}")
    
    if functions_exist:
        print("\n🎯 READY FOR:")
        print("   • Application code updates")
        print("   • UI score display improvements") 
        print("   • Hybrid search testing")
    else:
        print("\n🎯 NEXT STEPS:")
        print("   1. Execute score_normalized_functions.sql in Supabase")
        print("   2. Run this test script again")
        print("   3. Update application code")

def main():
    """Run all normalization tests"""
    
    client = get_supabase_client()
    if not client:
        return
    
    test_normalized_scores(client)
    compare_before_after_normalization(client)
    test_multi_word_normalization(client)
    validate_score_ranges(client)
    summarize_normalization_status(client)

if __name__ == "__main__":
    main() 