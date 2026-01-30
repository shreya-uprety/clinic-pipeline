import warnings
from google.genai.types import GenerateContentConfig
# Suppress deprecation warning for google.generativeai (agent-2.9 legacy code)
warnings.filterwarnings('ignore', category=FutureWarning, module='google.generativeai')
import google.generativeai as genai
import time
import json
import asyncio
import os
import threading
from dotenv import load_dotenv
import side_agent
import canvas_ops
load_dotenv()




genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL = "gemini-2.5-flash-lite"


with open("system_prompts/chat_model_system.md", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()




async def get_answer(query :str, conversation_text: str='', context: str=''):
    if not context:
        # Use canvas_ops directly like agent-2.9
        context_raw = canvas_ops.get_board_items()
        context = json.dumps(context_raw, indent=4)
    prompt = f"""
    Answer below user query using available data. Keep response brief - maximum 3 sentences.
    Be direct and concise.
    
    User query : {query}

    Chat History : 
    {conversation_text}

    Context : 
    {context}
    """

    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_PROMPT
    )

    response = model.generate_content(prompt)

    return response.text.strip()

async def chat_agent(chat_history: list[dict]) -> str:
    """
    Chat Agent:
    Takes a list of messages (chat history) and returns a natural language response.
    History format:
    [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."},
        ...
    ]
    """

    # Convert chat history into model-friendly input 
    conversation = []
    if len(chat_history) > 1:
        for msg in chat_history[:-1]:
            conversation.append(f"{msg.get('role')}: {msg.get('content')}")

    conversation_text = "\n".join(conversation)
    
    query = chat_history[-1].get('content')
    # Use canvas_ops directly like agent-2.9
    context_raw = canvas_ops.get_board_items()
    context = json.dumps(context_raw, indent=4)

    # Tools check
    print("Tools check") 
    tool_res = side_agent.parse_tool(query)
    print("Tools use :", tool_res)

    lower_q = query.lower()
    if 'easl' in lower_q or 'guideline' in lower_q:
        result = await side_agent.trigger_easl(query)
        return f"✅ EASL query completed. Result: {json.dumps(result, indent=2)}"
    
        
    elif tool_res.get('tool') == "get_easl_answer":
        result = await side_agent.trigger_easl(query)
        return f"✅ EASL query completed. Result: {json.dumps(result, indent=2)}"
    
    elif tool_res.get('tool') == "generate_task":
        result = await side_agent.generate_task_workflow(query)
        return f"✅ Task workflow created successfully. {json.dumps(result, indent=2)}"
    
    elif tool_res.get('tool') == "navigate_canvas":
        # For navigate operations, use resolve_object_id and focus
        try:
            object_id = await side_agent.resolve_object_id(query, context)
            if object_id:
                await canvas_ops.focus_item(object_id)
                return f"✅ Navigated to {object_id} on canvas"
            else:
                return "❌ Could not identify the object to navigate to"
        except Exception as e:
            return f"❌ Navigation failed: {str(e)}"
    
    elif tool_res.get('tool') == "create_schedule":
        schedule = await get_schedule()
        return f"✅ Schedule created: {schedule}"
    
    elif tool_res.get('tool') == "send_notification":
        notification = await get_notification()
        return f"✅ Notification sent: {notification}"

    else:
        answer = await get_answer(query, conversation_text, context)
        return answer

async def get_schedule():
    return {
        "title": "Schedule created",
        "description": "A new schedule has been created based on your request."
    }

async def get_notification():
    return {
        "title": "Notification sent",
        "description": "Your notification has been sent to the relevant parties."
    }
