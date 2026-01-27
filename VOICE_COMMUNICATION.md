# Voice Communication Feature

Two-way voice communication has been added to the WebSocket chat agent.

## Features

✅ **Speech-to-Text (STT)**: Transcribe user voice to text using Google Cloud Speech-to-Text  
✅ **Text-to-Speech (TTS)**: Synthesize agent responses as audio using Google Cloud Text-to-Speech  
✅ **Real-time Processing**: Seamless voice conversation through WebSocket  
✅ **Automatic Transcription**: Voice messages are transcribed and processed automatically  
✅ **Voice Response**: Agent can respond with synthesized speech  

## Installation

Install the required Google Cloud packages:

```bash
pip install google-cloud-speech google-cloud-texttospeech
```

## Setup

### 1. Enable Google Cloud APIs

In your Google Cloud Console:
- Enable **Cloud Speech-to-Text API**
- Enable **Cloud Text-to-Speech API**

### 2. Authentication

Make sure your `.env` file has the correct credentials set up (already configured):

```env
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json
PROJECT_ID=medforce-pilot-backend
```

Or authenticate using:
```bash
gcloud auth application-default login
```

## Usage

### WebSocket Message Types

New message types for voice communication:

```javascript
// Client sends audio to server
{
  "type": "audio_chunk",
  "audio": "base64_encoded_audio_data",  // WAV format, 16kHz, mono
  "stream": true,
  "voice_response": true  // Optional: request voice response
}

// Server sends transcription
{
  "type": "transcription",
  "content": "What are the test results?",
  "timestamp": "2026-01-27T14:30:00"
}

// Server sends audio response
{
  "type": "audio_response",
  "audio": "base64_encoded_audio_data",  // MP3 format
  "format": "mp3",
  "timestamp": "2026-01-27T14:30:05"
}
```

### Text Message with Voice Response

You can also send text and request a voice response:

```javascript
{
  "message": "What medications is the patient taking?",
  "stream": true,
  "voice_response": true  // Request synthesized speech response
}
```

## Client-Side Example (JavaScript)

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/chat/P0001');

// Record audio from microphone
let mediaRecorder;
let audioChunks = [];

async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);
  
  mediaRecorder.ondataavailable = (event) => {
    audioChunks.push(event.data);
  };
  
  mediaRecorder.onstop = async () => {
    // Convert audio to base64
    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
    const reader = new FileReader();
    
    reader.onloadend = () => {
      const base64Audio = reader.result.split(',')[1];
      
      // Send to WebSocket
      ws.send(JSON.stringify({
        type: 'audio_chunk',
        audio: base64Audio,
        stream: true,
        voice_response: true
      }));
    };
    
    reader.readAsDataURL(audioBlob);
    audioChunks = [];
  };
  
  mediaRecorder.start();
}

function stopRecording() {
  mediaRecorder.stop();
}

// Handle incoming messages
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case 'transcription':
      console.log('You said:', data.content);
      break;
    
    case 'audio_response':
      // Play audio response
      const audioBlob = base64ToBlob(data.audio, 'audio/mp3');
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      audio.play();
      break;
    
    case 'stream_chunk':
      console.log('Agent:', data.content);
      break;
  }
};

function base64ToBlob(base64, mimeType) {
  const byteCharacters = atob(base64);
  const byteArrays = [];
  
  for (let i = 0; i < byteCharacters.length; i++) {
    byteArrays.push(byteCharacters.charCodeAt(i));
  }
  
  return new Blob([new Uint8Array(byteArrays)], { type: mimeType });
}
```

## Audio Format Requirements

### Input (STT)
- **Format**: WAV (LINEAR16)
- **Sample Rate**: 16kHz
- **Channels**: Mono (1 channel)
- **Encoding**: Base64 string

### Output (TTS)
- **Format**: MP3
- **Quality**: High quality neural voice
- **Voice**: en-US-Neural2-F (female, can be customized)
- **Encoding**: Base64 string

## Voice Configuration

You can customize the voice in `websocket_agent.py`:

```python
async def _synthesize_speech(
    self, 
    text: str, 
    language_code: str = "en-US",
    voice_name: str = "en-US-Neural2-F"  # Change this
) -> bytes:
```

### Available Voices

**English US:**
- `en-US-Neural2-A` - Male
- `en-US-Neural2-C` - Female
- `en-US-Neural2-D` - Male
- `en-US-Neural2-F` - Female (default)

**Other Languages:**
- `en-GB-Neural2-A` - British English
- `es-US-Neural2-A` - Spanish
- `fr-FR-Neural2-A` - French
- More at: https://cloud.google.com/text-to-speech/docs/voices

## Testing

### 1. Test Text-to-Speech

```python
import asyncio
import base64

# Initialize agent
agent = websocket_agent

# Synthesize speech
audio = await agent._synthesize_speech("Hello, how can I help you?")

# Save to file
with open("test_output.mp3", "wb") as f:
    f.write(audio)

print("Audio saved to test_output.mp3")
```

### 2. Test Speech-to-Text

```python
# Read audio file
with open("test_input.wav", "rb") as f:
    audio_bytes = f.read()

# Transcribe
text = await agent._transcribe_audio(audio_bytes)
print(f"Transcription: {text}")
```

## WebSocket Flow

```
Client                              Server
  |                                   |
  |--- Connect to /ws/chat/P0001 --->|
  |<--- {"type": "status"} -----------|
  |                                   |
  |--- {"type": "audio_chunk"} ----->|
  |                                   |--- Transcribe with STT
  |<--- {"type": "transcription"} ---|
  |                                   |
  |                                   |--- Process with ChatAgent
  |<--- {"type": "stream_chunk"} ----|
  |<--- {"type": "stream_chunk"} ----|
  |<--- {"type": "stream_end"} ------|
  |                                   |
  |                                   |--- Synthesize with TTS
  |<--- {"type": "audio_response"} --|
  |                                   |
```

## Error Handling

If voice features are not available (packages not installed), the system will:
- Log a warning on startup
- Set `VOICE_ENABLED = False`
- Return errors when voice features are attempted

To check if voice is enabled:
```python
if websocket_agent.VOICE_ENABLED:
    print("Voice features available")
else:
    print("Install: pip install google-cloud-speech google-cloud-texttospeech")
```

## Troubleshooting

### "Voice features not available"
- Install packages: `pip install google-cloud-speech google-cloud-texttospeech`
- Restart the server

### "Speech client initialization failed"
- Check Google Cloud authentication
- Verify PROJECT_ID in .env
- Run: `gcloud auth application-default login`

### "Transcription error"
- Ensure audio is in correct format (WAV, 16kHz, mono)
- Check audio quality (clear speech, minimal background noise)
- Verify audio data is properly base64 encoded

### "TTS error"
- Check if Text-to-Speech API is enabled in Google Cloud Console
- Verify voice name is valid
- Check quota limits in Google Cloud

## Performance Considerations

- **Latency**: STT + TTS adds ~2-3 seconds latency
- **Bandwidth**: Audio data increases payload size significantly
- **Costs**: Google Cloud STT/TTS has usage-based pricing
- **Optimization**: Consider caching common responses

## Next Steps

1. **Update UI**: Add voice recording button to [ui/index.html](ui/index.html)
2. **Add Voice Controls**: Mute, volume, voice selection
3. **Improve UX**: Visual feedback during recording/transcription
4. **Add Wake Word**: Voice activation ("Hey Assistant")
5. **Multi-language**: Support multiple languages dynamically

## API Pricing

Google Cloud pricing (as of 2026):
- **Speech-to-Text**: $0.006 per 15 seconds
- **Text-to-Speech**: $4 per 1M characters (Neural voices)

For production, consider implementing:
- Request rate limiting
- Audio compression
- Response caching
- Usage monitoring

## Security Notes

- Audio data transmitted in base64 (not encrypted by default)
- Use WSS (WebSocket Secure) in production
- Implement authentication before exposing voice features
- Consider HIPAA compliance for medical conversations
- Log and monitor voice interactions for quality assurance

---

Voice communication feature added on **January 27, 2026**
