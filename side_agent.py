from google.genai.types import GenerateContentConfig
import google.generativeai as genai
import time
import json
import asyncio
import os
from dotenv import load_dotenv
import requests
import config
import canvas_ops
load_dotenv()
import helper_model
from patient_manager import patient_manager




BASE_URL = patient_manager.get_base_url()
print("#### side_agent.py CANVAS_URL : ",BASE_URL)
print("#### Current Patient ID: ", patient_manager.get_patient_id())

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

MODEL = "gemini-2.5-flash-lite"



def parse_tool(query):
    with open("system_prompts/side_agent_parser.md", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()

    # Define response schema for your side-agent output
    RESPONSE_SCHEMA = {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "User raw question or command."
            },
            "tool": {
                "type": "STRING",
                "enum": ["navigate_canvas", "generate_task", "get_easl_answer", "general" ,"send_notification","create_schedule", "generate_legal_report","generate_diagnosis", "generate_patient_report"],
                "description": "Tool category."
            }
        },
        "required": ["query", "tool"]
    }

    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_PROMPT,
    )

    prompt = f"User query : '{query}'\n\nPick tool for this query."
    
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            temperature=0.1,
        )
    )

    result = json.loads(response.text)
    print(f"Tool parsed: {result}")
    return result


async def resolve_object_id(query: str, context: str=""):
    with open("system_prompts/objectid_parser.md", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()

    patient_id = patient_manager.get_patient_id()
    url = BASE_URL + f"/api/board-items/{patient_id}"
    response = requests.get(url)
    data = response.json()

    # Handle new API format: {"patientId": "...", "items": [...]}
    if isinstance(data, dict) and 'items' in data:
        data = data['items']

    board_items = []
    for item in data:
        item_type = item.get('item_type', '')
        if item_type == 'content':
            item_content = item.get('content', {})
            board_items.append({
                "object_id": item.get('object_id'),
                "item_type": item_type,
                "title": item_content.get('title', ''),
                "component": item_content.get('component', ''),
                "description": item_content.get('description', ''),
            })
        else:
            board_items.append({
                "object_id": item.get('object_id'),
                "item_type": item_type,
                "title": item.get('title', ''),
                "description": item.get('description', ''),
            })

    # Define response schema for your side-agent output
    RESPONSE_SCHEMA = {
        "type": "OBJECT",
        "properties": {
            "objectId": {
                "type": "STRING",
                "description": "Resolved object ID."
            }
        },
        "required": ["objectId"]
    }

    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_PROMPT,
    )

    prompt = f"User query : '{query}'\n\nContext : {board_items}\n\n{context}"
    
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            temperature=0.1,
        )
    )

    result = json.loads(response.text)
    print(f"ObjectID Resolved: {result}")
    return result.get('objectId')


async def trigger_easl(question):
    print("Start EASL")
    with open("system_prompts/context_agent.md", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT_CONTEXT_GEN = f.read()

    with open("system_prompts/question_gen.md", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT_Q_GEN = f.read()

    ehr_data = await helper_model.load_ehr()
    
    print("Generate Context")
    prompt = f"""Please generate context for this : 
        Question : {question}


        This is raw data : {ehr_data}"""

    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_PROMPT_CONTEXT_GEN,
    )
    
    resp = model.generate_content(prompt)
    context_result = resp.text.replace("```markdown", " ").replace("```", "")
    with open(f"{config.output_dir}/context.md", "w", encoding="utf-8") as f:
        f.write(context_result)
    print("Context Generated")

    print("Generate Question")
    prompt = f"""Please generate proper question : 
        Question : {question}


        This is raw data : {ehr_data}"""

    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_PROMPT_Q_GEN,
    )
    
    resp = model.generate_content(prompt)
    q_gen_result = resp.text.replace("```markdown", " ").replace("```", "")
    with open(f"{config.output_dir}/question.md", "w", encoding="utf-8") as f:
        f.write(q_gen_result)
    print("Question Generated")

    patient_id = patient_manager.get_patient_id()
    url = BASE_URL + f"/api/board-items/{patient_id}"
    response = requests.get(url)
    data = response.json()

    # Handle new API format
    if isinstance(data, dict) and 'items' in data:
        data = data['items']

    board_items = []
    for item in data:
        item_type = item.get('item_type', '')
        if item_type == 'content':
            item_content = item.get('content', {})
            board_items.append({
                "object_id": item.get('object_id'),
                "item_type": item_type,
                "title": item_content.get('title', ''),
                "component": item_content.get('component', ''),
                "description": item_content.get('description', ''),
            })
        else:
            board_items.append({
                "object_id": item.get('object_id'),
                "item_type": item_type,
                "title": item.get('title', ''),
                "description": item.get('description', ''),
            })

    with open("system_prompts/objectid_parser.md", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()

    RESPONSE_SCHEMA = {
        "type": "OBJECT",
        "properties": {
            "objectId": {
                "type": "STRING",
                "description": "Resolved object ID."
            }
        },
        "required": ["objectId"]
    }

    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_PROMPT,
    )

    prompt = f"User query : 'Send to EASL.'\n\nContext : {board_items}\n\n"
    
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            temperature=0.1,
        )
    )

    result = json.loads(response.text)
    print(f"ObjectID Resolved: {result}")
    object_id = result.get('objectId')

    # Focus on the object first
    await canvas_ops.focus_item(object_id)
    
    # Send to EASL iframe with question
    full_question = f"Context: {context_result}\n\nQuestion: {q_gen_result}"
    result = await canvas_ops.initiate_easl_iframe(full_question)
    print("EASL Request sent successfully")
    return result


async def load_ehr():
    print("Start load_ehr")
    data = canvas_ops.get_board_items()
    with open(f"{config.output_dir}/ehr_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    return data

async def generate_response(todo_obj):
    with open("system_prompts/clinical_agent.md", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()
    
    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_PROMPT,
    )
    print(f"Running helper model")
    ehr_data = await load_ehr()
    prompt = f"""Please execute this todo : 
        {todo_obj}


        This is patient encounter data : {ehr_data}"""

    resp = model.generate_content(prompt)
    with open(f"{config.output_dir}/generate_response.md", "w", encoding="utf-8") as f:
        f.write(resp.text)

    print("Agent Result :", resp.text[:200])
    return {
        "answer": resp.text.replace("```markdown", " ").replace("```", "")
        }

async def generate_easl_diagnosis(ehr_data):
    with open("system_prompts/easl_diagnose.md", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()

    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_PROMPT,
    )
    print(f"Running easl diagnose model")
    
    prompt = f"""Please generate EASL diagnosis assessment.
        This is patient encounter data : {ehr_data}"""

    resp = model.generate_content(prompt)
    with open(f"{config.output_dir}/generate_easl_diagnosis.md", "w", encoding="utf-8") as f:
        f.write(resp.text)

    print("EASL Diagnosis Result :", resp.text[:200])
    
    try:
        result_json = json.loads(resp.text.replace("```json", "").replace("```", "").strip())
        with open(f"{config.output_dir}/generate_easl_diagnosis.json", "w", encoding="utf-8") as f:
            json.dump(result_json, f, indent=4)
        return result_json
    except:
        return {
            "answer": resp.text.replace("```markdown", " ").replace("```", "")
        }


def start_background_agent_processing(action_data, todo_obj):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_handle_agent_processing(action_data, todo_obj))

async def _handle_agent_processing(action_data, todo_obj):
    print("Start Background Agent Processing")
    print(f"Action Data: {action_data}")
    print(f"Todo Object: {todo_obj}")
    
    response_result = await generate_response(todo_obj)
    print(f"Response Result: {response_result}")
    
    patient_id = patient_manager.get_patient_id()
    url = BASE_URL + "/api/canvas-ops"
    payload = {
        "boardId": patient_id,
        "objectId": action_data.get('objectId'),
        "operation": "agent_answer",
        "agent_answer": response_result.get('answer')
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("Agent Answer sent successfully")
    except Exception as e:
        print(f"Error sending agent answer: {str(e)}")


async def generate_task_obj(query):
    with open("system_prompts/task_generator.md", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()

    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_PROMPT,
    )
    
    ehr_data = await load_ehr()
    prompt = f"""User request : {query}


        Patient data : {ehr_data}"""

    resp = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.7,
        )
    )

    result = json.loads(resp.text)
    with open(f"{config.output_dir}/generate_task_obj.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)

    print("Task Object Generated:", result)
    return result


async def generate_todo(query:str):
    with open("system_prompts/task_generator.md", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()

    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_PROMPT,
    )
    
    ehr_data = await load_ehr()
    prompt = f"""User request : {query}


        Patient data : {ehr_data}"""

    resp = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.7,
        )
    )

    result = json.loads(resp.text)
    with open(f"{config.output_dir}/generate_todo.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)

    print("TODO Generated:", result)
    
    # Use canvas_ops to create TODO
    response = await canvas_ops.create_todo(result)
    print("TODO created successfully")
    return response

async def generate_task_workflow(query: str):
    with open("system_prompts/task_generator.md", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()

    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_PROMPT,
    )
    
    ehr_data = await load_ehr()
    prompt = f"""User request : {query}


        Patient data : {ehr_data}"""

    resp = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.7,
        )
    )

    result = json.loads(resp.text)
    with open(f"{config.output_dir}/generate_task_workflow.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)

    print("Task Workflow Generated:", result)
    
    # Use canvas_ops to create TODO
    response = await canvas_ops.create_todo(result)
    print("Task workflow created successfully")
    return response

async def generate_dili_diagnosis():
    with open("system_prompts/dili_diagnosis_prompt.md", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()

    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_PROMPT,
    )
    
    ehr_data = await load_ehr()
    prompt = f"""Generate DILI diagnosis based on patient data.


        Patient data : {ehr_data}"""

    resp = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.7,
        )
    )

    result = json.loads(resp.text)
    with open(f"{config.output_dir}/generate_dili_diagnosis.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)

    print("DILI Diagnosis Generated")
    return result



async def generate_patient_report():
    with open("system_prompts/patient_report_prompt.md", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()

    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_PROMPT,
    )
    
    ehr_data = await load_ehr()
    prompt = f"""Generate patient report based on patient data.


        Patient data : {ehr_data}"""

    resp = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.7,
        )
    )

    result = json.loads(resp.text)
    with open(f"{config.output_dir}/generate_patient_report.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)

    print("Patient Report Generated")
    return result

async def create_dili_diagnosis():
    result = await generate_dili_diagnosis()
    # Use canvas_ops to create diagnosis
    canvas_ops.create_diagnosis(result)
    return result

async def create_patient_report():
    result = await generate_patient_report()
    # Use canvas_ops to create report
    await canvas_ops.create_report(result)
    return result



async def create_legal_doc():
    result = await generate_patient_report()
    # Use canvas_ops to create report (legal doc uses same API)
    await canvas_ops.create_report(result)
    return result
