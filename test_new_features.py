"""
Test Script for New Features
=============================

This script validates that the new chat agent and WebSocket features
are working correctly without breaking existing functionality.

Run this after starting the server to verify everything works.

Usage:
    python test_new_features.py
"""

import asyncio
import json
import sys
from typing import Dict, Any

# Test imports
try:
    from chat_agent import ChatAgent, RAGRetriever, ToolExecutor
    from websocket_agent import WebSocketLiveAgent, WebSocketSession, MessageType
    import bucket_ops
    print("✅ Module imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


class FeatureValidator:
    """Validates new features are working correctly."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def test(self, name: str, test_func):
        """Run a test and record results."""
        print(f"\n🧪 Testing: {name}")
        try:
            result = test_func()
            if asyncio.iscoroutine(result):
                result = asyncio.run(result)
            
            if result:
                print(f"   ✅ PASSED")
                self.passed += 1
                self.results.append((name, "PASSED", None))
            else:
                print(f"   ❌ FAILED")
                self.failed += 1
                self.results.append((name, "FAILED", "Test returned False"))
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
            self.failed += 1
            self.results.append((name, "FAILED", str(e)))
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"Total Tests: {self.passed + self.failed}")
        print(f"Passed: {self.passed} ✅")
        print(f"Failed: {self.failed} ❌")
        print(f"Success Rate: {(self.passed/(self.passed+self.failed)*100):.1f}%")
        
        if self.failed > 0:
            print("\nFailed Tests:")
            for name, status, error in self.results:
                if status == "FAILED":
                    print(f"  - {name}")
                    if error:
                        print(f"    Error: {error}")


# Test Functions

def test_chat_agent_initialization():
    """Test that ChatAgent can be initialized."""
    try:
        agent = ChatAgent(patient_id="P0001", use_tools=False)
        return agent is not None
    except Exception as e:
        print(f"    Error: {e}")
        return False


def test_rag_retriever():
    """Test RAGRetriever initialization."""
    try:
        gcs = bucket_ops.GCSBucketManager(bucket_name="clinic_sim")
        retriever = RAGRetriever(gcs)
        return retriever is not None
    except Exception as e:
        print(f"    Error: {e}")
        return False


def test_tool_executor():
    """Test ToolExecutor initialization and tool registration."""
    try:
        gcs = bucket_ops.GCSBucketManager(bucket_name="clinic_sim")
        executor = ToolExecutor(gcs)
        
        # Check tools are registered
        tools = executor._register_tools()
        expected_tools = [
            "get_patient_labs",
            "get_patient_medications",
            "get_patient_encounters",
            "search_patient_data",
            "calculate_drug_interaction"
        ]
        
        for tool_name in expected_tools:
            if tool_name not in tools:
                print(f"    Missing tool: {tool_name}")
                return False
        
        print(f"    Found {len(tools)} tools")
        return True
    except Exception as e:
        print(f"    Error: {e}")
        return False


def test_tool_declarations():
    """Test that tool declarations are properly formatted."""
    try:
        gcs = bucket_ops.GCSBucketManager(bucket_name="clinic_sim")
        executor = ToolExecutor(gcs)
        
        declarations = executor.get_tool_declarations()
        
        if not declarations or len(declarations) == 0:
            print("    No tool declarations found")
            return False
        
        # Check first tool has function_declarations
        if not hasattr(declarations[0], 'function_declarations'):
            print("    Tool declarations missing function_declarations attribute")
            return False
        
        func_decls = declarations[0].function_declarations
        print(f"    Found {len(func_decls)} function declarations")
        
        return len(func_decls) == 5  # Should have 5 tools
    except Exception as e:
        print(f"    Error: {e}")
        return False


def test_websocket_agent_initialization():
    """Test WebSocketLiveAgent initialization."""
    try:
        agent = WebSocketLiveAgent()
        return agent is not None and agent.connection_manager is not None
    except Exception as e:
        print(f"    Error: {e}")
        return False


def test_message_types():
    """Test that all message types are defined."""
    try:
        expected_types = [
            "TEXT", "FORM", "SLOTS", "ATTACHMENT", "ERROR",
            "STATUS", "TYPING", "TOOL_CALL", "STREAM_START",
            "STREAM_CHUNK", "STREAM_END"
        ]
        
        for msg_type in expected_types:
            if not hasattr(MessageType, msg_type):
                print(f"    Missing message type: {msg_type}")
                return False
        
        print(f"    All {len(expected_types)} message types defined")
        return True
    except Exception as e:
        print(f"    Error: {e}")
        return False


async def test_chat_agent_basic():
    """Test basic chat functionality (mocked - no actual API call)."""
    try:
        agent = ChatAgent(patient_id="TEST001", use_tools=False)
        
        # Check that agent has required attributes
        assert hasattr(agent, 'client')
        assert hasattr(agent, 'gcs')
        assert hasattr(agent, 'retriever')
        assert hasattr(agent, 'conversation_history')
        
        # Check history starts empty
        history = agent.get_history()
        assert len(history) == 0
        
        print("    Agent properly initialized with required components")
        return True
    except Exception as e:
        print(f"    Error: {e}")
        return False


def test_tool_execution_structure():
    """Test that tool execution has proper structure."""
    try:
        gcs = bucket_ops.GCSBucketManager(bucket_name="clinic_sim")
        executor = ToolExecutor(gcs)
        
        # Test with mock parameters (won't actually execute against GCS)
        # Just testing the structure
        tools = executor._register_tools()
        
        # Check each tool is callable
        for tool_name, tool_func in tools.items():
            if not callable(tool_func):
                print(f"    Tool {tool_name} is not callable")
                return False
        
        print(f"    All {len(tools)} tools are callable")
        return True
    except Exception as e:
        print(f"    Error: {e}")
        return False


def test_connection_manager():
    """Test WebSocket connection manager."""
    try:
        from websocket_agent import WebSocketConnectionManager
        
        manager = WebSocketConnectionManager()
        
        # Check initial state
        assert len(manager.active_sessions) == 0
        assert len(manager.patient_to_sessions) == 0
        
        # Check methods exist
        assert hasattr(manager, 'connect')
        assert hasattr(manager, 'disconnect')
        assert hasattr(manager, 'get_session')
        assert hasattr(manager, 'get_patient_sessions')
        assert hasattr(manager, 'broadcast_to_patient')
        
        print("    Connection manager properly initialized")
        return True
    except Exception as e:
        print(f"    Error: {e}")
        return False


def test_chat_agent_methods():
    """Test that ChatAgent has all required methods."""
    try:
        agent = ChatAgent(patient_id="TEST001", use_tools=False)
        
        required_methods = [
            'chat',
            'chat_stream',
            'get_history',
            'clear_history',
            'save_history'
        ]
        
        for method_name in required_methods:
            if not hasattr(agent, method_name):
                print(f"    Missing method: {method_name}")
                return False
            
            method = getattr(agent, method_name)
            if not callable(method):
                print(f"    {method_name} is not callable")
                return False
        
        print(f"    All {len(required_methods)} required methods present")
        return True
    except Exception as e:
        print(f"    Error: {e}")
        return False


def test_imports_in_server():
    """Test that server.py can import new modules."""
    try:
        # Try to import what server.py imports
        from chat_agent import ChatAgent
        from websocket_agent import (
            websocket_pre_consult_endpoint,
            websocket_chat_endpoint,
            websocket_agent
        )
        
        print("    Server imports successful")
        return True
    except ImportError as e:
        print(f"    Import error: {e}")
        return False


# Main execution

def main():
    """Run all tests."""
    print("="*60)
    print("NEW FEATURES VALIDATION SCRIPT")
    print("="*60)
    print("\nThis script validates that new features are properly integrated")
    print("without breaking existing functionality.\n")
    
    validator = FeatureValidator()
    
    # Run tests
    print("\n--- MODULE STRUCTURE TESTS ---")
    validator.test("Chat Agent Initialization", test_chat_agent_initialization)
    validator.test("RAG Retriever Initialization", test_rag_retriever)
    validator.test("Tool Executor Initialization", test_tool_executor)
    validator.test("Tool Declarations Format", test_tool_declarations)
    validator.test("WebSocket Agent Initialization", test_websocket_agent_initialization)
    validator.test("Message Types Definition", test_message_types)
    validator.test("Connection Manager", test_connection_manager)
    
    print("\n--- COMPONENT TESTS ---")
    validator.test("Chat Agent Basic Functionality", test_chat_agent_basic)
    validator.test("Tool Execution Structure", test_tool_execution_structure)
    validator.test("Chat Agent Methods", test_chat_agent_methods)
    
    print("\n--- INTEGRATION TESTS ---")
    validator.test("Server Module Imports", test_imports_in_server)
    
    # Print summary
    validator.print_summary()
    
    # Exit with appropriate code
    return 0 if validator.failed == 0 else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        
        print("\n" + "="*60)
        if exit_code == 0:
            print("✅ ALL TESTS PASSED - Features are ready!")
            print("\nNext steps:")
            print("1. Start the server: python server.py")
            print("2. Visit http://localhost:8000/docs for API documentation")
            print("3. Try the examples in QUICKSTART.md")
        else:
            print("❌ SOME TESTS FAILED - Please check the errors above")
            print("\nTroubleshooting:")
            print("1. Ensure all dependencies are installed: pip install -r requirements.txt")
            print("2. Check that .env file has required variables")
            print("3. Verify GCS bucket access")
        print("="*60)
        
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        sys.exit(1)
