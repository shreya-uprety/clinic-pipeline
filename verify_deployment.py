#!/usr/bin/env python3
"""
Verify that critical files have the correct lazy initialization pattern
"""
import sys

print("Verifying deployment-ready code...")
print("=" * 60)

# Check websocket_agent.py
print("1. Checking websocket_agent.py...")
with open("websocket_agent.py", "r", encoding="utf-8") as f:
    content = f.read()
    
    # Check for lazy initialization
    if 'websocket_agent = None' in content:
        print("   ✅ Has lazy initialization (websocket_agent = None)")
    else:
        print("   ❌ Missing lazy initialization!")
        sys.exit(1)
    
    # Check for getter function
    if 'def get_websocket_agent()' in content:
        print("   ✅ Has get_websocket_agent() function")
    else:
        print("   ❌ Missing getter function!")
        sys.exit(1)
    
    # Check it's NOT instantiating at module level
    if 'websocket_agent = WebSocketLiveAgent()' in content:
        # Check if it's inside a function (OK) or at module level (BAD)
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'websocket_agent = WebSocketLiveAgent()' in line:
                # Check indentation - if indented, it's inside a function (OK)
                if line.startswith(' ') or line.startswith('\t'):
                    print(f"   ✅ Instantiation at line {i+1} is inside function (OK)")
                else:
                    print(f"   ❌ ERROR: Module-level instantiation at line {i+1}!")
                    print(f"      Line: {line.strip()}")
                    sys.exit(1)
    
    if 'Version: 2.0' in content:
        print("   ✅ Version 2.0 marker present")
    else:
        print("   ⚠️  Version marker not found (may be old file)")

# Check server.py
print("\n2. Checking server.py...")
with open("server.py", "r", encoding="utf-8") as f:
    content = f.read()
    
    if 'get_websocket_agent' in content:
        print("   ✅ Imports get_websocket_agent function")
    else:
        print("   ❌ Not importing get_websocket_agent!")
        sys.exit(1)
    
    if '@app.get("/health")' in content:
        print("   ✅ Has /health endpoint")
    else:
        print("   ⚠️  Missing /health endpoint")

print("\n" + "=" * 60)
print("✅ ALL CHECKS PASSED - Ready for deployment!")
print("=" * 60)
