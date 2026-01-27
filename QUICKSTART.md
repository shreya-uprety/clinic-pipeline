# Quick Start Guide - New Features

## 🚀 Getting Started in 5 Minutes

### What's New?

Two new capabilities added to the clinic simulation pipeline:

1. **General Chat Agent** - Ask questions about patient data with AI
2. **WebSocket Support** - Real-time streaming communication

---

## Installation

**No new dependencies needed!** Everything uses existing packages.

```bash
# Just start the server as usual
python server.py
```

---

## Usage Examples

### 1. REST API - General Chat

**Ask a question about patient data:**

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "P0001",
    "message": "What are the patient'\''s current medications?",
    "use_tools": true
  }'
```

**Response:**
```json
{
  "patient_id": "P0001",
  "response": "The patient is currently taking:\n- Furosemide 80mg daily\n- Spironolactone 100mg daily\n- Lactulose 15ml twice daily",
  "status": "success"
}
```

### 2. WebSocket - Real-Time Chat

**Python Client:**

```python
import asyncio
import websockets
import json

async def chat():
    uri = "ws://localhost:8000/ws/chat/P0001"
    
    async with websockets.connect(uri) as ws:
        # Send message
        await ws.send(json.dumps({
            "message": "Summarize the patient's condition",
            "stream": True
        }))
        
        # Receive streaming response
        while True:
            msg = json.loads(await ws.recv())
            
            if msg["type"] == "stream_chunk":
                print(msg["content"], end="", flush=True)
            elif msg["type"] == "stream_end":
                break

asyncio.run(chat())
```

**JavaScript Client:**

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat/P0001');

ws.onopen = () => {
    ws.send(JSON.stringify({
        message: "What are the latest lab results?",
        stream: true
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'stream_chunk') {
        console.log(data.content);
    }
};
```

### 3. WebSocket - Pre-Consultation (Linda)

**Connect to existing Linda agent via WebSocket:**

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/pre-consult/P0001');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case 'form':
            // Linda wants a form filled
            showForm(data.data.form_request);
            break;
        case 'slots':
            // Linda offers appointment slots
            showSlots(data.data.available_slots);
            break;
        case 'text':
            // Regular message
            displayMessage(data.content);
            break;
    }
};

// Send message
ws.send(JSON.stringify({
    message: "I need to book an appointment",
    attachments: [],
    form_data: {}
}));
```

---

## New API Endpoints

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | General chat with RAG + tools |
| GET | `/api/chat/{patient_id}/history` | Get chat history |
| POST | `/api/chat/{patient_id}/clear` | Clear chat history |

### WebSocket Endpoints

| Endpoint | Description |
|----------|-------------|
| `ws://host/ws/chat/{patient_id}` | General chat with streaming |
| `ws://host/ws/pre-consult/{patient_id}` | Pre-consultation (Linda) |

### Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/ws/sessions` | View active WebSocket connections |

---

## Available Tools

The chat agent can automatically use these tools:

| Tool | Description | Example Query |
|------|-------------|---------------|
| `get_patient_labs` | Retrieve lab results | "What's the ALT level?" |
| `get_patient_medications` | Get medication list | "What drugs is the patient on?" |
| `get_patient_encounters` | Get visit history | "Show me past encounters" |
| `search_patient_data` | Search all records | "Find mentions of jaundice" |
| `calculate_drug_interaction` | Check drug interactions | "Check Furosemide + Spironolactone" |

**Tools are used automatically** - just ask natural language questions!

---

## Python SDK Examples

### Example 1: Simple Q&A

```python
from chat_agent import ChatAgent
import asyncio

async def main():
    agent = ChatAgent(patient_id="P0001", use_tools=True)
    
    response = await agent.chat("What's the latest bilirubin value?")
    print(response)

asyncio.run(main())
```

### Example 2: Streaming Response

```python
async def streaming_example():
    agent = ChatAgent(patient_id="P0001", use_tools=True)
    
    print("Response: ", end="")
    async for chunk in agent.chat_stream("Explain the diagnosis"):
        print(chunk, end="", flush=True)
    print()

asyncio.run(streaming_example())
```

### Example 3: Conversation History

```python
async def history_example():
    agent = ChatAgent(patient_id="P0001", use_tools=True)
    
    await agent.chat("What medications is the patient taking?")
    await agent.chat("Are any of them hepatotoxic?")
    
    # Get conversation
    history = agent.get_history()
    print(f"Total messages: {len(history)}")
    
    # Save to GCS
    agent.save_history()
    
    # Clear if needed
    agent.clear_history()

asyncio.run(history_example())
```

---

## Testing

### Test REST Endpoint

```bash
# Using curl
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"P0001","message":"Test query"}'

# Using httpie
http POST localhost:8000/api/chat \
  patient_id=P0001 \
  message="What are the lab results?"
```

### Test WebSocket

```bash
# Using websocat (install: brew install websocat)
websocat ws://localhost:8000/ws/chat/P0001

# Then type:
{"message": "Hello"}
```

### View Active Sessions

```bash
curl http://localhost:8000/ws/sessions
```

---

## Message Formats

### REST Request

```json
{
  "patient_id": "P0001",
  "message": "Your question here",
  "use_tools": true
}
```

### WebSocket Client→Server

```json
{
  "message": "Your question here",
  "stream": true
}
```

### WebSocket Server→Client (Streaming)

```json
{"type": "stream_start", "timestamp": "2026-01-27T10:00:00"}
{"type": "stream_chunk", "content": "The patient"}
{"type": "stream_chunk", "content": " is..."}
{"type": "stream_end", "timestamp": "2026-01-27T10:00:05"}
```

### WebSocket Server→Client (Regular)

```json
{
  "type": "text",
  "content": "Complete response here",
  "timestamp": "2026-01-27T10:00:00"
}
```

---

## Troubleshooting

### Issue: "Module not found: chat_agent"

**Solution:** Make sure you're running from the project root:
```bash
cd d:/clinic-sim-pipeline
python server.py
```

### Issue: WebSocket connection fails

**Check:**
1. Server is running: `curl http://localhost:8000/`
2. No firewall blocking WebSocket connections
3. Using correct URL: `ws://` not `wss://` for local dev

### Issue: "Patient data not found"

**Solution:** Ensure patient data exists in GCS:
```python
from bucket_ops import GCSBucketManager
gcs = GCSBucketManager(bucket_name="clinic_sim")
files = gcs.list_files("patient_data/P0001")
print(files)
```

### Issue: Slow responses

**Check:**
1. GCS bucket access is working
2. Vertex AI quotas not exceeded
3. Network connectivity to GCP

---

## Configuration

### Environment Variables

```bash
# .env file
PROJECT_ID=your-gcp-project-id
PROJECT_LOCATION=us-central1
```

### Model Configuration

Edit in `chat_agent.py`:

```python
MODEL = "gemini-2.5-flash-lite"  # Fast, cost-effective
MODEL_ADVANCED = "gemini-3-flash-preview"  # More capable
```

---

## Integration with Existing Code

### Original Endpoints Still Work

✅ All existing endpoints remain functional:
- `POST /chat` - Original Linda pre-consultation chat
- `GET /chat/{patient_id}` - Original chat history
- All schedule management endpoints
- All patient management endpoints

### Using Both Chat Agents

```python
# Original pre-consultation agent (Linda)
response = requests.post('http://localhost:8000/chat', json={
    "patient_id": "P0001",
    "patient_message": "I need an appointment",
    "patient_attachments": [],
    "patient_form": {}
})

# New general chat agent
response = requests.post('http://localhost:8000/api/chat', json={
    "patient_id": "P0001",
    "message": "What are the lab results?",
    "use_tools": True
})
```

---

## Advanced Features

### Custom System Instructions

```python
agent = ChatAgent(patient_id="P0001", use_tools=True)

custom_instruction = """
You are a hepatology specialist focused on liver disease.
Always consider drug-induced liver injury in your analysis.
"""

response = await agent.chat(
    "Analyze the patient's condition",
    system_instruction=custom_instruction
)
```

### Disable Tools

```python
# For simple Q&A without tool execution
agent = ChatAgent(patient_id="P0001", use_tools=False)
```

### Broadcasting to Multiple Clients

```python
from websocket_agent import websocket_agent

# Send notification to all connected clients for a patient
await websocket_agent.broadcast_to_patient(
    patient_id="P0001",
    message="New lab results available",
    msg_type="notification"
)
```

---

## Performance Tips

1. **Reuse Agent Instances:** Don't create a new `ChatAgent` for every message
2. **Enable Streaming:** For better UX, use streaming WebSocket responses
3. **Use Tools Selectively:** Set `use_tools=False` if not needed
4. **Cache Patient Context:** The agent caches context after first load

---

## Next Steps

1. **Read Full Documentation:** See `INTEGRATION_DOCUMENTATION.md`
2. **Explore Tool Capabilities:** Try different natural language queries
3. **Build Frontend:** Use WebSocket examples to create real-time UI
4. **Add Custom Tools:** Extend `ToolExecutor` class with domain-specific tools

---

## Support

- **Documentation:** `INTEGRATION_DOCUMENTATION.md`
- **Source Code:** `chat_agent.py`, `websocket_agent.py`
- **Original Server:** `server.py`
- **Existing Agents:** `my_agents.py`

**Everything is documented inline with comprehensive docstrings!**
