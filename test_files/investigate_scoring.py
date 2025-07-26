#!/usr/bin/env python3
"""
Investigate the scoring differences between normal and fuzzy search
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

def compare_scoring_systems(client: Client):
    """Compare the different scoring systems"""
    
    print("🔍 Investigating Scoring System Differences")
    print("=" * 50)
    
    test_query = "taxpayer"
    
    # Test 1: Original keyword search (full-text search)
    print(f"\n📋 1. ORIGINAL KEYWORD SEARCH: '{test_query}'")
    try:
        result = client.rpc('search_documents_keyword', {
            'search_query': test_query,
            'result_limit': 3
        }).execute()
        
        if result.data:
            print(f"  📊 Results: {len(result.data)}")
            for i, row in enumerate(result.data[:3]):
                print(f"  📄 #{i+1}: Score {row['score']:.6f} - {row['snippet'][:60]}...")
        else:
            print("  ❌ No results")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Test 2: Enhanced keyword search (fuzzy disabled - should be same as above)
    print(f"\n📋 2. ENHANCED KEYWORD SEARCH (fuzzy=false): '{test_query}'")
    try:
        result = client.rpc('search_documents_keyword_enhanced', {
            'search_query': test_query,
            'result_limit': 3,
            'fuzzy_enabled': False
        }).execute()
        
        if result.data:
            print(f"  📊 Results: {len(result.data)}")
            for i, row in enumerate(result.data[:3]):
                print(f"  📄 #{i+1}: Score {row['score']:.6f} - {row['snippet'][:60]}...")
        else:
            print("  ❌ No results")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Test 3: Enhanced keyword search (fuzzy enabled)
    print(f"\n📋 3. ENHANCED KEYWORD SEARCH (fuzzy=true): '{test_query}'")
    try:
        result = client.rpc('search_documents_keyword_enhanced', {
            'search_query': test_query,
            'result_limit': 3,
            'fuzzy_enabled': True,
            'similarity_threshold': 0.3
        }).execute()
        
        if result.data:
            print(f"  📊 Results: {len(result.data)}")
            for i, row in enumerate(result.data[:3]):
                print(f"  📄 #{i+1}: Score {row['score']:.6f} - {row['snippet'][:60]}...")
        else:
            print("  ❌ No results")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Test 4: Test with a typo
    typo_query = "taxpayeer"
    print(f"\n📋 4. FUZZY SEARCH WITH TYPO: '{typo_query}'")
    try:
        result = client.rpc('search_documents_keyword_enhanced', {
            'search_query': typo_query,
            'result_limit': 3,
            'fuzzy_enabled': True,
            'similarity_threshold': 0.3
        }).execute()
        
        if result.data:
            print(f"  📊 Results: {len(result.data)}")
            for i, row in enumerate(result.data[:3]):
                print(f"  📄 #{i+1}: Score {row['score']:.6f} - {row['snippet'][:60]}...")
        else:
            print("  ❌ No results")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")

def analyze_scoring_types(client: Client):
    """Analyze what scoring functions PostgreSQL is using"""
    
    print("\n🔬 Analyzing Scoring Function Types")
    print("=" * 40)
    
    # Let's test the different PostgreSQL similarity functions directly
    test_cases = [
        {
            'name': 'similarity()',
            'query': "SELECT similarity('taxpayer', 'taxpayer') as score_exact, similarity('taxpayer', 'taxpayeer') as score_typo"
        },
        {
            'name': 'word_similarity()', 
            'query': "SELECT word_similarity('taxpayer', 'taxpayer content here') as score_exact, word_similarity('taxpayeer', 'taxpayer content here') as score_typo"
        }
    ]
    
    for test in test_cases:
        print(f"\n📊 {test['name']}:")
        try:
            # Use raw SQL query
            result = client.postgrest.rpc('exec_sql', {'sql': test['query']}).execute()
            print(f"  ✅ {result.data}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            # Try alternative approach
            try:
                print(f"  🔄 SQL: {test['query']}")
            except:
                pass

def understand_score_ranges():
    """Explain the different score ranges"""
    
    print("\n📚 Understanding Score Ranges")
    print("=" * 35)
    print()
    print("🎯 FULL-TEXT SEARCH (ts_rank):")
    print("   • Range: 0.0 to ~0.1 (sometimes higher)")  
    print("   • Based on: Term frequency, document length, position")
    print("   • Used by: Original search_documents_keyword function")
    print()
    print("🎯 TRIGRAM SIMILARITY (pg_trgm):")
    print("   • Range: 0.0 to 1.0")
    print("   • 1.0 = Identical strings")
    print("   • 0.8 = Very similar (like 'taxpayer' vs 'taxpayeer')")
    print("   • Used by: Enhanced fuzzy search functions")
    print()
    print("🚨 THE PROBLEM:")
    print("   • When fuzzy=false: Uses full-text scores (0.0-0.1)")
    print("   • When fuzzy=true: Uses trigram scores (0.0-1.0)")
    print("   • Same query, different score ranges!")
    print()
    print("💡 POTENTIAL SOLUTIONS:")
    print("   1. Normalize fuzzy scores to match full-text range")
    print("   2. Always use one scoring system")
    print("   3. Add score type indicator to results")

def main():
    """Main investigation"""
    
    client = get_supabase_client()
    if not client:
        return
    
    compare_scoring_systems(client)
    analyze_scoring_types(client)
    understand_score_ranges()

if __name__ == "__main__":
    main() 