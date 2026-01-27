# Deployment and Testing Guide

## Quick Validation (No Server Required)

### ✅ Step 1: Verify Files Exist

Check that all new files were created:

```bash
# Windows PowerShell
Test-Path chat_agent.py
Test-Path websocket_agent.py
Test-Path INTEGRATION_DOCUMENTATION.md
Test-Path QUICKSTART.md
Test-Path README_NEW_FEATURES.md
Test-Path test_new_features.py
Test-Path CHECKLIST.md

# Expected output: True for each file
```

### ✅ Step 2: Verify File Content

Check that files are not empty:

```bash
# Windows PowerShell
(Get-Content chat_agent.py).Length          # Should be ~765 lines
(Get-Content websocket_agent.py).Length     # Should be ~618 lines
(Get-Content server.py | Select-String "from chat_agent").Length  # Should be > 0
```

### ✅ Step 3: Check Python Syntax

Verify Python files have no syntax errors:

```bash
python -m py_compile chat_agent.py
python -m py_compile websocket_agent.py
python -m py_compile test_new_features.py
# Should complete with no output if successful
```

---

## Full Testing (Requires Server)

### Prerequisites

1. **Install Dependencies** (if not already installed):
```bash
pip install -r requirements.txt
```

2. **Set Environment Variables**:
```bash
# Create or edit .env file
PROJECT_ID=your-gcp-project-id
PROJECT_LOCATION=us-central1
```

3. **Verify GCS Access**:
```bash
# Test that bucket operations work
python -c "from bucket_ops import GCSBucketManager; gcs = GCSBucketManager('clinic_sim'); print('✅ GCS connected')"
```

---

### Test 1: Start Server

```bash
# Start the server
python server.py

# Expected output:
# INFO:     Started server process
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

**✅ Success if:** Server starts without errors

---

### Test 2: Health Check

```bash
# In a new terminal
curl http://localhost:8000/

# Expected output:
# {"status":"MedForce Server is Running"}
```

**✅ Success if:** Returns JSON with status

---

### Test 3: API Documentation

Open browser to: `http://localhost:8000/docs`

**✅ Success if:** 
- Swagger UI loads
- See new endpoints:
  - `POST /api/chat`
  - `GET /api/chat/{patient_id}/history`
  - `POST /api/chat/{patient_id}/clear`

---

### Test 4: General Chat Endpoint (REST)

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"P0001","message":"What is the patient ID?","use_tools":false}'

# Expected: JSON response with patient_id, response, status
```

**✅ Success if:** Returns response without error

---

### Test 5: WebSocket Connection (Python)

Create `test_ws.py`:

```python
import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:8000/ws/chat/P0001"
    
    try:
        async with websockets.connect(uri) as ws:
            # Wait for connection confirmation
            status = await ws.recv()
            print(f"✅ Connected: {status}")
            
            # Send message
            await ws.send(json.dumps({
                "message": "Hello",
                "stream": False
            }))
            
            # Receive response
            response = await ws.recv()
            print(f"✅ Received: {response[:100]}...")
            
            return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test())
    print(f"\nWebSocket test: {'PASSED ✅' if result else 'FAILED ❌'}")
```

Run: `python test_ws.py`

**✅ Success if:** Connection established and message received

---

### Test 6: Existing Endpoints Still Work

Test that original functionality wasn't broken:

```bash
# Test 1: Original health check
curl http://localhost:8000/
# ✅ Should return: {"status":"MedForce Server is Running"}

# Test 2: Get patients (if data exists)
curl http://localhost:8000/patients
# ✅ Should return patient list or empty array

# Test 3: Original chat endpoint (Linda)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"P0001","patient_message":"Hello"}'
# ✅ Should return nurse_response with action_type
```

---

### Test 7: WebSocket Sessions Monitoring

```bash
curl http://localhost:8000/ws/sessions

# Expected output:
# {
#   "active_sessions": 0,
#   "sessions": []
# }
```

**✅ Success if:** Returns session count (0 or more)

---

### Test 8: Chat History Endpoints

```bash
# Clear history
curl -X POST http://localhost:8000/api/chat/P0001/clear

# Get history (should be empty)
curl http://localhost:8000/api/chat/P0001/history

# Expected: {"patient_id":"P0001","history":[],"message_count":0}
```

**✅ Success if:** History operations work without error

---

## Troubleshooting

### Issue: "Module not found: chat_agent"

**Cause:** Python can't find the new modules  
**Solution:** 
```bash
# Make sure you're in the correct directory
cd d:\clinic-sim-pipeline
python server.py
```

### Issue: "cannot import name 'genai' from 'google'"

**Cause:** Missing google-genai package  
**Solution:**
```bash
pip install google-genai
```

### Issue: WebSocket connection refused

**Cause:** Server not running or firewall blocking  
**Solution:**
```bash
# Check server is running
curl http://localhost:8000/

# Try different port
# Edit server.py, change port to 8001
uvicorn server:app --port 8001
```

### Issue: "Patient data not found"

**Cause:** No patient data in GCS for test patient ID  
**Solution:**
```bash
# Use a different patient ID that exists
# Or test with use_tools=False to avoid data access
```

### Issue: GCS authentication error

**Cause:** Missing credentials  
**Solution:**
```bash
# Set environment variable
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Or use application default credentials
gcloud auth application-default login
```

---

## Validation Checklist

Use this checklist to verify integration:

### Code Structure
- [ ] `chat_agent.py` exists and has ~765 lines
- [ ] `websocket_agent.py` exists and has ~618 lines
- [ ] `server.py` has new imports at top
- [ ] No syntax errors in Python files

### Server Startup
- [ ] Server starts without import errors
- [ ] Server starts without syntax errors
- [ ] Server listens on port 8000

### API Endpoints
- [ ] `GET /` returns status
- [ ] `POST /api/chat` is accessible
- [ ] `GET /api/chat/{patient_id}/history` is accessible
- [ ] `GET /ws/sessions` is accessible
- [ ] Swagger UI shows new endpoints at `/docs`

### WebSocket
- [ ] Can connect to `ws://localhost:8000/ws/chat/P0001`
- [ ] Can connect to `ws://localhost:8000/ws/pre-consult/P0001`
- [ ] Receives connection confirmation
- [ ] Can send and receive messages

### Backward Compatibility
- [ ] Original `POST /chat` still works
- [ ] Original `GET /chat/{patient_id}` still works
- [ ] Original `POST /chat/{patient_id}/reset` still works
- [ ] Other endpoints still functional

### Documentation
- [ ] `INTEGRATION_DOCUMENTATION.md` is comprehensive
- [ ] `QUICKSTART.md` has working examples
- [ ] `README_NEW_FEATURES.md` summarizes changes
- [ ] Code has inline documentation

---

## Success Criteria

**Minimum Success:** 
- ✅ Server starts without errors
- ✅ New endpoints are accessible
- ✅ No existing functionality broken

**Full Success:**
- ✅ All REST endpoints work
- ✅ WebSocket connections work
- ✅ Streaming responses work
- ✅ Tool execution works
- ✅ Conversation history works
- ✅ Session monitoring works
- ✅ All original endpoints work

---

## Post-Integration Steps

1. **Review Code**
   - Read through `chat_agent.py` 
   - Read through `websocket_agent.py`
   - Understand integration points

2. **Test with Real Data**
   - Use actual patient IDs
   - Test RAG context retrieval
   - Test tool automatic invocation
   - Test streaming responses

3. **Performance Testing**
   - Test with multiple concurrent users
   - Measure response times
   - Check memory usage
   - Monitor WebSocket connections

4. **Security Hardening**
   - Add authentication
   - Add rate limiting
   - Sanitize inputs
   - Add audit logging

5. **Deploy to Production**
   - Configure environment
   - Set up monitoring
   - Configure alerts
   - Test in staging first

---

## Quick Command Summary

```bash
# Verify files exist
ls chat_agent.py websocket_agent.py

# Check syntax
python -m py_compile chat_agent.py
python -m py_compile websocket_agent.py

# Start server
python server.py

# Test health (in new terminal)
curl http://localhost:8000/

# Test new endpoint
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"P0001","message":"test"}'

# Check WebSocket sessions
curl http://localhost:8000/ws/sessions

# View API docs
# Open: http://localhost:8000/docs
```

---

**Status: Ready for Testing ✅**

Follow this guide step-by-step to validate the integration.
