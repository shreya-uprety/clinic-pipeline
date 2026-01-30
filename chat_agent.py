"""
General-Purpose Gemini Chat Agent with RAG and Tool Execution
================================================================

This module provides a flexible chat agent that can:
1. Retrieve relevant context from patient data (RAG)
2. Execute tools/functions based on user queries
3. Maintain conversation history
4. Stream responses

Author: AI Developer Assistant
Date: January 27, 2026
"""

import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from google import genai
from google.genai import types
import bucket_ops
import httpx

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logger = logging.getLogger("chat-agent")

# Model Configuration
MODEL = "gemini-2.5-flash-lite"
MODEL_ADVANCED = "gemini-2.5-flash-lite"  # Use same model as existing agents

# Board URL configuration
BOARD_BASE_URL = "https://iso-clinic-v3.vercel.app"


class RAGRetriever:
    """
    Retrieval-Augmented Generation (RAG) component.
    Retrieves relevant context from patient board data via API.
    """
    
    def __init__(self, board_base_url: str = BOARD_BASE_URL):
        """
        Initialize RAG retriever.
        
        Args:
            board_base_url: Base URL for the board API
        """
        self.board_base_url = board_base_url
        
    async def retrieve_patient_context(self, patient_id: str) -> Dict[str, Any]:
        """
        Retrieve all relevant patient data from the board.
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            Dictionary containing patient context data
        """
        context = {
            "patient_id": patient_id,
            "retrieved_at": datetime.now().isoformat(),
            "data": {}
        }
        
        try:
            # Fetch board items from the API
            board_url = f"{self.board_base_url}/api/board-items?patientId={patient_id}"
            logger.info(f"Fetching board data from: {board_url}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(board_url)
                response.raise_for_status()
                board_data = response.json()
                
            logger.info(f"✅ Successfully fetched board data for patient {patient_id}")
            logger.info(f"Board data structure: {type(board_data)}, keys: {list(board_data.keys()) if isinstance(board_data, dict) else 'N/A'}")
            
            # Parse and organize the board data
            if isinstance(board_data, list):
                # Board returns a list of items directly
                logger.info(f"Processing {len(board_data)} board items...")
                
                for idx, item in enumerate(board_data):
                    if not isinstance(item, dict):
                        continue
                    
                    # Log the keys of this item for debugging
                    item_keys = list(item.keys())
                    logger.info(f"Item {idx} keys: {item_keys}")
                    
                    # Extract patient profile data
                    if 'patientProfile' in item:
                        context["data"]["patient_profile"] = item['patientProfile']
                        logger.info(f"Found patientProfile")
                    
                    # Extract patient basic data
                    if 'patient' in item and isinstance(item['patient'], dict):
                        context["data"]["basic_info"] = item['patient']
                        logger.info(f"Found patient data: {list(item['patient'].keys())}")
                    
                    # Extract patientData
                    if 'patientData' in item:
                        if 'patient_context' not in context["data"]:
                            context["data"]["patient_context"] = {}
                        context["data"]["patient_context"].update(item['patientData'])
                        logger.info(f"Found patientData")
                    
                    # Extract primary diagnosis
                    if 'primaryDiagnosis' in item:
                        if 'patient_context' not in context["data"]:
                            context["data"]["patient_context"] = {}
                        context["data"]["patient_context"]["primaryDiagnosis"] = item['primaryDiagnosis']
                        logger.info(f"Found primaryDiagnosis")
                    
                    # Check for adverse events / risk events
                    if 'adverseEvents' in item:
                        context["data"]["risk_events"] = {"events": item['adverseEvents']}
                    
                    # Check for medications
                    if 'medications' in item or 'currentMedications' in item:
                        meds = item.get('medications') or item.get('currentMedications', [])
                        context["data"]["medication_track"] = {"medications": meds}
                    
                    # Check for lab results
                    if 'labResults' in item or 'labs' in item or 'biomarkers' in item:
                        labs = item.get('labResults') or item.get('labs') or item.get('biomarkers', [])
                        context["data"]["lab_track"] = {"biomarkers": labs}
                    
                    # Check for encounters/visits
                    if 'encounters' in item or 'visits' in item:
                        encounters = item.get('encounters') or item.get('visits', [])
                        context["data"]["encounters"] = {"encounters": encounters}
                    
                    # Store the entire item if it has many fields (might be the main patient object)
                    if len(item_keys) > 5:
                        # This looks like a comprehensive patient object
                        for key, value in item.items():
                            if key not in context["data"]:
                                context["data"][key] = value
                        
            elif isinstance(board_data, dict) and "items" in board_data:
                items = board_data["items"]
                
                # Organize items by type
                for item in items:
                    item_type = item.get("type", "unknown")
                    
                    if item_type == "patient_context":
                        context["data"]["patient_context"] = item.get("data", {})
                    elif item_type == "basic_info":
                        context["data"]["basic_info"] = item.get("data", {})
                    elif item_type == "encounters":
                        context["data"]["encounters"] = item.get("data", {})
                    elif item_type == "lab_track" or item_type == "dashboard_lab_track":
                        context["data"]["lab_track"] = item.get("data", {})
                    elif item_type == "medication_track" or item_type == "dashboard_medication_track":
                        context["data"]["medication_track"] = item.get("data", {})
                    elif item_type == "risk_events" or item_type == "dashboard_risk_event_track":
                        context["data"]["risk_events"] = item.get("data", {})
                    elif item_type == "referral":
                        context["data"]["referral"] = item.get("data", {})
                        
            elif isinstance(board_data, list):
                # If the API returns a list directly
                for item in board_data:
                    item_type = item.get("type", "unknown")
                    
                    if item_type == "patient_context":
                        context["data"]["patient_context"] = item.get("data", {})
                    elif item_type == "basic_info":
                        context["data"]["basic_info"] = item.get("data", {})
                    elif item_type == "encounters":
                        context["data"]["encounters"] = item.get("data", {})
                    elif item_type == "lab_track" or item_type == "dashboard_lab_track":
                        context["data"]["lab_track"] = item.get("data", {})
                    elif item_type == "medication_track" or item_type == "dashboard_medication_track":
                        context["data"]["medication_track"] = item.get("data", {})
                    elif item_type == "risk_events" or item_type == "dashboard_risk_event_track":
                        context["data"]["risk_events"] = item.get("data", {})
                    elif item_type == "referral":
                        context["data"]["referral"] = item.get("data", {})
            else:
                # Store the raw data
                context["data"]["raw_board_data"] = board_data
                
            logger.info(f"Parsed board data types: {list(context['data'].keys())}")
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching board data: {e}")
            context["data"]["error"] = str(e)
        except Exception as e:
            logger.error(f"Error fetching board data: {e}")
            import traceback
            traceback.print_exc()
            context["data"]["error"] = str(e)
                
        return context
    
    def retrieve_medical_knowledge(self, query: str) -> str:
        """
        Retrieve relevant medical knowledge based on query.
        This is a placeholder for future vector database integration.
        
        Args:
            query: User query text
            
        Returns:
            Relevant medical knowledge snippets
        """
        # TODO: Implement vector database retrieval (e.g., ChromaDB, Pinecone)
        # For now, return empty context
        logger.info(f"Knowledge retrieval requested for: {query}")
        return ""


class ToolExecutor:
    """
    Handles tool/function execution for the chat agent.
    Supports various medical and administrative tools.
    """
    
    def __init__(self, gcs_manager: bucket_ops.GCSBucketManager, context_data_ref: Optional[Dict] = None):
        """
        Initialize tool executor.
        
        Args:
            gcs_manager: GCS bucket manager instance
            context_data_ref: Reference to context data (from board)
        """
        self.gcs = gcs_manager
        self.context_data_ref = context_data_ref
        self.tools = self._register_tools()
        
    def _register_tools(self) -> Dict[str, Callable]:
        """
        Register available tools/functions.
        
        Returns:
            Dictionary mapping tool names to functions
        """
        return {
            "get_patient_labs": self.get_patient_labs,
            "get_patient_medications": self.get_patient_medications,
            "get_patient_encounters": self.get_patient_encounters,
            "search_patient_data": self.search_patient_data,
            "calculate_drug_interaction": self.calculate_drug_interaction,
        }
    
    def get_tool_declarations(self) -> List[types.Tool]:
        """
        Get Gemini-compatible tool declarations.
        
        Returns:
            List of tool declarations for Gemini API
        """
        tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="get_patient_labs",
                        description="Retrieve laboratory test results for a patient. Returns chronological lab values including dates, biomarker names, values, and reference ranges.",
                        parameters={
                            "type": "object",
                            "properties": {
                                "patient_id": {
                                    "type": "string",
                                    "description": "The patient ID (e.g., P0001)"
                                },
                                "biomarker": {
                                    "type": "string",
                                    "description": "Optional: specific biomarker to retrieve (e.g., 'ALT', 'Bilirubin'). If not specified, returns all."
                                }
                            },
                            "required": ["patient_id"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="get_patient_medications",
                        description="Retrieve current and past medications for a patient. Returns medication timeline with dates, doses, and indications.",
                        parameters={
                            "type": "object",
                            "properties": {
                                "patient_id": {
                                    "type": "string",
                                    "description": "The patient ID (e.g., P0001)"
                                },
                                "active_only": {
                                    "type": "boolean",
                                    "description": "If true, returns only currently active medications"
                                }
                            },
                            "required": ["patient_id"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="get_patient_encounters",
                        description="Retrieve past medical encounters/visits for a patient. Returns visit dates, providers, diagnoses, and treatments.",
                        parameters={
                            "type": "object",
                            "properties": {
                                "patient_id": {
                                    "type": "string",
                                    "description": "The patient ID (e.g., P0001)"
                                },
                                "limit": {
                                    "type": "integer",
                                    "description": "Maximum number of encounters to return (default: 10)"
                                }
                            },
                            "required": ["patient_id"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="search_patient_data",
                        description="Search across all patient data for specific keywords or conditions. Useful for finding specific mentions of symptoms, diagnoses, or treatments.",
                        parameters={
                            "type": "object",
                            "properties": {
                                "patient_id": {
                                    "type": "string",
                                    "description": "The patient ID (e.g., P0001)"
                                },
                                "query": {
                                    "type": "string",
                                    "description": "Search query (e.g., 'jaundice', 'liver failure')"
                                }
                            },
                            "required": ["patient_id", "query"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="calculate_drug_interaction",
                        description="Check for potential drug-drug interactions between medications. Returns interaction severity and clinical recommendations.",
                        parameters={
                            "type": "object",
                            "properties": {
                                "drug_a": {
                                    "type": "string",
                                    "description": "First medication name"
                                },
                                "drug_b": {
                                    "type": "string",
                                    "description": "Second medication name"
                                }
                            },
                            "required": ["drug_a", "drug_b"]
                        }
                    ),
                ]
            )
        ]
        return tools
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool by name with given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            
        Returns:
            Tool execution result
        """
        if tool_name not in self.tools:
            return {
                "error": f"Tool '{tool_name}' not found",
                "available_tools": list(self.tools.keys())
            }
        
        try:
            result = self.tools[tool_name](**parameters)
            logger.info(f"Executed tool: {tool_name}")
            return result
        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
            return {"error": str(e)}
    
    # Tool Implementation Methods
    
    def get_patient_labs(self, patient_id: str, biomarker: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve patient laboratory results."""
        try:
            # Try to get from loaded context first
            lab_data = None
            if self.context_data_ref and isinstance(self.context_data_ref, dict):
                context = self.context_data_ref.get("data", {})
                lab_data = context.get("lab_track") or context.get("labs") or context.get("labResults")
            
            # Fallback to GCS if not in context
            if not lab_data:
                lab_data = json.loads(
                    self.gcs.read_file_as_string(f"patient_data/{patient_id}/board_items/dashboard_lab_track.json")
                )
            
            # Handle both list and dict formats
            if isinstance(lab_data, list):
                biomarkers = lab_data
            elif isinstance(lab_data, dict):
                biomarkers = lab_data.get("biomarkers", [])
            else:
                biomarkers = []
            
            if biomarker:
                # Filter for specific biomarker
                filtered = [item for item in biomarkers 
                           if biomarker.lower() in item.get("name", "").lower()]
                return {"status": "success", "biomarkers": filtered, "count": len(filtered)}
            
            return {"status": "success", "biomarkers": biomarkers, "count": len(biomarkers)}
        except Exception as e:
            logger.warning(f"No lab data for patient {patient_id}: {e}")
            return {"status": "not_found", "message": f"No laboratory results found for patient {patient_id}."}
    
    def get_patient_medications(self, patient_id: str, active_only: bool = False) -> Dict[str, Any]:
        """Retrieve patient medications."""
        try:
            # Try to get from loaded context first
            med_data = None
            if self.context_data_ref and isinstance(self.context_data_ref, dict):
                context = self.context_data_ref.get("data", {})
                med_data = context.get("medication_track") or context.get("medications") or context.get("medicationTimeline")
            
            # Fallback to GCS if not in context
            if not med_data:
                med_data = json.loads(
                    self.gcs.read_file_as_string(f"patient_data/{patient_id}/board_items/dashboard_medication_track.json")
                )
            
            # Handle both list and dict formats
            if isinstance(med_data, list):
                medications = med_data
            elif isinstance(med_data, dict):
                medications = med_data.get("medications", [])
            else:
                medications = []
            
            if active_only:
                # Filter for active medications (no end date or future end date)
                current_date = datetime.now().isoformat()
                filtered = [med for med in medications
                           if not med.get("endDate") or med.get("endDate") > current_date]
                return {"status": "success", "medications": filtered, "count": len(filtered)}
            
            return {"status": "success", "medications": medications, "count": len(medications)}
        except Exception as e:
            logger.warning(f"No medication data for patient {patient_id}: {e}")
            return {"status": "not_found", "message": f"No medication records found for patient {patient_id}."}
    
    def get_patient_encounters(self, patient_id: str, limit: int = 10) -> Dict[str, Any]:
        """Retrieve patient encounters."""
        try:
            # Try to get from loaded context first
            encounter_data = None
            if self.context_data_ref and isinstance(self.context_data_ref, dict):
                context = self.context_data_ref.get("data", {})
                encounter_data = context.get("encounters") or context.get("encounter")
            
            # Fallback to GCS if not in context
            if not encounter_data:
                encounter_data = json.loads(
                    self.gcs.read_file_as_string(f"patient_data/{patient_id}/board_items/encounters.json")
                )
            
            # Handle both list and dict formats
            if isinstance(encounter_data, list):
                encounters = encounter_data[:limit]
            elif isinstance(encounter_data, dict):
                encounters = encounter_data.get("encounters", [])[:limit]
            else:
                encounters = []
            
            return {
                "status": "success",
                "encounters": encounters,
                "count": len(encounters)
            }
        except Exception as e:
            logger.warning(f"No encounter data for patient {patient_id}: {e}")
            return {
                "status": "not_found",
                "message": f"No encounter records found for patient {patient_id}. This patient may not have any documented encounters yet."
            }
    
    def search_patient_data(self, patient_id: str, query: str) -> Dict[str, Any]:
        """Search patient data for query."""
        try:
            # Retrieve all patient data
            files = [
                f"patient_data/{patient_id}/patient_profile.txt",
                f"patient_data/{patient_id}/board_items/patient_context.json",
            ]
            
            results = []
            for file_path in files:
                try:
                    content = self.gcs.read_file_as_string(file_path)
                    if content and query.lower() in content.lower():
                        results.append({
                            "source": file_path.split("/")[-1] if file_path else "unknown",
                            "snippet": self._extract_snippet(content, query)
                        })
                except:
                    continue
            
            return {
                "query": query,
                "results": results,
                "count": len(results)
            }
        except Exception as e:
            return {"error": f"Search failed: {e}"}
    
    def calculate_drug_interaction(self, drug_a: str, drug_b: str) -> Dict[str, Any]:
        """
        Check drug-drug interactions.
        This is a placeholder - in production, integrate with a drug database API.
        """
        # TODO: Integrate with DrugBank API or similar service
        logger.info(f"Drug interaction check: {drug_a} + {drug_b}")
        
        return {
            "drug_a": drug_a,
            "drug_b": drug_b,
            "note": "Drug interaction checking requires external API integration (e.g., DrugBank, RxNorm). This is a placeholder implementation.",
            "severity": "unknown",
            "recommendation": "Please consult a pharmacist or drug interaction database."
        }
    
    @staticmethod
    def _extract_snippet(text: str, query: str, context_chars: int = 200) -> str:
        """Extract text snippet around query match."""
        lower_text = text.lower()
        lower_query = query.lower()
        
        pos = lower_text.find(lower_query)
        if pos == -1:
            return ""
        
        start = max(0, pos - context_chars)
        end = min(len(text), pos + len(query) + context_chars)
        
        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        
        return snippet


class ChatAgent:
    """
    Main chat agent class with RAG and tool execution capabilities.
    Maintains conversation history and provides intelligent responses.
    """
    
    def __init__(self, patient_id: Optional[str] = None, use_tools: bool = True):
        """
        Initialize chat agent.
        
        Args:
            patient_id: Optional patient ID for context
            use_tools: Whether to enable tool execution
        """
        self.client = genai.Client(
            api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        self.gcs = bucket_ops.GCSBucketManager(bucket_name="clinic_sim")
        self.retriever = RAGRetriever(board_base_url=BOARD_BASE_URL)
        
        self.patient_id = patient_id
        self.conversation_history: List[Dict[str, str]] = []
        self.context_data: Optional[Dict] = None
        
        # Initialize tool executor with reference to context data
        self.tool_executor = ToolExecutor(self.gcs, self.context_data) if use_tools else None
        
        # Load patient context if patient_id provided
        if patient_id:
            asyncio.create_task(self._load_patient_context())
    
    async def _load_patient_context(self):
        """Load patient context data for RAG."""
        try:
            logger.info(f"Loading context for patient {self.patient_id}...")
            self.context_data = await self.retriever.retrieve_patient_context(self.patient_id)
            
            # Update tool executor's context reference
            if self.tool_executor:
                self.tool_executor.context_data_ref = self.context_data
            
            # Log what was retrieved
            if self.context_data and self.context_data.get("data"):
                data_keys = list(self.context_data["data"].keys())
                logger.info(f"✅ Loaded context for patient {self.patient_id}: {data_keys}")
            else:
                logger.warning(f"⚠️ No context data found for patient {self.patient_id}")
        except Exception as e:
            logger.error(f"❌ Failed to load patient context: {e}")
            import traceback
            traceback.print_exc()
            self.context_data = None
    
    async def reload_context(self):
        """Reload patient context data (useful if data has been updated)."""
        if self.patient_id:
            await self._load_patient_context()
    
    def _build_context_prompt(self) -> str:
        """Build context prompt from retrieved data."""
        if not self.context_data or not self.context_data.get("data"):
            return ""
        
        context_parts = ["\n=== PATIENT CONTEXT (USE THIS TO ANSWER QUESTIONS) ===\n\n"]
        
        data = self.context_data["data"]
        
        # Add patient profile first (most comprehensive)
        if data.get("patient_profile"):
            profile = data["patient_profile"]
            context_parts.append("## Patient Profile\n")
            if isinstance(profile, dict):
                for key, value in profile.items():
                    if key not in ['id', 'x', 'y', 'width', 'height', 'zone', 'componentType']:
                        context_parts.append(f"- {key}: {value}\n")
            else:
                context_parts.append(f"{profile}\n")
            context_parts.append("\n")
        
        # Add basic info (name, demographics)
        if data.get("basic_info"):
            basic_info = data["basic_info"]
            context_parts.append("## Basic Patient Information\n")
            if isinstance(basic_info, dict):
                for key, value in basic_info.items():
                    if key not in ['id', 'x', 'y', 'width', 'height', 'zone', 'componentType']:
                        context_parts.append(f"- {key}: {value}\n")
            else:
                context_parts.append(f"{basic_info}\n")
            context_parts.append("\n")
        
        # Add patient profile (most important)
        if data.get("patient_profile"):
            context_parts.append(f"## Patient Profile\n{data['patient_profile']}\n\n")
        
        # Add structured data summaries
        if data.get("patient_context"):
            context_parts.append(f"## Clinical Summary\n{json.dumps(data['patient_context'], indent=2)}\n\n")
        
        # Add encounters
        if data.get("encounters"):
            encounters = data["encounters"]
            if isinstance(encounters, dict) and encounters.get("encounters"):
                enc_list = encounters["encounters"]
                context_parts.append(f"## Recent Encounters ({len(enc_list)} total)\n")
                for enc in enc_list[:3]:  # Show top 3
                    context_parts.append(f"- {enc.get('date')}: {enc.get('type')} - {enc.get('summary', 'N/A')}\n")
                context_parts.append("\n")
        
        # Add medications
        if data.get("medication_track"):
            meds_data = data["medication_track"]
            if isinstance(meds_data, dict):
                meds = meds_data.get("medications", [])
                if meds:
                    context_parts.append(f"## Current Medications ({len(meds)} total)\n")
                    for med in meds[:5]:  # Show top 5
                        context_parts.append(f"- {med.get('name')}: {med.get('dose', 'N/A')}\n")
                    context_parts.append("\n")
        
        # Add lab tracking
        if data.get("lab_track"):
            lab_data = data["lab_track"]
            if isinstance(lab_data, dict) and lab_data.get("biomarkers"):
                context_parts.append(f"## Lab Results Summary\n")
                biomarkers = lab_data.get("biomarkers", [])
                for biomarker in biomarkers[:5]:  # Show top 5
                    name = biomarker.get("name", "Unknown")
                    latest = biomarker.get("latest_value", "N/A")
                    context_parts.append(f"- {name}: {latest}\n")
                context_parts.append("\n")
        
        # Add risk events
        if data.get("risk_events"):
            risk_data = data["risk_events"]
            if isinstance(risk_data, dict) and risk_data.get("events"):
                events = risk_data["events"]
                if events:
                    context_parts.append(f"## Risk Events ({len(events)} total)\n")
                    for event in events[:3]:
                        context_parts.append(f"- {event.get('date')}: {event.get('type')} - {event.get('description', 'N/A')}\n")
                    context_parts.append("\n")
        
        context_parts.append("=== END PATIENT CONTEXT ===\n\n")
        context_parts.append("IMPORTANT: Use the above patient context to answer questions about the patient's name, demographics, medical history, medications, lab results, and encounters. Do not say you don't have access to this information if it's provided above.\n\n")
        
        return "".join(context_parts)
    
    async def chat(self, message: str, system_instruction: Optional[str] = None) -> str:
        """
        Send a message and get a response.
        
        Args:
            message: User message
            system_instruction: Optional system instruction override
            
        Returns:
            Agent response text
        """
        # Default system instruction - try to load from file
        if not system_instruction:
            try:
                with open("system_prompts/system_prompt.md", "r", encoding="utf-8") as f:
                    base_prompt = f.read()
                
                system_instruction = f"""{base_prompt}

--- PATIENT-SPECIFIC CONTEXT ---
Current Patient ID: {self.patient_id}
Board URL: https://iso-clinic-v3.vercel.app/board/{self.patient_id}

CRITICAL INSTRUCTIONS:
- You are currently helping with patient ID: {self.patient_id}
- When using tools, ALWAYS use patient_id: {self.patient_id}
"""
            except Exception as e:
                logger.warning(f"Failed to load system prompt, using fallback: {e}")
                system_instruction = """You are an expert medical AI assistant specializing in hepatology and clinical care.
            
Your capabilities:
1. Answer medical questions using the patient context provided
2. Retrieve specific data using available tools
3. Provide evidence-based clinical reasoning
4. Maintain patient confidentiality

Guidelines:
- Always reference specific data from the patient context when available
- If you need more information, use the available tools
- Be clear about limitations and uncertainties
- Use medical terminology appropriately but explain complex concepts
- Prioritize patient safety in all recommendations

When patient context is provided, use it to give personalized answers."""

        # Ensure context is loaded
        if self.patient_id and not self.context_data:
            logger.info("Context not loaded yet, loading now...")
            await self._load_patient_context()

        # Build full prompt with context
        context_prompt = self._build_context_prompt()
        full_message = f"{context_prompt}\n\nUser Question: {message}"
        
        # Debug logging
        if context_prompt:
            logger.info(f"Including patient context in prompt ({len(context_prompt)} chars)")
        else:
            logger.warning(f"No patient context available for patient {self.patient_id}")
        
        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": message
        })
        
        try:
            # Prepare config
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,  # Lower for more factual responses
            )
            
            # Add tools if enabled
            if self.tool_executor:
                config.tools = self.tool_executor.get_tool_declarations()
            
            # Make API call
            response = await self.client.aio.models.generate_content(
                model=MODEL,
                contents=full_message,
                config=config
            )
            
            # Handle tool calls if present
            if hasattr(response.candidates[0].content, 'parts'):
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        # Execute the tool
                        tool_result = self.tool_executor.execute_tool(
                            part.function_call.name,
                            dict(part.function_call.args)
                        )
                        
                        # Ensure tool_result is a dict (wrap if needed)
                        if not isinstance(tool_result, dict):
                            tool_result = {"result": tool_result}
                        
                        # Send tool result back to model
                        # Filter out None parts from the response content
                        model_parts = [p for p in response.candidates[0].content.parts if p is not None]
                        
                        follow_up = await self.client.aio.models.generate_content(
                            model=MODEL,
                            contents=[
                                full_message,
                                types.Content(role="model", parts=model_parts),
                                types.Part.from_function_response(
                                    name=part.function_call.name,
                                    response=tool_result
                                )
                            ],
                            config=types.GenerateContentConfig(
                                system_instruction=system_instruction,
                                temperature=0.3
                            )
                        )
                        response = follow_up
            
            response_text = response.text
            
            # Add to history
            self.conversation_history.append({
                "role": "assistant",
                "content": response_text
            })
            
            return response_text
            
        except Exception as e:
            logger.error(f"Chat error: {e}")
            error_msg = f"I apologize, but I encountered an error: {str(e)}"
            self.conversation_history.append({
                "role": "assistant",
                "content": error_msg
            })
            return error_msg
    
    async def chat_stream(self, message: str, system_instruction: Optional[str] = None):
        """
        Stream chat responses for real-time interaction.
        
        Args:
            message: User message
            system_instruction: Optional system instruction override
            
        Yields:
            Response chunks as they arrive
        """
        if not system_instruction:
            try:
                with open("system_prompts/system_prompt.md", "r", encoding="utf-8") as f:
                    base_prompt = f.read()
                
                system_instruction = f"""{base_prompt}

--- PATIENT-SPECIFIC CONTEXT ---
Current Patient ID: {self.patient_id}
Board URL: https://iso-clinic-v3.vercel.app/board/{self.patient_id}
"""
            except Exception as e:
                logger.warning(f"Failed to load system prompt for streaming: {e}")
                system_instruction = "You are a helpful medical AI assistant."
        
        # Ensure context is loaded
        if self.patient_id and not self.context_data:
            logger.info("Context not loaded yet, loading now...")
            await self._load_patient_context()
        
        context_prompt = self._build_context_prompt()
        full_message = f"{context_prompt}\n\nUser Question: {message}"
        
        self.conversation_history.append({
            "role": "user",
            "content": message
        })
        
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
            )
            
            if self.tool_executor:
                config.tools = self.tool_executor.get_tool_declarations()
            
            # Get complete response (simulate streaming by chunking)
            response = await self.client.aio.models.generate_content(
                model=MODEL,
                contents=full_message,
                config=config
            )
            
            # Handle tool calls if present
            if self.tool_executor and response.candidates:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        # Execute tool
                        logger.info(f"Executing tool: {part.function_call.name}")
                        tool_result = self.tool_executor.execute_tool(
                            part.function_call.name,
                            dict(part.function_call.args)
                        )
                        
                        # Ensure tool_result is a dict (wrap if needed)
                        if not isinstance(tool_result, dict):
                            tool_result = {"result": tool_result}
                        
                        # Send tool result back to model
                        # Filter out None parts from the response content
                        model_parts = [p for p in response.candidates[0].content.parts if p is not None]
                        
                        follow_up = await self.client.aio.models.generate_content(
                            model=MODEL,
                            contents=[
                                full_message,
                                types.Content(role="model", parts=model_parts),
                                types.Part.from_function_response(
                                    name=part.function_call.name,
                                    response=tool_result
                                )
                            ],
                            config=types.GenerateContentConfig(
                                system_instruction=system_instruction,
                                temperature=0.3
                            )
                        )
                        response = follow_up
            
            complete_response = response.text if response and hasattr(response, 'text') and response.text else ""
            
            # Handle empty or None response
            if not complete_response:
                logger.error("Stream error: Empty or None response from model")
                yield "I apologize, but I couldn't generate a response. Please try asking your question again."
                return
            
            # Simulate streaming by yielding in chunks
            chunk_size = 5  # Words per chunk
            words = complete_response.split()
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                if i + chunk_size < len(words):
                    chunk += " "
                yield chunk
                # Small delay to simulate streaming
                await asyncio.sleep(0.05)
            
            # Save complete response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": complete_response
            })
            
        except Exception as e:
            logger.error(f"Stream error: {e}")
            error_msg = f"Error: {str(e)}"
            yield error_msg
    
    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history."""
        return self.conversation_history
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        logger.info("Conversation history cleared")
    
    def save_history(self, filename: Optional[str] = None):
        """
        Save conversation history to GCS.
        
        Args:
            filename: Optional filename, defaults to timestamped file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"chat_history_{timestamp}.json"
        
        history_data = {
            "patient_id": self.patient_id,
            "saved_at": datetime.now().isoformat(),
            "conversation": self.conversation_history
        }
        
        path = f"patient_data/{self.patient_id}/chat_histories/{filename}"
        
        try:
            self.gcs.create_file_from_string(
                json.dumps(history_data, indent=2),
                path,
                content_type="application/json"
            )
            logger.info(f"Saved chat history to {path}")
        except Exception as e:
            logger.error(f"Failed to save history: {e}")


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def demo():
        """Demo the chat agent."""
        # Initialize agent for a patient
        agent = ChatAgent(patient_id="P0001", use_tools=True)
        
        # Example queries
        queries = [
            "What are the patient's current liver function test results?",
            "Can you summarize the patient's medication history?",
            "Are there any concerning trends in the lab values?"
        ]
        
        for query in queries:
            print(f"\n{'='*60}")
            print(f"User: {query}")
            print(f"{'='*60}")
            
            response = await agent.chat(query)
            print(f"Assistant: {response}")
            print()
        
        # Save history
        agent.save_history()
    
    asyncio.run(demo())
