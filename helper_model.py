import os
import google.generativeai as genai
import requests
import config
import httpx
import json
from dotenv import load_dotenv
from patient_manager import patient_manager
load_dotenv()




BASE_URL = patient_manager.get_base_url()

print("#### helper_model.py CANVAS_URL : ",BASE_URL)
print("#### Current Patient ID: ", patient_manager.get_patient_id())


genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
MODEL = "gemini-2.5-flash-lite"



with open("system_prompts/clinical_agent.md", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

with open("system_prompts/context_agent.md", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT_CONTEXT_GEN = f.read()

with open("system_prompts/question_gen.md", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT_Q_GEN = f.read()

async def load_ehr():
    print("Start load_ehr")
    patient_id = patient_manager.get_patient_id().lower()
    url = BASE_URL + f"/api/board-items/{patient_id}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        print(f"Status code: {response.status_code}")
        data = response.json()
        
        # Handle new API format: {"patientId": "...", "items": [...]}
        if isinstance(data, dict) and 'items' in data:
            data = data['items']
        
        return data

async def generate_response(todo_obj):
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

async def generate_context(question):
    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_PROMPT_CONTEXT_GEN,
    )
    print(f"Running Context Generation model")
    ehr_data = await load_ehr()
    prompt = f"""Please generate context for this : 
        Question : {question}


        This is raw data : {ehr_data}"""

    resp = model.generate_content(prompt)
    with open(f"{config.output_dir}/generate_context.md", "w", encoding="utf-8") as f:
        f.write(resp.text)
    return resp.text.replace("```markdown", " ").replace("```", "")
        

async def generate_question(question):
    model = genai.GenerativeModel(
        MODEL,
        system_instruction=SYSTEM_PROMPT_Q_GEN,
    )
    print(f"Running Context Generation model")
    ehr_data = await load_ehr()
    prompt = f"""Please generate proper question : 
        Question : {question}


        This is raw data : {ehr_data}"""

    resp = model.generate_content(prompt)
    with open(f"{config.output_dir}/generate_question.md", "w", encoding="utf-8") as f:
        f.write(resp.text)
    return resp.text.replace("```markdown", " ").replace("```", "")
