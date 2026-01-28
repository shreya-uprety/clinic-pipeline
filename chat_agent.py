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

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logger = logging.getLogger("chat-agent")

# Model Configuration
MODEL = "gemini-2.5-flash-lite"
MODEL_ADVANCED = "gemini-2.5-flash-lite"  # Use same model as existing agents


class RAGRetriever:
    """
    Retrieval-Augmented Generation (RAG) component.
    Retrieves relevant context from patient data stored in GCS.
    """
    
    def __init__(self, gcs_manager: bucket_ops.GCSBucketManager):
        """
        Initialize RAG retriever.
        
        Args:
            gcs_manager: GCS bucket manager instance
        """
        self.gcs = gcs_manager
        
    def retrieve_patient_context(self, patient_id: str) -> Dict[str, Any]:
        """
        Retrieve all relevant patient data for context.
        
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
        
        # Define data sources to retrieve
        data_sources = [
            ("patient_profile", f"patient_data/{patient_id}/patient_profile.txt"),
            ("basic_info", f"patient_data/{patient_id}/basic_info.json"),
            ("encounters", f"patient_data/{patient_id}/board_items/encounters.json"),
            ("patient_context", f"patient_data/{patient_id}/board_items/patient_context.json"),
            ("lab_track", f"patient_data/{patient_id}/board_items/dashboard_lab_track.json"),
            ("medication_track", f"patient_data/{patient_id}/board_items/dashboard_medication_track.json"),
            ("risk_events", f"patient_data/{patient_id}/board_items/dashboard_risk_event_track.json"),
            ("referral", f"patient_data/{patient_id}/board_items/referral.json"),
        ]
        
        for key, path in data_sources:
            try:
                content = self.gcs.read_file_as_string(path)
                # Try to parse as JSON if possible
                try:
                    context["data"][key] = json.loads(content)
                except json.JSONDecodeError:
                    context["data"][key] = content
                    
                logger.info(f"Retrieved {key} for patient {patient_id}")
            except Exception as e:
                logger.warning(f"Could not retrieve {key}: {e}")
                context["data"][key] = None
                
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
    
    def __init__(self, gcs_manager: bucket_ops.GCSBucketManager):
        """
        Initialize tool executor.
        
        Args:
            gcs_manager: GCS bucket manager instance
        """
        self.gcs = gcs_manager
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
            lab_data = json.loads(
                self.gcs.read_file_as_string(f"patient_data/{patient_id}/board_items/dashboard_lab_track.json")
            )
            
            if biomarker:
                # Filter for specific biomarker
                filtered = [item for item in lab_data.get("biomarkers", []) 
                           if biomarker.lower() in item.get("name", "").lower()]
                return {"status": "success", "biomarkers": filtered, "count": len(filtered)}
            
            return {"status": "success", **lab_data}
        except Exception as e:
            logger.warning(f"No lab data for patient {patient_id}: {e}")
            return {"status": "not_found", "message": f"No laboratory results found for patient {patient_id}."}
    
    def get_patient_medications(self, patient_id: str, active_only: bool = False) -> Dict[str, Any]:
        """Retrieve patient medications."""
        try:
            med_data = json.loads(
                self.gcs.read_file_as_string(f"patient_data/{patient_id}/board_items/dashboard_medication_track.json")
            )
            
            if active_only:
                # Filter for active medications (no end date or future end date)
                current_date = datetime.now().isoformat()
                filtered = [med for med in med_data.get("medications", [])
                           if not med.get("endDate") or med.get("endDate") > current_date]
                return {"status": "success", "medications": filtered, "count": len(filtered)}
            
            return {"status": "success", **med_data}
        except Exception as e:
            logger.warning(f"No medication data for patient {patient_id}: {e}")
            return {"status": "not_found", "message": f"No medication records found for patient {patient_id}."}
    
    def get_patient_encounters(self, patient_id: str, limit: int = 10) -> Dict[str, Any]:
        """Retrieve patient encounters."""
        try:
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
                    if query.lower() in content.lower():
                        results.append({
                            "source": file_path.split("/")[-1],
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
        self.retriever = RAGRetriever(self.gcs)
        self.tool_executor = ToolExecutor(self.gcs) if use_tools else None
        
        self.patient_id = patient_id
        self.conversation_history: List[Dict[str, str]] = []
        self.context_data: Optional[Dict] = None
        
        # Load patient context if patient_id provided
        if patient_id:
            self._load_patient_context()
    
    def _load_patient_context(self):
        """Load patient context data for RAG."""
        try:
            self.context_data = self.retriever.retrieve_patient_context(self.patient_id)
            logger.info(f"Loaded context for patient {self.patient_id}")
        except Exception as e:
            logger.error(f"Failed to load patient context: {e}")
            self.context_data = None
    
    def _build_context_prompt(self) -> str:
        """Build context prompt from retrieved data."""
        if not self.context_data or not self.context_data.get("data"):
            return ""
        
        context_parts = ["=== PATIENT CONTEXT ===\n"]
        
        data = self.context_data["data"]
        
        # Add patient profile (most important)
        if data.get("patient_profile"):
            context_parts.append(f"## Patient Profile\n{data['patient_profile']}\n")
        
        # Add structured data summaries
        if data.get("patient_context"):
            context_parts.append(f"## Clinical Summary\n{json.dumps(data['patient_context'], indent=2)}\n")
        
        if data.get("medication_track"):
            meds = data["medication_track"].get("medications", [])
            if meds:
                context_parts.append(f"## Current Medications ({len(meds)} total)\n")
                for med in meds[:5]:  # Show top 5
                    context_parts.append(f"- {med.get('name')}: {med.get('dose')}\n")
        
        context_parts.append("\n=== END CONTEXT ===\n")
        
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
        # Default system instruction
        if not system_instruction:
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

        # Build full prompt with context
        context_prompt = self._build_context_prompt()
        full_message = f"{context_prompt}\n\nUser Question: {message}"
        
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
                        follow_up = await self.client.aio.models.generate_content(
                            model=MODEL,
                            contents=[
                                full_message,
                                response.candidates[0].content,
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
            system_instruction = "You are a helpful medical AI assistant."
        
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
                        follow_up = await self.client.aio.models.generate_content(
                            model=MODEL,
                            contents=[
                                full_message,
                                response.candidates[0].content,
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
            
            complete_response = response.text
            
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
