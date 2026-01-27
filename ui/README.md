# Chat Agent Test UI

A simple HTML + JavaScript interface to test the FastAPI chat endpoints (REST and WebSocket).

## Features

- ✅ **REST API Testing**: Send messages via HTTP POST to `/api/chat`
- ✅ **WebSocket Testing**: Real-time streaming communication via `/ws/chat/{patient_id}`
- ✅ **Message History**: Display conversation with timestamps
- ✅ **Typing Indicators**: Visual feedback when agent is processing
- ✅ **Streaming Support**: See responses stream in real-time (WebSocket)
- ✅ **Status Monitoring**: Connection status display
- ✅ **Patient ID Selection**: Test different patients easily

## Quick Start

### Step 1: Start the FastAPI Server

Navigate to the project root and start the server:

```bash
cd d:\clinic-sim-pipeline
python server.py
```

The server should start at `http://localhost:8000` (or check the console output for the actual URL).

### Step 2: Open the UI

**Option A - Direct File (Simplest):**
1. Navigate to `d:\clinic-sim-pipeline\ui\`
2. Double-click `index.html` to open in your browser
3. The file will open as `file:///d:/clinic-sim-pipeline/ui/index.html`

**Option B - Local HTTP Server (Recommended):**
```bash
cd d:\clinic-sim-pipeline\ui
python -m http.server 8080
```
Then open: http://localhost:8080

### Step 3: Test the Endpoints

#### Testing REST API

1. Enter a patient ID (e.g., `P0001`)
2. Type a message in the input box
3. Click **"Send REST"** button
4. Wait for the response to appear

Example messages to try:
- "What are the patient's recent lab results?"
- "Show me the medication history"
- "Summarize the latest encounter"

#### Testing WebSocket

1. Enter a patient ID (e.g., `P0001`)
2. Click **"Connect WebSocket"** button
3. Wait for "Connected" status
4. Type a message and click **"Send WS"** button
5. Watch the response stream in real-time!

Example messages:
- "Tell me about this patient's medical history"
- "What medications is the patient currently taking?"
- "Are there any risk events I should be aware of?"

## UI Overview

### Controls Section
- **Patient ID**: Specify which patient's data to query (default: P0001)
- **Server URL**: FastAPI server address (default: http://localhost:8000)
- **Connect WebSocket**: Establish WebSocket connection
- **Disconnect**: Close WebSocket connection
- **Clear**: Clear message history

### Message Area
- Displays conversation history with timestamps
- User messages appear with blue background
- Assistant responses appear with white background
- System messages appear with gray background
- Typing indicator shows when agent is processing

### Input Area
- **Message box**: Type your message (Shift+Enter for new line)
- **Send REST**: Send via REST API (HTTP POST)
- **Send WS**: Send via WebSocket (real-time streaming)

## Keyboard Shortcuts

- **Enter**: Send message (uses WebSocket if connected, otherwise REST)
- **Shift + Enter**: New line in message box

## Troubleshooting

### "Failed to send message" Error

**Problem**: REST API call fails

**Solutions**:
1. Check if server is running at http://localhost:8000
2. Verify the server URL in the UI matches your server
3. Check browser console (F12) for detailed error messages
4. Verify the patient ID exists in your system

### "WebSocket connection error"

**Problem**: Cannot establish WebSocket connection

**Solutions**:
1. Ensure server is running and WebSocket endpoints are enabled
2. Check if the server URL is correct (should auto-convert http → ws)
3. Try restarting the server
4. Check server logs for WebSocket errors

### No Response Received

**Problem**: Message sent but no response

**Solutions**:
1. Check server logs for errors
2. Verify patient ID exists
3. Ensure Google Cloud credentials are configured (.env file)
4. Check if the agent has access to patient data in GCS bucket

### CORS Errors (If using file://)

**Problem**: Browser blocks requests from `file://` protocol

**Solution**: Use local HTTP server instead:
```bash
cd ui
python -m http.server 8080
# Then open http://localhost:8080
```

## Testing Checklist

Use this checklist to verify functionality:

- [ ] Server starts without errors
- [ ] UI opens in browser
- [ ] Can change patient ID
- [ ] REST API: Can send message
- [ ] REST API: Receives response
- [ ] REST API: Typing indicator appears
- [ ] WebSocket: Can connect
- [ ] WebSocket: Status shows "Connected"
- [ ] WebSocket: Can send message
- [ ] WebSocket: Response streams in real-time
- [ ] WebSocket: Can disconnect
- [ ] Messages display with timestamps
- [ ] Can clear message history
- [ ] Keyboard shortcuts work (Enter to send)

## API Endpoints Being Tested

### REST API Endpoint
```
POST http://localhost:8000/api/chat
Content-Type: application/json

{
  "patient_id": "P0001",
  "message": "What are the patient's lab results?",
  "use_tools": true
}
```

### WebSocket Endpoint
```
ws://localhost:8000/ws/chat/P0001

Send message:
{
  "message": "Tell me about this patient",
  "stream": true
}
```

## Advanced Usage

### Testing Different Features

**RAG Retrieval** (REST or WebSocket):
```
"Show me all information about patient P0001"
"What is the patient's medical history?"
```

**Tool Execution** (REST or WebSocket):
```
"Get the patient's latest lab results"
"What medications is the patient taking?"
"Search for diabetes-related information"
```

**Streaming** (WebSocket only):
```
Connect WebSocket first, then send any message to see streaming
```

### Monitoring Server Logs

While testing, keep an eye on the server terminal to see:
- Incoming requests
- RAG retrieval operations
- Tool executions
- Error messages
- WebSocket connections/disconnections

## Technical Details

### Technologies Used
- **HTML5**: Structure
- **CSS3**: Styling with gradients and animations
- **Vanilla JavaScript**: No frameworks/libraries required
- **Fetch API**: REST API calls
- **WebSocket API**: Real-time communication

### Message Types (WebSocket)
The UI handles these WebSocket message types:
- `status`: Connection status updates
- `typing`: Typing indicator control
- `stream_start`: Begin streaming response
- `stream_chunk`: Partial response content
- `stream_end`: Streaming complete
- `text`: Complete text message
- `error`: Error messages

### Browser Compatibility
- Chrome/Edge: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support
- Internet Explorer: ❌ Not supported

## Next Steps

After verifying the UI works:

1. **Integrate with Production**: Update server URL for production environment
2. **Add Authentication**: Implement user authentication if required
3. **Enhance UI**: Add more features like file upload, voice input, etc.
4. **Monitor Performance**: Track response times and errors
5. **User Testing**: Get feedback from actual users

## Support

If you encounter issues:

1. Check the [TESTING_GUIDE.md](../TESTING_GUIDE.md) in the project root
2. Review server logs for detailed error messages
3. Open browser DevTools (F12) → Console for JavaScript errors
4. Verify your `.env` file has correct GCP credentials

## File Structure

```
ui/
├── index.html          # Main UI file (this is all you need!)
└── README.md          # This documentation
```

That's it! The entire UI is self-contained in `index.html` with inline CSS and JavaScript for simplicity.
