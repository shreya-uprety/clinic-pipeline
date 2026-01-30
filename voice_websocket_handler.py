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
    
    async def get_system_instruction_with_context(self):
        """Get system instruction with patient context for this patient"""
        try:
            # Load the system prompt from file
            with open("system_prompts/system_prompt.md", "r", encoding="utf-8") as f:
                base_prompt = f.read()
            
            # Load patient context if chat_agent is available
            context_info = ""
            if self.chat_agent:
                # Ensure context is loaded
                if not self.chat_agent.context_data:
                    await self.chat_agent._load_patient_context()
                
                # Build context summary for system prompt
                if self.chat_agent.context_data and self.chat_agent.context_data.get("data"):
                    data = self.chat_agent.context_data["data"]
                    context_info = "\n\n--- LOADED PATIENT DATA ---\n"
                    
                    if data.get("patient_profile"):
                        context_info += f"Patient Profile: {str(data['patient_profile'])[:500]}\n"
                    
                    if data.get("basic_info"):
                        context_info += f"Basic Info: {str(data['basic_info'])[:300]}\n"
                    
                    if data.get("patient_context"):
                        context_info += f"Clinical Context: {str(data['patient_context'])[:300]}\n"
                    
                    context_info += "--- END LOADED DATA ---\n"
            
            # Add patient-specific context
            return f"""{base_prompt}

--- PATIENT-SPECIFIC CONTEXT ---
Current Patient ID: {self.patient_id}
Board URL: https://iso-clinic-v3.vercel.app/board/{self.patient_id}
{context_info}

CRITICAL INSTRUCTIONS:
- You are currently helping with patient ID: {self.patient_id}
- This patient ID never changes during this conversation
- When using tools, ALWAYS use patient_id: {self.patient_id}
- NEVER ask for patient ID - you already know it is {self.patient_id}
- All data queries should reference patient {self.patient_id}
- Patient information is loaded above - use it to answer questions
"""
        except Exception as e:
            logger.error(f"Failed to load system prompt: {e}")
            # Fallback to basic prompt
            return f"""You are MedForce Agent — a real-time conversational AI assistant.
Current Patient ID: {self.patient_id}
Board URL: https://iso-clinic-v3.vercel.app/board/{self.patient_id}
Assist the clinician with patient care. Communicate only in English. Be concise.
"""
    
    def get_system_instruction(self):
        """Get system instruction for this patient (sync wrapper)"""
        try:
            # Load the system prompt from file
            with open("system_prompts/system_prompt.md", "r", encoding="utf-8") as f:
                base_prompt = f.read()
            
            # Add patient-specific context
            return f"""{base_prompt}

--- PATIENT-SPECIFIC CONTEXT ---
Current Patient ID: {self.patient_id}
Board URL: https://iso-clinic-v3.vercel.app/board/{self.patient_id}

CRITICAL INSTRUCTIONS:
- You are currently helping with patient ID: {self.patient_id}
- This patient ID never changes during this conversation
- When using tools, ALWAYS use patient_id: {self.patient_id}
- NEVER ask for patient ID - you already know it is {self.patient_id}
- All data queries should reference patient {self.patient_id}
"""
        except Exception as e:
            logger.error(f"Failed to load system prompt: {e}")
            # Fallback to basic prompt
            return f"""You are MedForce Agent — a real-time conversational AI assistant.
Current Patient ID: {self.patient_id}
Board URL: https://iso-clinic-v3.vercel.app/board/{self.patient_id}
Assist the clinician with patient care. Communicate only in English. Be concise.
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
    
    async def stop_speaking(self):
        """Stop current Gemini response and clear audio queue"""
        logger.info("🛑 Stop button pressed")
        self.should_stop = True
        # Clear audio queue immediately
        cleared = 0
        while not self.audio_in_queue.empty():
            try:
                self.audio_in_queue.get_nowait()
                cleared += 1
            except asyncio.QueueEmpty:
                break
        logger.info(f"✅ Stopped speaking, cleared {cleared} chunks")
    
    async def listen_audio(self):
        """Receive audio from WebSocket and send to Gemini"""
        logger.info("🎤 Listening to client audio...")
        try:
            while True:
                message = await self.websocket.receive()
                
                # Check for stop command
                if "text" in message:
                    try:
                        data = json.loads(message["text"])
                        if data.get("type") == "stop":
                            await self.stop_speaking()
                            continue
                    except:
                        pass
                
                if "bytes" in message:
                    data = message["bytes"]
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
                    # Handle audio data - stream immediately for low latency
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
            
            # Load patient context
            logger.info(f"Loading patient context for voice session...")
            if not self.chat_agent.context_data:
                await self.chat_agent._load_patient_context()
            
            # Get configuration with context
            system_instruction = await self.get_system_instruction_with_context()
            config = self.get_config()
            config["system_instruction"] = system_instruction
            
            logger.info(f"✅ Voice session configured with patient context")
            
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
