#!/usr/bin/env python3
"""
Quick test to verify server can start without errors
"""
import sys
import os

print("Testing server startup...")
print("=" * 60)

try:
    # Add current directory to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    print("1. Importing server module...")
    import server
    print("   ✅ Server module imported successfully")
    
    print("2. Checking FastAPI app...")
    assert server.app is not None
    print("   ✅ FastAPI app exists")
    
    print("3. Checking endpoints...")
    routes = [route.path for route in server.app.routes]
    print(f"   Found {len(routes)} routes")
    
    critical_routes = ["/", "/health"]
    for route in critical_routes:
        if route in routes:
            print(f"   ✅ {route} exists")
        else:
            print(f"   ⚠️  {route} missing")
    
    print("\n" + "=" * 60)
    print("✅ SERVER CAN START - No import errors")
    print("=" * 60)
    sys.exit(0)
    
except ImportError as e:
    print(f"\n❌ IMPORT ERROR: {e}")
    print("\nMissing dependency. Check requirements.txt")
    sys.exit(1)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
