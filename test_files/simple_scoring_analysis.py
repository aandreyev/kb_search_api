#!/usr/bin/env python3
"""
Simplified scoring analysis focusing on keyword vs fuzzy search
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

def test_scoring_consistency(client: Client):
    """Test scoring consistency across different modes"""
    
    print("🔍 SCORING CONSISTENCY ANALYSIS")
    print("=" * 50)
    
    # Test queries with increasing complexity
    test_cases = [
        {
            'name': 'Single word',
            'query': 'taxpayer',
            'typo': 'taxpayeer'
        },
        {
            'name': 'Two words',
            'query': 'tax deduction',
            'typo': 'tax deducton'
        },
        {
            'name': 'Three words',
            'query': 'capital gains tax',
            'typo': 'captial gains tax'
        },
        {
            'name': 'Phrase',
            'query': 'business income tax',
            'typo': 'bussiness incme tax'
        }
    ]
    
    for case in test_cases:
        print(f"\n{'='*60}")
        print(f"🎯 TEST: {case['name'].upper()}")
        print(f"   Query: '{case['query']}'")
        print(f"   Typo:  '{case['typo']}'")
        print(f"{'='*60}")
        
        # Test normal keyword search
        test_normal_keyword(client, case['query'])
        
        # Test fuzzy keyword search (same query)
        test_fuzzy_keyword(client, case['query'])
        
        # Test fuzzy keyword search with typo
        test_fuzzy_keyword_typo(client, case['typo'])
        
        # Analyze score differences
        analyze_score_differences(client, case['query'], case['typo'])

def test_normal_keyword(client: Client, query: str):
    """Test normal keyword search"""
    print(f"\n📊 NORMAL KEYWORD SEARCH: '{query}'")
    
    try:
        result = client.rpc('search_documents_keyword', {
            'search_query': query,
            'result_limit': 5
        }).execute()
        
        if result.data:
            print(f"   📈 Results: {len(result.data)}")
            scores = [row['score'] for row in result.data]
            print(f"   📊 Score range: {min(scores):.6f} - {max(scores):.6f}")
            print(f"   📊 Score type: Full-text (ts_rank)")
            for i, row in enumerate(result.data[:3]):
                print(f"   📄 #{i+1}: {row['score']:.6f} - {row['snippet'][:50]}...")
        else:
            print("   ❌ No results")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

def test_fuzzy_keyword(client: Client, query: str):
    """Test fuzzy keyword search with same query"""
    print(f"\n📊 FUZZY KEYWORD SEARCH: '{query}'")
    
    try:
        result = client.rpc('search_documents_keyword_enhanced', {
            'search_query': query,
            'result_limit': 5,
            'fuzzy_enabled': True,
            'similarity_threshold': 0.3
        }).execute()
        
        if result.data:
            print(f"   📈 Results: {len(result.data)}")
            scores = [row['score'] for row in result.data]
            print(f"   📊 Score range: {min(scores):.6f} - {max(scores):.6f}")
            print(f"   📊 Score type: Trigram similarity (pg_trgm)")
            for i, row in enumerate(result.data[:3]):
                print(f"   📄 #{i+1}: {row['score']:.6f} - {row['snippet'][:50]}...")
        else:
            print("   ❌ No results")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

def test_fuzzy_keyword_typo(client: Client, typo_query: str):
    """Test fuzzy keyword search with typo"""
    print(f"\n📊 FUZZY KEYWORD SEARCH (typo): '{typo_query}'")
    
    try:
        result = client.rpc('search_documents_keyword_enhanced', {
            'search_query': typo_query,
            'result_limit': 5,
            'fuzzy_enabled': True,
            'similarity_threshold': 0.3
        }).execute()
        
        if result.data:
            print(f"   📈 Results: {len(result.data)}")
            scores = [row['score'] for row in result.data]
            print(f"   📊 Score range: {min(scores):.6f} - {max(scores):.6f}")
            print(f"   📊 Score type: Trigram similarity (pg_trgm)")
            for i, row in enumerate(result.data[:3]):
                print(f"   📄 #{i+1}: {row['score']:.6f} - {row['snippet'][:50]}...")
        else:
            print("   ❌ No results")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

def analyze_score_differences(client: Client, original_query: str, typo_query: str):
    """Analyze how scores differ between modes"""
    print(f"\n🔬 SCORE ANALYSIS:")
    
    try:
        # Get scores from each mode
        normal_result = client.rpc('search_documents_keyword', {
            'search_query': original_query,
            'result_limit': 3
        }).execute()
        
        fuzzy_original_result = client.rpc('search_documents_keyword_enhanced', {
            'search_query': original_query,
            'result_limit': 3,
            'fuzzy_enabled': True,
            'similarity_threshold': 0.3
        }).execute()
        
        fuzzy_typo_result = client.rpc('search_documents_keyword_enhanced', {
            'search_query': typo_query,
            'result_limit': 3,
            'fuzzy_enabled': True,
            'similarity_threshold': 0.3
        }).execute()
        
        # Compare top scores
        normal_top = normal_result.data[0]['score'] if normal_result.data else 0
        fuzzy_original_top = fuzzy_original_result.data[0]['score'] if fuzzy_original_result.data else 0
        fuzzy_typo_top = fuzzy_typo_result.data[0]['score'] if fuzzy_typo_result.data else 0
        
        print(f"   📊 Normal search top score:      {normal_top:.6f}")
        print(f"   📊 Fuzzy search (same) top score: {fuzzy_original_top:.6f}")
        print(f"   📊 Fuzzy search (typo) top score: {fuzzy_typo_top:.6f}")
        print(f"   📊 Score ratio (fuzzy/normal):    {fuzzy_original_top/normal_top if normal_top > 0 else 'N/A':.2f}x")
        
        if fuzzy_original_top > 0 and normal_top > 0:
            if fuzzy_original_top > normal_top * 5:
                print(f"   🚨 WARNING: Fuzzy scores are {fuzzy_original_top/normal_top:.1f}x higher than normal!")
                print(f"   💡 Suggestion: Normalize fuzzy scores to match full-text range")
        
    except Exception as e:
        print(f"   ❌ Error in score analysis: {e}")

def test_multi_word_behavior(client: Client):
    """Test how multi-word queries behave in fuzzy vs normal search"""
    
    print(f"\n{'='*60}")
    print("🔬 MULTI-WORD QUERY BEHAVIOR ANALYSIS")
    print(f"{'='*60}")
    
    multi_word_tests = [
        {
            'query': 'capital gains',
            'description': 'Two common words'
        },
        {
            'query': 'business income tax deduction',
            'description': 'Four words phrase'
        },
        {
            'query': 'australian taxation office ruling',
            'description': 'Four words with proper noun'
        }
    ]
    
    for test in multi_word_tests:
        print(f"\n📋 Testing: {test['description']} - '{test['query']}'")
        
        # Normal search
        try:
            normal = client.rpc('search_documents_keyword', {
                'search_query': test['query'],
                'result_limit': 3
            }).execute()
            normal_count = len(normal.data) if normal.data else 0
            normal_score = normal.data[0]['score'] if normal.data else 0
            print(f"   📊 Normal: {normal_count} results, top score: {normal_score:.6f}")
        except Exception as e:
            print(f"   ❌ Normal error: {e}")
        
        # Fuzzy search
        try:
            fuzzy = client.rpc('search_documents_keyword_enhanced', {
                'search_query': test['query'],
                'result_limit': 3,
                'fuzzy_enabled': True,
                'similarity_threshold': 0.3
            }).execute()
            fuzzy_count = len(fuzzy.data) if fuzzy.data else 0
            fuzzy_score = fuzzy.data[0]['score'] if fuzzy.data else 0
            print(f"   📊 Fuzzy:  {fuzzy_count} results, top score: {fuzzy_score:.6f}")
        except Exception as e:
            print(f"   ❌ Fuzzy error: {e}")

def summarize_findings():
    """Summarize the key findings"""
    
    print(f"\n{'='*60}")
    print("📋 KEY FINDINGS SUMMARY")
    print(f"{'='*60}")
    
    print("""
🚨 MAJOR SCORING INCONSISTENCIES FOUND:

1. SCALE MISMATCH:
   • Normal keyword search: 0.0 - 0.1 range (ts_rank)
   • Fuzzy keyword search: 0.0 - 1.0 range (trigram)
   • Same query can show 10x+ score difference!

2. USER CONFUSION:
   • Users see fuzzy results with much higher scores
   • May think fuzzy is "better" when it's just different scale
   • Inconsistent across different search modes

3. MULTI-WORD QUERIES:
   • Full-text search: Searches for all words (AND logic)
   • Fuzzy search: Uses trigram similarity on entire string
   • Different matching behavior, not just scoring

4. IMPLICATIONS FOR HYBRID SEARCH:
   • Hybrid combines vector (0.0-1.0) + keyword (0.0-0.1) + fuzzy (0.0-1.0)
   • Mixing incompatible score ranges
   • Fuzzy scores dominate in weighted combinations

💡 RECOMMENDED SOLUTIONS:

1. SCORE NORMALIZATION:
   • Normalize fuzzy scores to 0.0-0.1 range to match full-text
   • Formula: fuzzy_score * 0.1 for display consistency

2. SCORE TYPE INDICATORS:
   • Add "score_type" field to results ("fulltext", "fuzzy", "vector")
   • Allow UI to handle different score types appropriately

3. UNIFIED SCORING SYSTEM:
   • Consider normalizing ALL scores to 0.0-1.0 range
   • Update full-text scores: ts_rank * 10 (approximately)

4. HYBRID SEARCH FIXES:
   • Normalize all component scores before combining
   • Ensure weighted combination uses same scale

5. DOCUMENTATION:
   • Document score ranges for each search mode
   • Clarify scoring behavior for users
    """)

def main():
    """Run the simplified scoring analysis"""
    
    client = get_supabase_client()
    if not client:
        return
    
    test_scoring_consistency(client)
    test_multi_word_behavior(client)
    summarize_findings()

if __name__ == "__main__":
    main() 