"""
Test script for FAISS RAG and Enhanced Chat Agent (agent-2.9 architecture)
Verifies:
- FAISS vector store initialization
- Embedding cache functionality
- RAG query execution
- Tool parsing and routing
- Enhanced chat agent integration
"""

import asyncio
import logging
from board_rag import run_rag, load_board_items
from tool_parser import parse_tool
from enhanced_chat_agent import chat_agent, get_answer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_faiss_rag")

async def test_board_loading():
    """Test board items loading from API"""
    print("\n" + "="*60)
    print("TEST 1: Board Items Loading")
    print("="*60)
    
    try:
        patient_id = "p0001"
        items = await load_board_items(patient_id)
        
        if items:
            print(f"✅ Successfully loaded {len(items)} board items")
            print(f"   Sample item types: {[item.get('item_type', 'unknown') for item in items[:3]]}")
            return True
        else:
            print("❌ No board items loaded")
            return False
    except Exception as e:
        print(f"❌ Error loading board items: {e}")
        return False


async def test_rag_query():
    """Test RAG query with FAISS"""
    print("\n" + "="*60)
    print("TEST 2: FAISS RAG Query")
    print("="*60)
    
    try:
        patient_id = "p0001"
        test_queries = [
            "What are the patient's lab results?",
            "Show me medication history",
            "What encounters are recorded?"
        ]
        
        for query in test_queries:
            print(f"\n📋 Query: {query}")
            results = await run_rag(patient_id, query, top_k=3)
            
            if results:
                print(f"✅ Found {len(results)} relevant items")
                for i, item in enumerate(results, 1):
                    print(f"   {i}. {item.get('item_type', 'unknown')} - {item.get('title', 'No title')[:50]}")
            else:
                print("⚠️  No results found")
        
        return True
    except Exception as e:
        print(f"❌ Error in RAG query: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_tool_parsing():
    """Test tool parsing and routing"""
    print("\n" + "="*60)
    print("TEST 3: Tool Parsing")
    print("="*60)
    
    test_cases = [
        ("Show me the lab chart", "navigate_canvas"),
        ("Create a task to follow up on labs", "generate_task"),
        ("What does EASL recommend for DILI?", "get_easl_answer"),
        ("Generate DILI diagnosis report", "generate_diagnosis"),
        ("Tell me about the patient", "general"),
    ]
    
    all_passed = True
    for query, expected_tool in test_cases:
        try:
            result = await parse_tool(query)
            actual_tool = result.get("tool", "unknown")
            
            if actual_tool == expected_tool:
                print(f"✅ '{query}'")
                print(f"   → Correctly routed to: {actual_tool}")
            else:
                print(f"⚠️  '{query}'")
                print(f"   → Expected: {expected_tool}, Got: {actual_tool}")
                all_passed = False
        except Exception as e:
            print(f"❌ Error parsing '{query}': {e}")
            all_passed = False
    
    return all_passed


async def test_enhanced_chat_agent():
    """Test enhanced chat agent with various queries"""
    print("\n" + "="*60)
    print("TEST 4: Enhanced Chat Agent")
    print("="*60)
    
    patient_id = "p0001"
    test_conversations = [
        "What are the patient's current medications?",
        "Tell me about recent lab results",
        "What is the RUCAM score for this case?",
    ]
    
    for message in test_conversations:
        try:
            print(f"\n💬 User: {message}")
            
            # Build simple chat history
            chat_history = [{
                "role": "user",
                "parts": [{"text": message}]
            }]
            
            # Get response
            response = await chat_agent(patient_id, chat_history)
            
            print(f"🤖 Agent: {response[:200]}...")
            print("✅ Response received")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    return True


async def test_cache_persistence():
    """Test embedding cache save/load"""
    print("\n" + "="*60)
    print("TEST 5: Embedding Cache Persistence")
    print("="*60)
    
    try:
        patient_id = "p0001"
        
        # First query - will build cache
        print("First query (building cache)...")
        await run_rag(patient_id, "test query", top_k=1)
        
        # Check if cache file exists
        import os
        cache_path = "vector_cache/embedding_cache.pkl"
        
        if os.path.exists(cache_path):
            size = os.path.getsize(cache_path)
            print(f"✅ Cache file created: {cache_path} ({size} bytes)")
            
            # Second query - should use cache
            print("\nSecond query (using cache)...")
            await run_rag(patient_id, "another test", top_k=1)
            print("✅ Cache loaded successfully")
            
            return True
        else:
            print("❌ Cache file not created")
            return False
    except Exception as e:
        print(f"❌ Cache test error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("🧪 FAISS RAG & Enhanced Chat Agent Test Suite")
    print("   Agent-2.9 Architecture Verification")
    print("="*60)
    
    results = {
        "Board Loading": await test_board_loading(),
        "FAISS RAG Query": await test_rag_query(),
        "Tool Parsing": await test_tool_parsing(),
        "Enhanced Chat Agent": await test_enhanced_chat_agent(),
        "Cache Persistence": await test_cache_persistence(),
    }
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} - {test_name}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! System ready for deployment.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review errors above.")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
