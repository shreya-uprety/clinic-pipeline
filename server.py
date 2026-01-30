import uvicorn
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
import json
import base64 
import pandas as pd
import os
import traceback
import uuid

# Configure Logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("medforce-server")

# Import your agent class with error handling
try:
    import my_agents
    from my_agents import PreConsulteAgent
    logger.info("✅ my_agents imported successfully")
except Exception as e:
    logger.error(f"❌ Failed to import my_agents: {e}")
    my_agents = None
    PreConsulteAgent = None

try:
    import schedule_manager
    logger.info("✅ schedule_manager imported successfully")
except Exception as e:
    logger.error(f"❌ Failed to import schedule_manager: {e}")
    schedule_manager = None

try:
    import bucket_ops
    logger.info("✅ bucket_ops imported successfully")
except Exception as e:
    logger.error(f"❌ Failed to import bucket_ops: {e}")
    bucket_ops = None

# Import agent-2.9 modules
try:
    import chat_model
    import side_agent
    from patient_manager import patient_manager
    logger.info("✅ Agent-2.9 modules imported successfully")
except Exception as e:
    logger.error(f"❌ Failed to import Agent-2.9 modules: {e}")
    chat_model = None
    side_agent = None
    patient_manager = None

try:
    from websocket_agent import websocket_pre_consult_endpoint, websocket_chat_endpoint, get_websocket_agent
    logger.info("✅ websocket_agent imported successfully")
except Exception as e:
    logger.error(f"❌ Failed to import websocket_agent: {e}")
    websocket_pre_consult_endpoint = None
    websocket_chat_endpoint = None
    get_websocket_agent = None

try:
    from voice_websocket_handler import VoiceWebSocketHandler
    logger.info("✅ VoiceWebSocketHandler imported successfully")
except Exception as e:
    logger.error(f"❌ Failed to import VoiceWebSocketHandler: {e}")
    VoiceWebSocketHandler = None

# Initialize FastAPI app
app = FastAPI(title="MedForce Hepatology Chat Server")

# Add CORS Middleware (allows your frontend to talk to this server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the Agent
# We instantiate it once so we don't reconnect to GCS/VertexAI on every request
chat_agent = None
if PreConsulteAgent:
    try:
        chat_agent = PreConsulteAgent()
        logger.info("✅ PreConsulteAgent initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️ PreConsulteAgent initialization failed: {e}")

gcs = None
if bucket_ops:
    try:
        gcs = bucket_ops.GCSBucketManager(bucket_name="clinic_sim")
        logger.info("✅ GCS Bucket Manager initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️ GCS Bucket Manager initialization failed: {e}")


# Startup event
@app.on_event("startup")
async def startup_event():
    """Log startup information"""
    port = os.environ.get("PORT", "8080")
    logger.info("=" * 60)
    logger.info("🚀 MedForce Clinic Sim Pipeline Starting")
    logger.info(f"📍 Listening on port: {port}")
    logger.info(f"🏥 PreConsulteAgent: {'Ready' if chat_agent else 'Not Available'}")
    logger.info(f"☁️ GCS Manager: {'Ready' if gcs else 'Not Available'}")
    logger.info("=" * 60)


# --- Pydantic Models ---
class PatientRegistrationRequest(BaseModel):
    # We use Optional for fields that might be missing, 
    # though your agent tries to collect them all.
    first_name: str
    last_name: str
    dob: str
    gender: str
    occupation: Optional[str] = None
    marital_status: Optional[str] = None
    phone: str
    email: str
    address: Optional[str] = None
    
    # Emergency Contact
    emergency_name: Optional[str] = None
    emergency_relation: Optional[str] = None
    emergency_phone: Optional[str] = None
    
    # Medical Data
    chief_complaint: str
    medical_history: Optional[str] = "None"
    allergies: Optional[str] = "None"

class RegistrationResponse(BaseModel):
    patient_id: str
    status: str

class SlotResponse(BaseModel):
    available_slots: List[dict]

class ScheduleRequestBase(BaseModel):
    clinician_id: str  # e.g., N0001
    date: str          # e.g., 2026-01-22
    time: str          # e.g., 8:00

class ScheduleBase(BaseModel):
    clinician_id: str  # e.g., N0001

class ScheduleBasePatient(BaseModel):
    patient: str  # e.g., P0001
    date: str          # e.g., 2026-01-22
    time: str          # e.g., 8:00

class SwitchSchedule(ScheduleBase):
    item1: Optional[ScheduleBasePatient] = None
    item2: Optional[ScheduleBasePatient] = None


class UpdateSlotRequest(ScheduleRequestBase):
    patient: Optional[str] = None
    status: Optional[str] = None

class FileAttachment(BaseModel):
    filename: str
    content_base64: str  # The file bytes encoded as a Base64 string

class ChatRequest(BaseModel):
    patient_id: str
    patient_message: str
    # Changed to accept a list of objects containing the data
    patient_attachments: Optional[List[FileAttachment]] = None 
    patient_form: Optional[dict] = None

class ChatResponse(BaseModel):
    patient_id: str
    nurse_response: dict # Changed from str to dict to handle the rich JSON
    status: str

# --- Endpoints ---

@app.get("/")
async def root():
    return {"status": "MedForce Server is Running"}

@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run"""
    return {
        "status": "healthy",
        "service": "clinic-sim-pipeline",
        "port": os.environ.get("PORT", 8080)
    }

@app.post("/chat", response_model=ChatResponse)
async def handle_chat(payload: ChatRequest):
    """
    Receives JSON payload with Base64 encoded files.
    Decodes files -> Saves to GCS -> Passes filenames to Agent.
    """
    logger.info(f"Received message from patient: {payload.patient_id}")

    try:
        # 1. HANDLE FILE UPLOADS (Base64 -> GCS)
        filenames_for_agent = []
        
        if payload.patient_attachments:
            for att in payload.patient_attachments:
                try:
                    # Decode the Base64 string back to bytes
                    # Handle cases where frontend might send "data:image/png;base64,..." header
                    if "," in att.content_base64:
                        header, encoded = att.content_base64.split(",", 1)
                    else:
                        encoded = att.content_base64

                    file_bytes = base64.b64decode(encoded)

                    # Save to GCS
                    file_path = f"patient_data/{payload.patient_id}/raw_data/{att.filename}"
                    
                    # We can try to infer content type from filename extension or header
                    content_type = "application/octet-stream"
                    if att.filename.lower().endswith(".png"): content_type = "image/png"
                    elif att.filename.lower().endswith(".jpg"): content_type = "image/jpeg"
                    elif att.filename.lower().endswith(".pdf"): content_type = "application/pdf"

                    chat_agent.gcs.create_file_from_string(
                        file_bytes, 
                        file_path, 
                        content_type=content_type
                    )
                    
                    # Keep track of just the filename for the agent
                    filenames_for_agent.append(att.filename)
                    logger.info(f"Saved file via Base64: {att.filename}")

                except Exception as e:
                    logger.error(f"Failed to decode file {att.filename}: {e}")

        # 2. PREPARE AGENT INPUT
        # Convert Pydantic model to dict, but override the attachments with just filenames
        agent_input = {
            "patient_message": payload.patient_message,
            "patient_attachment": filenames_for_agent, # Agent gets ["lab.png"], NOT the bytes
            "patient_form": payload.patient_form
        }

        # 3. CALL AGENT
        response_data = await chat_agent.pre_consulte_agent(
            user_request=agent_input,
            patient_id=payload.patient_id
        )

        return ChatResponse(
            patient_id=payload.patient_id,
            nurse_response=response_data,
            status="success"
        )

    except FileNotFoundError:
        logger.error(f"Patient data not found for ID: {payload.patient_id}")
        raise HTTPException(status_code=404, detail="Patient data not found.")
    
    except Exception as e:
        logger.error(f"Error processing chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/{patient_id}")
async def get_chat_history(patient_id: str):
    """
    Retrieves the full chat history for a specific patient.
    """
    try:
        # Define the path based on your folder structure in my_agents.py
        file_path = f"patient_data/{patient_id}/pre_consultation_chat.json"

        # Read file from GCS using the agent's existing GCS manager
        content_str = chat_agent.gcs.read_file_as_string(file_path)

        if not content_str:
            raise HTTPException(status_code=404, detail="Chat history file is empty or missing.")

        # Parse string back to JSON object to return proper structure
        history_data = json.loads(content_str)

        return history_data

    except Exception as e:
        logger.error(f"Error fetching chat history for {patient_id}: {str(e)}")
        # Check if it's a specific GCS 'Not Found' error if possible, otherwise generic 404
        raise HTTPException(status_code=404, detail=f"Chat history not found for patient {patient_id}")

@app.get("/patients")
async def get_patients():
    """
    Retrieves a list of all patient IDs.
    """
    patient_pool = []
    try:
        file_list = chat_agent.gcs.list_files("patient_data")
        for p in file_list:
            try:
                patient_id = p.replace('/',"")  # Extract patient ID from path
                basic_data = json.loads(chat_agent.gcs.read_file_as_string(f"patient_data/{patient_id}/basic_info.json"))
                patient_pool.append(basic_data)
            except Exception as e:
                print(f"Error reading basic info for {p}: {e}")
        return patient_pool
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error fetching patient list: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve patient list : {e}")

@app.post("/chat/{patient_id}/reset")
async def reset_chat_history(patient_id: str):
    """
    Resets the chat history for a specific patient to the default initial greeting.
    """
    try:
        # Define the default starting state
        default_chat_state = {
            "conversation": [
                {
                    'sender': 'admin',
                    'message': 'Hello, this is Linda the Hepatology Clinic admin desk. How can I help you today?'
                }
            ]
        }
        
        # Define the path in GCS
        file_path = f"patient_data/{patient_id}/pre_consultation_chat.json"
        
        # Convert to JSON string
        json_content = json.dumps(default_chat_state, indent=4)
        
        # Overwrite the file in GCS using the agent's bucket manager
        chat_agent.gcs.create_file_from_string(
            json_content, 
            file_path, 
            content_type="application/json"
        )
        
        logger.info(f"Chat history reset for patient: {patient_id}")
        
        return {
            "status": "success", 
            "message": "Chat history has been reset.",
            "current_state": default_chat_state
        }

    except Exception as e:
        logger.error(f"Error resetting chat for {patient_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to reset chat: {str(e)}")


# --- NEW: General Chat Agent Endpoints ---

class GeneralChatRequest(BaseModel):
    """Request model for general chat agent."""
    patient_id: str
    message: str
    use_tools: Optional[bool] = True


class GeneralChatResponse(BaseModel):
    """Response model for general chat agent."""
    patient_id: str
    response: str
    status: str


@app.post("/send-chat")
async def run_chat_agent(payload: list[dict]):
    """
    Chat endpoint using agent-2.9 architecture.
    Accepts chat history and returns agent response.
    """
    try:
        if patient_manager:
            # Extract patient_id if provided in first message metadata
            if len(payload) > 0 and isinstance(payload[0], dict):
                patient_id = payload[0].get('patient_id', patient_manager.get_patient_id())
                patient_manager.set_patient_id(patient_id)
        
        answer = await chat_model.chat_agent(payload)
        logger.info(f"Agent Answer: {answer[:200]}...")
        return {"response": answer, "status": "success"}
        
    except Exception as e:
        logger.error(f"Chat agent error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate_diagnosis")
async def gen_diagnosis(payload: dict):
    """Generate DILI diagnosis using agent-2.9"""
    try:
        if patient_manager and payload.get('patient_id'):
            patient_manager.set_patient_id(payload['patient_id'])
        
        await side_agent.create_dili_diagnosis()
        return {"status": "done"}
    except Exception as e:
        logger.error(f"Error generating diagnosis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_report")
async def gen_report(payload: dict):
    """Generate patient report using agent-2.9"""
    try:
        if patient_manager and payload.get('patient_id'):
            patient_manager.set_patient_id(payload['patient_id'])
        
        await side_agent.create_patient_report()
        return {"status": "done"}
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_legal")
async def gen_legal(payload: dict):
    """Generate legal report using agent-2.9"""
    try:
        if patient_manager and payload.get('patient_id'):
            patient_manager.set_patient_id(payload['patient_id'])
        
        await side_agent.create_legal_doc()
        return {"status": "done"}
    except Exception as e:
        logger.error(f"Error generating legal report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/patient/current")
async def get_current_patient():
    """Get current patient ID"""
    if patient_manager:
        return {"patient_id": patient_manager.get_patient_id()}
    return {"patient_id": "p0001"}

@app.post("/patient/switch")
async def switch_patient(payload: dict):
    """Switch current patient"""
    if patient_manager and payload.get('patient_id'):
        patient_manager.set_patient_id(payload['patient_id'])
        return {"status": "success", "patient_id": patient_manager.get_patient_id()}
    raise HTTPException(status_code=400, detail="Missing patient_id")


@app.get("/api/chat/{patient_id}/history")
async def get_general_chat_history(patient_id: str):
    """
    Get conversation history for general chat agent.
    """
    try:
        agent = ChatAgent(patient_id=patient_id, use_tools=False)
        history = agent.get_history()
        
        return {
            "patient_id": patient_id,
            "history": history,
            "message_count": len(history)
        }
        
    except Exception as e:
        logger.error(f"Error retrieving chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/{patient_id}/clear")
async def clear_general_chat_history(patient_id: str):
    """
    Clear conversation history for general chat agent.
    """
    try:
        agent = ChatAgent(patient_id=patient_id, use_tools=False)
        agent.clear_history()
        
        return {
            "status": "success",
            "message": "Chat history cleared"
        }
        
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- NEW: WebSocket Endpoints ---

@app.websocket("/ws/pre-consult/{patient_id}")
async def websocket_pre_consult(websocket: WebSocket, patient_id: str):
    """
    WebSocket endpoint for real-time pre-consultation chat (Linda the admin).
    
    Provides:
    - Real-time bidirectional communication
    - Typing indicators
    - Form and slot offerings
    - Attachment handling
    
    Client should send JSON messages with format:
    {
        "message": "user message text",
        "attachments": ["filename1.png", ...],
        "form_data": {...}
    }
    """
    if websocket_pre_consult_endpoint is None:
        await websocket.close(code=1011, reason="Service unavailable")
        return
    await websocket_pre_consult_endpoint(websocket, patient_id)


@app.websocket("/ws/chat/{patient_id}")
async def websocket_chat(websocket: WebSocket, patient_id: str):
    """
    WebSocket endpoint for real-time general chat with RAG + tools.
    
    Provides:
    - Streaming responses
    - Real-time tool execution
    - RAG-enhanced answers
    - Session persistence
    
    Client should send JSON messages with format:
    {
        "message": "user question",
        "stream": true  // optional, defaults to true
    }
    """
    if websocket_chat_endpoint is None:
        await websocket.close(code=1011, reason="Service unavailable")
        return
    await websocket_chat_endpoint(websocket, patient_id)


@app.websocket("/ws/voice/{patient_id}")
async def websocket_voice(websocket: WebSocket, patient_id: str):
    """
    WebSocket endpoint for real-time voice communication using Gemini Live API.
    
    Provides:
    - Continuous bidirectional audio streaming
    - Native speech-to-text and text-to-speech
    - Real-time tool execution during conversation
    - Low-latency voice interaction
    
    Client should send raw PCM audio bytes (16kHz, mono, 16-bit).
    Server will respond with raw PCM audio bytes (24kHz, mono, 16-bit).
    """
    if VoiceWebSocketHandler is None:
        await websocket.close(code=1011, reason="Voice service unavailable")
        return
    
    await websocket.accept()
    logger.info(f"🎙️ Voice WebSocket connected for patient: {patient_id}")
    
    try:
        handler = VoiceWebSocketHandler(websocket, patient_id)
        await handler.run()
    except Exception as e:
        logger.error(f"Voice WebSocket error: {e}")
        await websocket.close()


@app.get("/ws/sessions")
async def get_active_websocket_sessions():
    """
    Get information about all active WebSocket sessions.
    Useful for monitoring and debugging.
    """
    if get_websocket_agent is None:
        return {"error": "WebSocket agent not available", "sessions": []}
    
    agent = get_websocket_agent()
    if agent is None:
        return {"error": "WebSocket agent not available", "sessions": []}
    
    try:
        sessions = agent.get_active_sessions()
        return {
            "active_sessions": len(sessions),
            "sessions": sessions
        }
    except Exception as e:
        logger.error(f"Error getting session info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/process/{patient_id}/preconsult")
async def process_pre_consult(patient_id: str):
    """
    Resets the chat history for a specific patient to the default initial greeting.
    """
    try:
        data_process = my_agents.RawDataProcessing()
        await data_process.process_raw_data(patient_id)
        
        return {
            "status": "success", 
            "message": "Chat history has been reset."
            }

    except Exception as e:
        logger.error(f"Error processing patient for {patient_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process patient: {str(e)}")
    
@app.get("/process/{patient_id}/board")
async def process_board(patient_id: str):
    """
    Resets the chat history for a specific patient to the default initial greeting.
    """
    try:
        data_process = my_agents.RawDataProcessing()
        await data_process.process_dashboard_content(patient_id)
        
        return {
            "status": "success", 
            "message": "Board objects have been processed."
            }

    except Exception as e:
        logger.error(f"Error processing patient for {patient_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process patient: {str(e)}")
    
@app.get("/process/{patient_id}/board-update")
async def process_board_update(patient_id: str):
    """
    Resets the chat history for a specific patient to the default initial greeting.
    """
    try:
        data_process = my_agents.RawDataProcessing()
        await data_process.process_board_object(patient_id)
        
        return {
            "status": "success", 
            "message": "Board objects have been processed."
            }

    except Exception as e:
        logger.error(f"Error processing patient for {patient_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process patient: {str(e)}")

@app.get("/data/{patient_id}/{file_path}")
async def process_board_update(patient_id: str,file_path: str):
    """
    Resets the chat history for a specific patient to the default initial greeting.
    """
    try:
        blob_file_path = f"patient_data/{patient_id}/{file_path}"
        content_str = chat_agent.gcs.read_file_as_string(blob_file_path)
        data_json = json.loads(content_str)
        
        return data_json

    except Exception as e:
        logger.error(f"Error get data {file_path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process patient: {str(e)}")

@app.get("/image/{patient_id}/{file_path}")
async def get_image(patient_id:str, file_path: str):

    try:
        byte_data = chat_agent.gcs.read_file_as_bytes(f"patient_data/{patient_id}/raw_data/{file_path}")
        
        return {
            "file": file_path, 
            "data": byte_data
            }

    except Exception as e:
        logger.error(f"Error getting image for {patient_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get image: {str(e)}")

@app.get("/schedule/{clinician_id}")
async def get_schedule(clinician_id: str):

    try:
        if clinician_id.startswith("N"):
            doc_file = "nurse_schedule.csv"
        elif clinician_id.startswith("D"):
            doc_file = "doctor_schedule.csv"



        schedule_ops = schedule_manager.ScheduleCSVManager(gcs_manager=gcs, csv_blob_path=f"clinic_data/{doc_file}")
        return schedule_ops.get_all()

    except Exception as e:
        logger.error(f"Error getting schedule for {clinician_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get schedule: {str(e)}")        



@app.post("/schedule/update")
async def update_schedule_details(request: UpdateSlotRequest):
    """
    General update: Mark as 'done', 'break', 'cancelled', or correct a patient ID.
    Only updates fields that are provided (not None).
    """
    try:
        # 1. Determine File
        if request.clinician_id.startswith("N"):
            doc_file = "nurse_schedule.csv"
        elif request.clinician_id.startswith("D"):
            doc_file = "doctor_schedule.csv"
        else:
            raise HTTPException(status_code=400, detail="Invalid Clinician ID prefix")

        # 2. Initialize Manager
        schedule_ops = schedule_manager.ScheduleCSVManager(
            gcs_manager=gcs, 
            csv_blob_path=f"clinic_data/{doc_file}"
        )

        # 3. Dynamic Update Dict
        # Only add fields to the update dict if they are sent in the request
        updates = {}
        if request.patient is not None:
            updates["patient"] = request.patient
        if request.status is not None:
            updates["status"] = request.status

        if not updates:
            return {"message": "No changes requested."}

        # 4. Perform Update
        success = schedule_ops.update_slot(
            nurse_id=request.clinician_id,
            date=request.date,
            time=request.time,
            updates=updates
        )

        if not success:
            raise HTTPException(status_code=404, detail="Slot not found.")

        return {"message": "Schedule updated successfully."}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/schedule/switch")
async def update_schedule_details(request: SwitchSchedule):
    """
    General update: Mark as 'done', 'break', 'cancelled', or correct a patient ID.
    Only updates fields that are provided (not None).
    """
    try:
        # 1. Determine File
        if request.clinician_id.startswith("N"):
            doc_file = "nurse_schedule.csv"
        elif request.clinician_id.startswith("D"):
            doc_file = "doctor_schedule.csv"
        else:
            raise HTTPException(status_code=400, detail="Invalid Clinician ID prefix")

        # 2. Initialize Manager
        schedule_ops = schedule_manager.ScheduleCSVManager(
            gcs_manager=gcs, 
            csv_blob_path=f"clinic_data/{doc_file}"
        )

        # 3. Dynamic Update Dict
        # Only add fields to the update dict if they are sent in the request
        updates = {}
        if request.item1.patient is not None:
            updates["patient"] = request.item1.patient
        if request.item1.date is not None:
            updates["date"] = request.item1.date
        if request.item1.time is not None:
            updates["time"] = request.item1.time

        if not updates:
            return {"message": "No changes requested."}

        # 4. Perform Update
        success = schedule_ops.update_slot(
            nurse_id=request.clinician_id,
            date=request.item1.date,
            time=request.item1.time,
            updates=updates
        )

        updates = {}
        if request.item2.patient is not None:
            updates["patient"] = request.item2.patient
        if request.item2.date is not None:
            updates["date"] = request.item2.date
        if request.item2.time is not None:
            updates["time"] = request.item2.time

        if not updates:
            return {"message": "No changes requested."}

        # 4. Perform Update
        success = schedule_ops.update_slot(
            nurse_id=request.clinician_id,
            date=request.item2.date,
            time=request.item2.time,
            updates=updates
        )

        if not success:
            raise HTTPException(status_code=404, detail="Slot not found.")

        return {"message": "Schedule updated successfully."}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/register", response_model=RegistrationResponse)
async def register_patient(patient: PatientRegistrationRequest):
    """
    Receives patient data, 'saves' it to a database, and returns an ID.
    """
    print(f"--- Receiving Registration Request for {patient.first_name} {patient.last_name} ---")
    print(f"Complaint: {patient.chief_complaint}")
    
    # SIMULATION: Here you would write code to save to SQL/Firebase/Postgres
    # For now, we generate a fake Patient ID
    patient_data = patient.dict()
    patient_id = f"PT-{str(uuid.uuid4())[:8].upper()}"
    patient_data["patient_id"] = patient_id

    file_path = f"patient_data/{patient_id}/patient_form.json"
        
    # Convert to JSON string
    json_content = json.dumps(patient_data, indent=4)
    
    # Overwrite the file in GCS using the agent's bucket manager
    gcs.create_file_from_string(
        json_content, 
        file_path, 
        content_type="application/json"
    )
    # Return the response Dialogflow expects
    return {
        "patient_id": patient_id,
        "status": "Patient profile created successfully."
    }

@app.get("/slots", response_model=SlotResponse)
async def get_available_slots(doctor_type: Optional[str] = "General"):
    """
    Returns a list of available appointment slots.
    """
    print(f"--- Checking slots for doctor type: {doctor_type} ---")
    
    # SIMULATION: logic to get dates relative to 'today'

    schedule_ops = schedule_manager.ScheduleCSVManager(gcs_manager=gcs, csv_blob_path=f"clinic_data/doctor_schedule.csv")
    slots = schedule_ops.get_empty_schedule()

    return {"available_slots": slots}


# Agent-2.9 UI endpoint
@app.get("/ui/{file_path:path}")
async def serve_ui(file_path: str):
    """Serve UI files"""
    try:
        ui_file = os.path.join("ui", file_path)
        if os.path.exists(ui_file):
            with open(ui_file, "r", encoding="utf-8") as f:
                content = f.read()
            return HTMLResponse(content=content)
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Run Block ---
if __name__ == "__main__":
    # Run with: python server.py
    port = int(os.environ.get("PORT", 8080))

    uvicorn.run("server:app", host="0.0.0.0", port=port, log_level="info")