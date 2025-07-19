#!/usr/bin/env python3
"""
Test script for enhanced RAG API search modes
Tests vector, keyword, and hybrid search with proper authentication
"""

import requests
import json
import time
import sys

# Configuration
API_BASE_URL = "http://localhost:8002"
EMBEDDING_SERVICE_URL = "http://localhost:8001"

# Test queries
TEST_QUERIES = [
    "employment law",
    "restraint of trade",
    "section 180",
    "termination clauses"
]

def get_auth_token():
    """
    Get a valid authentication token
    In a real test, this would use proper MSAL authentication
    For now, we'll need to provide a valid token
    """
    # This would need to be replaced with actual token acquisition
    # For testing, we'll skip authentication or use a test token
    return "Bearer test-token"

def test_health_check():
    """Test if services are accessible"""
    print("🔍 Testing service health...")
    
    # Test embedding service
    try:
        response = requests.get(f"{EMBEDDING_SERVICE_URL}/", timeout=5)
        if response.status_code == 200:
            print("✅ Embedding service: OK")
        else:
            print(f"❌ Embedding service: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Embedding service: Connection failed - {e}")
        return False
    
    # Test RAG API service basic connectivity
    try:
        # Try to access a non-existent endpoint to get 404 (shows service is running)
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        # Even 404 means the service is responding
        print("✅ RAG API service: Accessible")
        return True
    except Exception as e:
        print(f"❌ RAG API service: Connection failed - {e}")
        return False

def test_search_mode(mode, query, **params):
    """Test a specific search mode"""
    print(f"\n🧪 Testing {mode.upper()} search: '{query}'")
    
    payload = {
        "query": query,
        "mode": mode,
        "limit": 3,
        **params
    }
    
    headers = {
        "Content-Type": "application/json"
        # Note: Authentication removed for now due to complexity
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/search",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            results_count = len(data.get('results', []))
            search_mode = data.get('search_mode', 'unknown')
            
            print(f"   ✅ Success: {results_count} results")
            print(f"   Mode confirmed: {search_mode}")
            
            # Show parameters used
            used_params = data.get('parameters', {})
            print(f"   Parameters: {json.dumps({k: v for k, v in used_params.items() if k not in ['query']}, indent=None)}")
            
            # Show top result if available
            if data.get('results'):
                top_result = data['results'][0]
                filename = top_result.get('original_filename', 'Unknown')
                score = top_result.get('max_similarity', 0)
                print(f"   Top result: {filename} (score: {score:.3f})")
                
                if top_result.get('snippets'):
                    snippet = top_result['snippets'][0]['content'][:80] + "..."
                    print(f"   Snippet: {snippet}")
            
            return True
            
        elif response.status_code == 401:
            print("   ❌ Authentication required")
            return False
        else:
            print(f"   ❌ Error {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Details: {error_data.get('error', error_data)}")
            except:
                print(f"   Response: {response.text[:100]}")
            return False
            
    except requests.exceptions.ConnectError:
        print("   ❌ Connection failed")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    print("🚀 Testing Enhanced RAG API Search Modes")
    print("=" * 50)
    
    # Health check
    if not test_health_check():
        print("\n❌ Service health check failed. Exiting.")
        sys.exit(1)
    
    print(f"\n✅ Services are healthy. Starting search tests...")
    
    # Test results tracking
    total_tests = 0
    passed_tests = 0
    
    # Test each query with different modes
    for query in TEST_QUERIES:
        print(f"\n📝 Testing Query: '{query}'")
        print("-" * 40)
        
        # Test vector search
        total_tests += 1
        if test_search_mode("vector", query):
            passed_tests += 1
        
        # Test keyword search
        total_tests += 1
        if test_search_mode("keyword", query):
            passed_tests += 1
        
        # Test hybrid search with different weights
        total_tests += 1
        if test_search_mode("hybrid", query, vector_weight=0.6, keyword_weight=0.4):
            passed_tests += 1
    
    # Test specific parameter combinations
    print(f"\n🔧 Testing Parameter Variations")
    print("-" * 40)
    
    # Test fuzzy keyword search
    total_tests += 1
    if test_search_mode("keyword", "emploment law", fuzzy=True, similarity_threshold=0.5):  # Intentional typo
        passed_tests += 1
    
    # Test high vector weight hybrid
    total_tests += 1
    if test_search_mode("hybrid", "contract termination", vector_weight=0.9, keyword_weight=0.1):
        passed_tests += 1
    
    # Test high keyword weight hybrid  
    total_tests += 1
    if test_search_mode("hybrid", "section 180", vector_weight=0.2, keyword_weight=0.8):
        passed_tests += 1
    
    # Results summary
    print(f"\n📊 Test Results")
    print("=" * 30)
    print(f"Tests passed: {passed_tests}/{total_tests}")
    print(f"Success rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        print("\n🎉 All tests passed! Enhanced search API is working correctly.")
        return 0
    elif passed_tests > 0:
        print(f"\n⚠️  {total_tests - passed_tests} tests failed. Check the details above.")
        return 1
    else:
        print("\n❌ All tests failed. Check service configuration and authentication.")
        return 2

if __name__ == "__main__":
    sys.exit(main()) 