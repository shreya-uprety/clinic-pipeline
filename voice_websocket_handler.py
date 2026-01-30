"""
Voice WebSocket Handler for Gemini Live API Integration
Handles real-time bidirectional voice communication
"""

import asyncio
import os
import traceback
import logging
import json
from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types
import side_agent
import canvas_ops

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
        self.context_data = None
        
        # Initialize Gemini client with Vertex AI
        self.client = genai.Client(
            vertexai=True,
            project=os.getenv("PROJECT_ID", "medforce-pilot-backend"),
            location="us-central1"
        )
    
    async def get_system_instruction_with_context(self):
        """Get system instruction - SHORT to avoid context window issues"""
        try:
            # Load the system prompt from file - use chat_model_system for brevity
            with open("system_prompts/chat_model_system.md", "r", encoding="utf-8") as f:
                base_prompt = f.read()
            
            # Load patient context using canvas_ops but DON'T put in system instruction
            # It's too large and causes context window errors
            if not self.context_data:
                self.context_data = canvas_ops.get_board_items()
            
            # Keep system instruction SHORT - patient data will be accessed via tools
            full_instruction = f"""{base_prompt}

--- PATIENT-SPECIFIC CONTEXT ---
Current Patient ID: {self.patient_id}
Board URL: https://iso-clinic-v3.vercel.app/board/{self.patient_id}

CRITICAL INSTRUCTIONS FOR VOICE MODE:
- Keep responses VERY SHORT - 1-2 sentences maximum
- Be conversational and natural for voice interaction
- You are currently helping with patient ID: {self.patient_id}
- This patient ID never changes during this conversation
- Use tools to get patient data, navigate canvas, create tasks, etc.
- When using tools, ALWAYS use patient_id: {self.patient_id}
"""
            
            logger.info(f"✅ Voice system instruction ready (context loaded separately)")
            return full_instruction
            
        except Exception as e:
            logger.error(f"Failed to load system prompt: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to basic prompt
            return f"""You are MedForce Agent — a real-time conversational AI assistant.
Keep responses VERY SHORT - 1-2 sentences maximum for voice interaction.
Current Patient ID: {self.patient_id}
Board URL: https://iso-clinic-v3.vercel.app/board/{self.patient_id}
Assist the clinician with patient care. Use tools to access data and perform actions.
"""
    
    def get_system_instruction(self):
        """Get system instruction for this patient (sync wrapper) - SHORT version"""
        try:
            # Load the system prompt from file - use chat_model_system for brevity
            with open("system_prompts/chat_model_system.md", "r", encoding="utf-8") as f:
                base_prompt = f.read()
            
            # Add patient-specific context - KEEP SHORT
            return f"""{base_prompt}

--- PATIENT-SPECIFIC CONTEXT ---
Current Patient ID: {self.patient_id}
Board URL: https://iso-clinic-v3.vercel.app/board/{self.patient_id}

CRITICAL INSTRUCTIONS FOR VOICE MODE:
- Keep responses VERY SHORT - 1-2 sentences maximum
- Be conversational and natural for voice interaction
- You are currently helping with patient ID: {self.patient_id}
- IMPORTANT: When asked about patient information (medications, labs, demographics, history, etc.), ALWAYS call get_patient_data tool FIRST to retrieve the data
- After getting patient data, answer the question using that data
- Use tools to navigate canvas, create tasks, etc.
- When using tools, ALWAYS use patient_id: {self.patient_id}
"""
        except Exception as e:
            logger.error(f"Failed to load system prompt: {e}")
            # Fallback to basic prompt
            return f"""You are MedForce Agent — a real-time conversational AI assistant.
Keep responses VERY SHORT - 1-2 sentences maximum for voice interaction.
Current Patient ID: {self.patient_id}
Use tools to access data and perform actions.
"""
    
    def get_config(self):
        """Get Gemini Live API configuration with tool declarations"""
        # Define tool declarations for voice mode actions
        tool_declarations = [
            {
                "name": "get_patient_data",
                "description": "Get ALL current patient's data including: demographics, medications, lab results, encounters, risk events, medical history, and clinical context. ALWAYS call this tool FIRST when user asks ANY question about the patient (e.g., 'what medications', 'lab results', 'patient name', 'medical history', etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "focus_board_item",
                "description": "Focus on a specific board item (e.g., medication timeline, lab results, encounter notes)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language description of what to focus on"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "create_task",
                "description": "Create a TODO task for the patient",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Description of the task to create"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "send_to_easl",
                "description": "Send a clinical question to EASL for analysis",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "Clinical question to analyze"
                        }
                    },
                    "required": ["question"]
                }
            }
        ]
        
        return {
            "response_modalities": ["AUDIO"],
            "system_instruction": self.get_system_instruction(),
            "tools": [{"function_declarations": tool_declarations}],
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
                    "end_of_speech_sensitivity": "END_SENSITIVITY_HIGH",
                    "prefix_padding_ms": 150,
                    "silence_duration_ms": 700
                }
            }
        }
    
    async def handle_tool_call(self, tool_call):
        """Handle tool calls from Gemini using side_agent and canvas_ops"""
        try:
            logger.info("🔧 Tool call detected")
            function_responses = []
            
            for fc in tool_call.function_calls:
                function_name = fc.name
                arguments = dict(fc.args)
                
                logger.info(f"  📋 Executing: {function_name}")
                
                result = ""
                try:
                    if function_name == "get_patient_data":
                        # Load full context if not already loaded
                        if not self.context_data:
                            self.context_data = canvas_ops.get_board_items()
                        
                        logger.info(f"📊 Context data type: {type(self.context_data)}, length: {len(self.context_data) if isinstance(self.context_data, (list, dict)) else 'N/A'}")
                        
                        # Search for "pulmonary" and related medical terms across all data
                        search_terms = ["pulmonary", "respiratory", "lung", "copd", "pneumonia", "dyspnea", "asthma", "bronchitis"]
                        full_data_str = json.dumps(self.context_data).lower()
                        found_terms = [term for term in search_terms if term in full_data_str]
                        
                        if found_terms:
                            logger.info(f"🔍 FOUND medical terms in board data: {found_terms}")
                        else:
                            logger.info(f"🔍 WARNING: None of these terms found in board: {search_terms}")
                        
                        pulmonary_locations = []
                        
                        # Extract ESSENTIAL data only - full dump exceeds 32k context window
                        # We need structured info that's useful but concise
                        summary = {"patient_id": self.patient_id}
                        
                        if isinstance(self.context_data, list):
                            logger.info(f"📋 Processing {len(self.context_data)} board items")
                            for idx, item in enumerate(self.context_data):
                                if not isinstance(item, dict):
                                    continue
                                
                                # Check if this item contains pulmonary or respiratory info
                                item_str = json.dumps(item).lower()
                                found_in_item = [term for term in search_terms if term in item_str]
                                if found_in_item:
                                    comp_type_for_log = item.get('componentType', 'unknown')
                                    logger.info(f"🔍 Item {idx} ({comp_type_for_log}) contains: {found_in_item}")
                                    pulmonary_locations.append(f"Item {idx}: {comp_type_for_log} - {found_in_item}")
                                
                                comp_type = item.get("componentType")
                                item_type = item.get("type")
                                
                                # Log ALL items to find patient profile
                                logger.info(f"  Item {idx}: componentType={comp_type}, type={item_type}, keys={list(item.keys())}")
                                
                                # Extract patient data from 'patient' field (SingleEncounterDocument)
                                if "patient" in item and isinstance(item["patient"], dict):
                                    patient = item["patient"]
                                    if "name" not in summary:
                                        logger.info(f"✅ Found patient field in item {idx}, patient keys: {list(patient.keys())}")
                                        if patient.get("name"):
                                            summary["name"] = patient.get("name")
                                            # Handle different field names
                                            summary["age"] = patient.get("age") or patient.get("age_at_first_encounter")
                                            summary["gender"] = patient.get("gender") or patient.get("sex")
                                            summary["mrn"] = patient.get("mrn") or patient.get("id")
                                            summary["date_of_birth"] = patient.get("date_of_birth") or patient.get("dateOfBirth")
                                            logger.info(f"   Patient: {summary.get('name')}, {summary.get('age')}yo, {summary.get('gender')}")
                                        if patient.get("medicalHistory"):
                                            history = patient.get("medicalHistory")
                                            logger.info(f"📋 Found medicalHistory in item {idx}, type: {type(history)}")
                                            summary["medical_history"] = str(history)[:2000]  # Increased to capture more
                                        if patient.get("medical_history"):
                                            history = patient.get("medical_history")
                                            logger.info(f"📋 Found medical_history in item {idx}, type: {type(history)}")
                                            summary["medical_history"] = str(history)[:2000]
                                
                                # Extract encounter data with clinical notes
                                if "encounter" in item and isinstance(item["encounter"], dict):
                                    encounter = item["encounter"]
                                    # Check for pulmonary in encounter
                                    encounter_str = json.dumps(encounter)
                                    if "pulmonary" in encounter_str.lower():
                                        logger.info(f"🔍 Found 'pulmonary' in encounter at item {idx}!")
                                    
                                    if "clinical_notes" not in summary:
                                        summary["clinical_notes"] = []
                                    if "rawText" in encounter:
                                        summary["clinical_notes"].append({
                                            "date": encounter.get("date"),
                                            "text": encounter.get("rawText")[:1500]  # Increased to 1500
                                        })
                                    if "assessment" in encounter:
                                        if "assessment" not in summary:
                                            summary["assessment"] = encounter["assessment"]
                                    # Extract history of present illness, review of systems, etc
                                    if "history_of_present_illness" in encounter:
                                        if "hpi" not in summary:
                                            summary["hpi"] = []
                                        summary["hpi"].append(encounter["history_of_present_illness"][:1000])
                                    if "review_of_systems" in encounter:
                                        if "review_of_systems" not in summary:
                                            summary["review_of_systems"] = []
                                        ros = encounter["review_of_systems"]
                                        if isinstance(ros, dict):
                                            summary["review_of_systems"].append(ros)
                                        else:
                                            summary["review_of_systems"].append(str(ros)[:1000])
                                
                                # Extract raw clinical note
                                if comp_type == "RawClinicalNote":
                                    # Check for pulmonary in raw text
                                    raw_text = item.get("rawText", "")
                                    if "pulmonary" in raw_text.lower():
                                        logger.info(f"🔍 Found 'pulmonary' in RawClinicalNote at item {idx}!")
                                    
                                    if "recent_clinical_notes" not in summary:
                                        summary["recent_clinical_notes"] = []
                                    note = {
                                        "date": item.get("date"),
                                        "visitType": item.get("visitType"),
                                        "provider": item.get("provider"),
                                        "text": raw_text[:1500] if raw_text else ""  # Increased to 1500 to capture more
                                    }
                                    summary["recent_clinical_notes"].append(note)
                                    logger.info(f"📋 Added clinical note from {item.get('date')}, text length: {len(raw_text)}")
                                
                                # Extract patient data from 'patientData' field (Sidebar, DifferentialDiagnosis)
                                if "patientData" in item and isinstance(item["patientData"], dict):
                                    patient_data = item["patientData"]
                                    logger.info(f"📋 patientData keys in item {idx}: {list(patient_data.keys())}")
                                    
                                    # Check if there's a nested 'patient' object inside patientData (Sidebar)
                                    if "patient" in patient_data and isinstance(patient_data["patient"], dict):
                                        nested_patient = patient_data["patient"]
                                        if "name" not in summary and nested_patient.get("name"):
                                            logger.info(f"✅ Found nested patient in patientData in item {idx}, keys: {list(nested_patient.keys())}")
                                            summary["name"] = nested_patient.get("name")
                                            summary["age"] = nested_patient.get("age") or nested_patient.get("age_at_first_encounter")
                                            summary["gender"] = nested_patient.get("gender") or nested_patient.get("sex")
                                            summary["mrn"] = nested_patient.get("mrn") or nested_patient.get("id")
                                            summary["date_of_birth"] = nested_patient.get("date_of_birth")
                                            summary["identifiers"] = nested_patient.get("identifiers")
                                            logger.info(f"   Patient: {summary.get('name')}, {summary.get('age')}yo, {summary.get('gender')}, DOB: {summary.get('date_of_birth')}")
                                    
                                    # Extract additional clinical data from Sidebar
                                    if "problem_list" in patient_data:
                                        problems = patient_data["problem_list"]
                                        logger.info(f"📋 Found problem_list in item {idx}: {problems}")
                                        if isinstance(problems, list):
                                            summary["problem_list"] = [str(p)[:300] for p in problems[:30]]  # Increased limits
                                        elif isinstance(problems, dict):
                                            summary["problem_list"] = problems
                                        else:
                                            summary["problem_list"] = str(problems)[:1000]
                                    if "allergies" in patient_data:
                                        logger.info(f"📋 Found allergies in item {idx}: {patient_data['allergies']}")
                                        summary["allergies"] = patient_data["allergies"]
                                    if "medication_timeline" in patient_data:
                                        # This might be large, so summarize
                                        med_timeline = patient_data["medication_timeline"]
                                        if isinstance(med_timeline, list):
                                            summary["medication_count"] = len(med_timeline)
                                        else:
                                            summary["medication_timeline_info"] = str(med_timeline)[:300]
                                    if "riskLevel" in patient_data:
                                        summary["risk_level"] = patient_data["riskLevel"]
                                    if "description" in patient_data:
                                        desc = patient_data["description"]
                                        logger.info(f"📋 Found clinical description in item {idx}, length: {len(str(desc))}")
                                        summary["clinical_summary"] = str(desc)[:2000]  # Increased to capture more info
                                    
                                    # Also check for direct fields in patientData
                                    if "name" not in summary and patient_data.get("name"):
                                        logger.info(f"✅ Found name in patientData in item {idx}")
                                        summary["name"] = patient_data.get("name")
                                        summary["age"] = patient_data.get("age") or patient_data.get("age_at_first_encounter")
                                        summary["gender"] = patient_data.get("gender") or patient_data.get("sex")
                                        summary["mrn"] = patient_data.get("mrn") or patient_data.get("id")
                                        summary["date_of_birth"] = patient_data.get("date_of_birth")
                                        logger.info(f"   Patient: {summary.get('name')}, {summary.get('age')}yo, {summary.get('gender')}")
                                
                                # Patient profile - check multiple possible field names
                                if "patientProfile" in item:
                                    profile = item["patientProfile"]
                                    logger.info(f"✅ Found patientProfile in item {idx}: {profile}")
                                    summary["name"] = profile.get("name")
                                    summary["age"] = profile.get("age")
                                    summary["gender"] = profile.get("gender")
                                    summary["mrn"] = profile.get("mrn")
                                
                                # Check for direct patient fields
                                if "name" in item and "age" in item and "name" not in summary:
                                    logger.info(f"✅ Found direct patient fields in item {idx}")
                                    summary["name"] = item.get("name")
                                    summary["age"] = item.get("age")
                                    summary["gender"] = item.get("gender")
                                    summary["mrn"] = item.get("mrn")
                                
                                # Patient context - check multiple field names
                                if "patientContext" in item:
                                    ctx = item["patientContext"]
                                    logger.info(f"✅ Found patientContext in item {idx}")
                                    summary["chief_complaint"] = ctx.get("chiefComplaint")
                                    summary["history"] = ctx.get("presentingHistory", ctx.get("history", ""))[:500]
                                
                                # Risk analysis
                                if "riskAnalysis" in item:
                                    risk = item["riskAnalysis"]
                                    logger.info(f"✅ Found riskAnalysis in item {idx}")
                                    summary["risk_score"] = risk.get("riskScore")
                                    summary["risk_factors"] = risk.get("riskFactors", [])[:5]
                                
                                # Encounters - check both structures
                                if "encounters" in item and isinstance(item["encounters"], list):
                                    if "recent_encounters" not in summary:
                                        summary["recent_encounters"] = []
                                    for enc in item["encounters"][:5]:
                                        if isinstance(enc, dict):
                                            enc_data = {
                                                "date": enc.get("date"),
                                                "visitType": enc.get("visitType"),
                                                "provider": enc.get("provider")
                                            }
                                            # Add assessment if available
                                            if "assessment" in enc:
                                                enc_data["assessment"] = enc["assessment"]
                                            summary["recent_encounters"].append(enc_data)
                                    logger.info(f"✅ Found {len(item['encounters'])} encounters in item {idx}")
                                
                                # Medications - check for medications array
                                if "medications" in item and isinstance(item["medications"], list):
                                    meds = []
                                    for med in item["medications"][:10]:
                                        if isinstance(med, dict):
                                            med_str = f"{med.get('name')} {med.get('dose')} {med.get('frequency')}"
                                            # Add indication if available
                                            if med.get("indication"):
                                                med_str += f" (for {med.get('indication')})"
                                            meds.append(med_str)
                                    if meds:
                                        logger.info(f"✅ Found {len(meds)} medications in item {idx}")
                                        summary["current_medications"] = meds
                                
                                # Labs - check for labs array
                                if "labs" in item and isinstance(item["labs"], list):
                                    labs = []
                                    for lab in item["labs"][:15]:
                                        if isinstance(lab, dict):
                                            lab_str = f"{lab.get('name')}: {lab.get('value')} {lab.get('unit')}"
                                            if lab.get("date"):
                                                lab_str += f" ({lab.get('date')})"
                                            # Add flag if abnormal
                                            if lab.get("flag") or lab.get("abnormal"):
                                                lab_str += " [ABNORMAL]"
                                            labs.append(lab_str)
                                    if labs:
                                        logger.info(f"✅ Found {len(labs)} labs in item {idx}")
                                        summary["recent_labs"] = labs
                                
                                # Risk events
                                if "risks" in item and isinstance(item["risks"], list):
                                    if "risk_events" not in summary:
                                        summary["risk_events"] = []
                                    for risk in item["risks"][:10]:
                                        if isinstance(risk, dict):
                                            summary["risk_events"].append({
                                                "date": risk.get("date"),
                                                "event": risk.get("event") or risk.get("description"),
                                                "severity": risk.get("severity") or risk.get("level")
                                            })
                                
                                # Key events
                                if "events" in item and isinstance(item["events"], list):
                                    if "key_events" not in summary:
                                        summary["key_events"] = []
                                    for event in item["events"][:10]:
                                        if isinstance(event, dict):
                                            summary["key_events"].append({
                                                "date": event.get("date"),
                                                "event": event.get("event") or event.get("description")
                                            })
                                
                                # Differential diagnosis
                                if "differential" in item and isinstance(item["differential"], list):
                                    summary["differential_diagnosis"] = item["differential"][:10]
                                
                                # Primary diagnosis (from Sidebar)
                                if "primaryDiagnosis" in item:
                                    summary["primary_diagnosis"] = item["primaryDiagnosis"]
                        
                        logger.info(f"📤 Returning summary with keys: {list(summary.keys())}")
                        logger.info(f"📤 Summary values: name={summary.get('name')}, age={summary.get('age')}, meds={len(summary.get('current_medications', []))}, labs={len(summary.get('recent_labs', []))}")
                        if pulmonary_locations:
                            logger.info(f"🔍 Pulmonary info found in: {pulmonary_locations}")
                        result = json.dumps(summary, indent=2)
                    
                    elif function_name == "focus_board_item":
                        query = arguments.get("query", "")
                        # Use side_agent to resolve object_id
                        context = json.dumps(self.context_data) if self.context_data else "{}"
                        object_id = await side_agent.resolve_object_id(query, context)
                        if object_id:
                            await canvas_ops.focus_item(object_id)
                            result = f"Focused on {object_id}"
                        else:
                            result = "Could not find matching board item"
                    
                    elif function_name == "create_task":
                        query = arguments.get("query", "")
                        # Use side_agent to generate and create task
                        task_result = await side_agent.generate_task_workflow(query)
                        result = f"Task created: {task_result}"
                    
                    elif function_name == "send_to_easl":
                        question = arguments.get("question", "")
                        # Use side_agent to trigger EASL
                        easl_result = await side_agent.trigger_easl(question)
                        result = f"Sent to EASL: {easl_result}"
                    
                    else:
                        result = f"Unknown tool: {function_name}"
                    
                except Exception as tool_error:
                    logger.error(f"Tool {function_name} error: {tool_error}")
                    result = f"Error executing {function_name}: {str(tool_error)}"
                
                function_responses.append(
                    types.FunctionResponse(
                        id=fc.id,
                        name=function_name,
                        response={"result": result}
                    )
                )
                
                logger.info(f"  ✅ Tool {function_name} completed")
            
            # Send responses back to Gemini - use correct Live API method
            await self.session.send(input={"function_responses": function_responses})
            
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            traceback.print_exc()
    
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
        """Receive audio and handle tool calls from Gemini Live"""
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
            # Load patient context using canvas_ops (agent-2.9 way)
            logger.info(f"Loading patient context for voice session...")
            self.context_data = canvas_ops.get_board_items()
            
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
