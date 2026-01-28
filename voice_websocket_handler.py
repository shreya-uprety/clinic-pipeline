"""
Voice WebSocket Handler for Gemini Live API Integration
Handles real-time bidirectional voice communication
"""

import asyncio
import os
import traceback
import logging
from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types
from chat_agent import ChatAgent

logger = logging.getLogger("voice-websocket")

# Gemini Live configuration
MODEL = "gemini-live-2.5-flash-preview-native-audio-09-2025"

class VoiceWebSocketHandler:
    """Handles real-time voice communication with Gemini Live API"""
    
    def __init__(self, websocket: WebSocket, patient_id: str):
        self.websocket = websocket
        self.patient_id = patient_id
        self.audio_in_queue = None
        self.out_queue = None
        self.session = None
        self.chat_agent = None
        
        # Initialize Gemini client with Vertex AI
        self.client = genai.Client(
            vertexai=True,
            project=os.getenv("PROJECT_ID", "medforce-pilot-backend"),
            location="us-central1"
        )
    
    def get_system_instruction(self):
        """Get system instruction for this patient"""
        return f"""You are an expert medical AI assistant specializing in hepatology and clinical care.
You're currently helping with patient {self.patient_id}.

Your capabilities:
1. Answer medical questions using patient context
2. Retrieve specific data using available tools
3. Provide evidence-based clinical reasoning
4. Maintain natural conversation flow

Guidelines:
- Speak naturally and conversationally (you're having a voice call)
- Be concise but thorough in your responses
- Use medical terminology appropriately but explain complex terms
- Reference specific patient data when available
- Ask clarifying questions when needed
"""
    
    def get_config(self):
        """Get Gemini Live API configuration"""
        # Get tool declarations
        tool_declarations = []
        if self.chat_agent and self.chat_agent.tool_executor:
            tools_list = self.chat_agent.tool_executor.get_tool_declarations()
            if tools_list:
                for tool in tools_list:
                    if hasattr(tool, 'function_declarations'):
                        tool_declarations.extend(tool.function_declarations)
        
        return {
            "response_modalities": ["AUDIO"],
            "system_instruction": self.get_system_instruction(),
            "tools": [{"function_declarations": tool_declarations}] if tool_declarations else [],
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": "Charon"
                    }
                },
                "language_code": "en-US"
            },
            "realtime_input_config": {
                "automatic_activity_detection": {
                    "disabled": False,
                    "start_of_speech_sensitivity": "START_SENSITIVITY_LOW",
                    "end_of_speech_sensitivity": "END_SENSITIVITY_LOW",
                    "prefix_padding_ms": 200,
                    "silence_duration_ms": 2000
                }
            }
        }
    
    async def handle_tool_call(self, tool_call):
        """Handle tool calls from Gemini"""
        try:
            logger.info("🔧 Tool call detected")
            function_responses = []
            
            for fc in tool_call.function_calls:
                function_name = fc.name
                arguments = dict(fc.args)
                
                logger.info(f"  📋 Executing: {function_name}")
                
                # Execute tool using ChatAgent's tool_executor
                # Note: execute_tool is synchronous, so run in thread
                result = await asyncio.to_thread(
                    self.chat_agent.tool_executor.execute_tool,
                    function_name,
                    arguments
                )
                
                function_responses.append(
                    types.FunctionResponse(
                        id=fc.id,
                        name=function_name,
                        response={"result": result}
                    )
                )
                
                logger.info(f"  ✅ Tool {function_name} completed")
            
            # Send responses back to Gemini
            await self.session.send_tool_response(function_responses=function_responses)
            
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            traceback.print_exc()
            # Send error response back to Gemini
            try:
                function_responses = [
                    types.FunctionResponse(
                        id=fc.id,
                        name=fc.name,
                        response={"error": str(e)}
                    )
                    for fc in tool_call.function_calls
                ]
                await self.session.send_tool_response(function_responses=function_responses)
            except:
                pass
    
    async def listen_audio(self):
        """Receive audio from WebSocket and send to Gemini"""
        logger.info("🎤 Listening to client audio...")
        try:
            while True:
                data = await self.websocket.receive_bytes()
                await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
        except WebSocketDisconnect:
            logger.info("Client disconnected")
            raise asyncio.CancelledError()
        except Exception as e:
            logger.error(f"Error receiving audio: {e}")
            raise asyncio.CancelledError()
    
    async def send_audio_to_gemini(self):
        """Send audio from queue to Gemini"""
        try:
            while True:
                audio_data = await self.out_queue.get()
                await self.session.send(input=audio_data)
        except Exception as e:
            logger.error(f"Error sending to Gemini: {e}")
    
    async def receive_audio(self):
        """Receive audio and handle tool calls from Gemini"""
        logger.info("🔊 Starting response processing...")
        try:
            while True:
                turn = self.session.receive()
                
                async for response in turn:
                    # Handle interruptions
                    if response.server_content and response.server_content.interrupted:
                        logger.info("🛑 Interrupted! Clearing queue...")
                        while not self.audio_in_queue.empty():
                            try:
                                self.audio_in_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                break
                        continue
                    
                    # Handle audio data
                    if data := response.data:
                        self.audio_in_queue.put_nowait(data)
                    
                    # Handle tool calls
                    if hasattr(response, 'tool_call') and response.tool_call:
                        await self.handle_tool_call(response.tool_call)
        except Exception as e:
            logger.error(f"Error receiving audio: {e}")
            traceback.print_exc()
    
    async def play_audio(self):
        """Send audio from queue to WebSocket"""
        logger.info("🔊 Streaming to client...")
        try:
            while True:
                bytestream = await self.audio_in_queue.get()
                await self.websocket.send_bytes(bytestream)
        except Exception as e:
            logger.error(f"Error sending audio: {e}")
    
    async def run(self):
        """Main run loop with concurrent tasks"""
        logger.info(f"🎵 Starting voice session for patient {self.patient_id}")
        
        try:
            # Initialize chat agent for tools
            self.chat_agent = ChatAgent(patient_id=self.patient_id, use_tools=True)
            
            # Get configuration
            config = self.get_config()
            
            # Connect to Gemini Live API
            async with (
                self.client.aio.live.connect(model=MODEL, config=config) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session
                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=10)
                
                logger.info("🔗 Connected to Gemini Live API")
                
                # Start concurrent tasks
                tg.create_task(self.send_audio_to_gemini())
                tg.create_task(self.listen_audio())
                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())
                
                # Keep alive until disconnect
                await asyncio.Future()
                
        except asyncio.CancelledError:
            logger.info("✅ Voice session ended")
        except Exception as e:
            logger.error(f"❌ Voice session error: {e}")
            traceback.print_exc()
        finally:
            logger.info("🧹 Cleanup completed")
