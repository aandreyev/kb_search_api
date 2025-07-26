#!/usr/bin/env python3
"""
Comprehensive scoring analysis across all search modes
"""

import os
import json
from supabase import create_client, Client

def get_supabase_client():
    """Initialize Supabase client"""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not supabase_url or not supabase_key:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables required")
        return None
        
    return create_client(supabase_url, supabase_key)

def test_all_search_modes(client: Client):
    """Test all search modes with single and multi-word queries"""
    
    print("🔍 COMPREHENSIVE SCORING ANALYSIS")
    print("=" * 60)
    
    # Test queries
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
        }
    ]
    
    for case in test_cases:
        print(f"\n{'='*50}")
        print(f"🎯 TEST CASE: {case['name'].upper()}")
        print(f"   Query: '{case['query']}'")
        print(f"   Typo:  '{case['typo']}'")
        print(f"{'='*50}")
        
        # Test each search mode
        test_vector_search(client, case['query'])
        test_keyword_search_normal(client, case['query'])
        test_keyword_search_fuzzy(client, case['query'])
        test_keyword_search_fuzzy_typo(client, case['typo'])
        test_hybrid_search_normal(client, case['query'])
        test_hybrid_search_fuzzy(client, case['query'])
        test_hybrid_search_fuzzy_typo(client, case['typo'])

def test_vector_search(client: Client, query: str):
    """Test vector search scoring"""
    print(f"\n📊 1. VECTOR SEARCH: '{query}'")
    
    try:
        # Get embedding from the embedding service
        import requests
        embedding_response = requests.post(
            'http://localhost:8001/embed',
            json={'text': query}
        )
        if embedding_response.status_code == 200:
            embedding = embedding_response.json()['embedding']
            
            # Call vector search function
            result = client.rpc('match_chunks_for_rag', {
                'query_embedding': embedding,
                'match_count': 3
            }).execute()
            
            if result.data:
                print(f"   📈 Results: {len(result.data)}")
                for i, row in enumerate(result.data[:3]):
                    # Vector search uses cosine distance, convert to similarity
                    similarity = 1 - row.get('similarity', 0)
                    print(f"   📄 #{i+1}: Score {similarity:.6f} (distance: {row.get('similarity', 'N/A'):.6f})")
                    print(f"      📝 {row.get('content', '')[:60]}...")
            else:
                print("   ❌ No results")
        else:
            print(f"   ❌ Embedding service error: {embedding_response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

def test_keyword_search_normal(client: Client, query: str):
    """Test normal keyword search (full-text)"""
    print(f"\n📊 2. KEYWORD SEARCH (normal): '{query}'")
    
    try:
        result = client.rpc('search_documents_keyword', {
            'search_query': query,
            'result_limit': 3
        }).execute()
        
        if result.data:
            print(f"   📈 Results: {len(result.data)}")
            for i, row in enumerate(result.data[:3]):
                print(f"   📄 #{i+1}: Score {row['score']:.6f} (full-text)")
                print(f"      📝 {row['snippet'][:60]}...")
        else:
            print("   ❌ No results")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

def test_keyword_search_fuzzy(client: Client, query: str):
    """Test fuzzy keyword search"""
    print(f"\n📊 3. KEYWORD SEARCH (fuzzy): '{query}'")
    
    try:
        result = client.rpc('search_documents_keyword_enhanced', {
            'search_query': query,
            'result_limit': 3,
            'fuzzy_enabled': True,
            'similarity_threshold': 0.3
        }).execute()
        
        if result.data:
            print(f"   📈 Results: {len(result.data)}")
            for i, row in enumerate(result.data[:3]):
                print(f"   📄 #{i+1}: Score {row['score']:.6f} (trigram)")
                print(f"      📝 {row['snippet'][:60]}...")
        else:
            print("   ❌ No results")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

def test_keyword_search_fuzzy_typo(client: Client, typo_query: str):
    """Test fuzzy keyword search with typo"""
    print(f"\n📊 4. KEYWORD SEARCH (fuzzy + typo): '{typo_query}'")
    
    try:
        result = client.rpc('search_documents_keyword_enhanced', {
            'search_query': typo_query,
            'result_limit': 3,
            'fuzzy_enabled': True,
            'similarity_threshold': 0.3
        }).execute()
        
        if result.data:
            print(f"   📈 Results: {len(result.data)}")
            for i, row in enumerate(result.data[:3]):
                print(f"   📄 #{i+1}: Score {row['score']:.6f} (trigram + typo)")
                print(f"      📝 {row['snippet'][:60]}...")
        else:
            print("   ❌ No results")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

def test_hybrid_search_normal(client: Client, query: str):
    """Test hybrid search (normal)"""
    print(f"\n📊 5. HYBRID SEARCH (normal): '{query}'")
    
    try:
        # Get embedding
        import requests
        embedding_response = requests.post(
            'http://localhost:8001/embed',
            json={'text': query}
        )
        if embedding_response.status_code == 200:
            embedding = embedding_response.json()['embedding']
            
            result = client.rpc('search_documents_hybrid', {
                'search_query': query,
                'query_embedding': embedding,
                'vector_weight': 0.7,
                'keyword_weight': 0.3,
                'result_limit': 3,
                'rrf_k': 60
            }).execute()
            
            if result.data:
                print(f"   📈 Results: {len(result.data)}")
                for i, row in enumerate(result.data[:3]):
                    print(f"   📄 #{i+1}: Hybrid {row.get('hybrid_score', 0):.6f} "
                          f"(V:{row.get('vector_score', 0):.3f} + K:{row.get('keyword_score', 0):.3f} + RRF:{row.get('rrf_score', 0):.3f})")
                    print(f"      🔗 Sources: {row.get('match_sources', 'unknown')}")
                    print(f"      📝 {row.get('snippet', '')[:60]}...")
            else:
                print("   ❌ No results")
        else:
            print(f"   ❌ Embedding service error: {embedding_response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

def test_hybrid_search_fuzzy(client: Client, query: str):
    """Test hybrid search (fuzzy)"""
    print(f"\n📊 6. HYBRID SEARCH (fuzzy): '{query}'")
    
    try:
        # Get embedding
        import requests
        embedding_response = requests.post(
            'http://localhost:8001/embed',
            json={'text': query}
        )
        if embedding_response.status_code == 200:
            embedding = embedding_response.json()['embedding']
            
            result = client.rpc('search_documents_hybrid_enhanced', {
                'search_query': query,
                'query_embedding': embedding,
                'vector_weight': 0.7,
                'keyword_weight': 0.3,
                'result_limit': 3,
                'rrf_k': 60,
                'fuzzy_enabled': True,
                'similarity_threshold': 0.3
            }).execute()
            
            if result.data:
                print(f"   📈 Results: {len(result.data)}")
                for i, row in enumerate(result.data[:3]):
                    print(f"   📄 #{i+1}: Hybrid {row.get('hybrid_score', 0):.6f} "
                          f"(V:{row.get('vector_score', 0):.3f} + K:{row.get('keyword_score', 0):.3f} + RRF:{row.get('rrf_score', 0):.3f})")
                    print(f"      🔗 Sources: {row.get('match_sources', 'unknown')}")
                    print(f"      📝 {row.get('snippet', '')[:60]}...")
            else:
                print("   ❌ No results")
        else:
            print(f"   ❌ Embedding service error: {embedding_response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

def test_hybrid_search_fuzzy_typo(client: Client, typo_query: str):
    """Test hybrid search (fuzzy + typo)"""
    print(f"\n📊 7. HYBRID SEARCH (fuzzy + typo): '{typo_query}'")
    
    try:
        # Get embedding
        import requests
        embedding_response = requests.post(
            'http://localhost:8001/embed',
            json={'text': typo_query}
        )
        if embedding_response.status_code == 200:
            embedding = embedding_response.json()['embedding']
            
            result = client.rpc('search_documents_hybrid_enhanced', {
                'search_query': typo_query,
                'query_embedding': embedding,
                'vector_weight': 0.7,
                'keyword_weight': 0.3,
                'result_limit': 3,
                'rrf_k': 60,
                'fuzzy_enabled': True,
                'similarity_threshold': 0.3
            }).execute()
            
            if result.data:
                print(f"   📈 Results: {len(result.data)}")
                for i, row in enumerate(result.data[:3]):
                    print(f"   📄 #{i+1}: Hybrid {row.get('hybrid_score', 0):.6f} "
                          f"(V:{row.get('vector_score', 0):.3f} + K:{row.get('keyword_score', 0):.3f} + RRF:{row.get('rrf_score', 0):.3f})")
                    print(f"      🔗 Sources: {row.get('match_sources', 'unknown')}")
                    print(f"      📝 {row.get('snippet', '')[:60]}...")
            else:
                print("   ❌ No results")
        else:
            print(f"   ❌ Embedding service error: {embedding_response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

def analyze_score_ranges():
    """Analyze all the different score ranges"""
    
    print(f"\n{'='*60}")
    print("📊 SCORE RANGE ANALYSIS")
    print(f"{'='*60}")
    
    print("""
🎯 VECTOR SEARCH:
   • Score Type: Cosine similarity (1 - distance)
   • Range: 0.0 to 1.0 (1.0 = identical vectors)
   • Used in: Vector search, hybrid search vector component

🎯 KEYWORD SEARCH (Full-text):
   • Score Type: ts_rank (PostgreSQL full-text)
   • Range: 0.0 to ~0.1 (sometimes higher)
   • Used in: Normal keyword search, hybrid search keyword component

🎯 FUZZY SEARCH (Trigram):
   • Score Type: pg_trgm similarity
   • Range: 0.0 to 1.0 (1.0 = identical strings)
   • Used in: Fuzzy keyword search, fuzzy hybrid search

🎯 HYBRID SEARCH:
   • Combines: Vector + Keyword + RRF scores
   • Problem: Mixes different score ranges!
   • vector_weight * vector_score + keyword_weight * keyword_score
   • Example: 0.7 * 0.8 (vector) + 0.3 * 0.05 (keyword) = 0.575

🚨 MAJOR INCONSISTENCIES:
   1. Vector scores (0.0-1.0) vs Keyword scores (0.0-0.1)
   2. Fuzzy vs Non-fuzzy keyword scores (0.0-1.0 vs 0.0-0.1)
   3. Hybrid search mixing incompatible score ranges
   4. Multi-word queries may behave differently in fuzzy vs full-text

💡 SOLUTIONS NEEDED:
   1. Normalize ALL scores to same range (e.g., 0.0-1.0)
   2. OR: Use separate score types/indicators
   3. Fix hybrid search to handle mixed score ranges properly
   4. Test multi-word fuzzy matching behavior
    """)

def main():
    """Run comprehensive analysis"""
    
    client = get_supabase_client()
    if not client:
        return
    
    test_all_search_modes(client)
    analyze_score_ranges()

if __name__ == "__main__":
    main() 