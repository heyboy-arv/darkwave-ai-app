# main.py - The heart of the Darkwave AI Web Application

import requests
import json
import os
import zipfile
import shutil
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# --- Configuration ---
# Make sure to replace this with your actual Groq API key
import os
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")       
PROJECTS_DIR = "generated_projects" 

# --- FastAPI App Initialization ---
app = FastAPI()
# Mount the 'static' directory to serve our HTML, CSS, JS files
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Helper Functions (Our Tools) ---

def write_file_tool(filename, content):
    """A tool that can write content to a file."""
    try:
        full_path = os.path.normpath(filename)
        directory = os.path.dirname(full_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Success: The file '{full_path}' was written."
    except Exception as e:
        return f"Error writing {filename}: {e}"

def create_lesson(user_prompt):
    """Creates the lesson for the AI, teaching it the JSON format."""
    return [
        {"role": "system", "content": "You are Darkwave AI, an expert software architect. You must always respond with a single, valid JSON object containing a 'thought' and a list of 'actions'. The only tool available is 'write_file_tool'."},
        {"role": "user", "content": "build a simple html page with a blue background"},
        {"role": "assistant", "content": """{"thought": "Okay, this requires two files: an HTML file for the content and a CSS file for the blue background. I will create both.","actions": [{"tool_to_use": "write_file_tool","parameters": {"filename": "project_1/index.html","content": "<!DOCTYPE html><html><head><link rel='stylesheet' href='style.css'></head><body><h1>My Website</h1></body></html>"}},{"tool_to_use": "write_file_tool","parameters": {"filename": "project_1/style.css","content": "body { background-color: blue; }"}}]}"""},
        {"role": "user", "content": user_prompt}
    ]

# --- API Endpoints (The Server's Doors) ---

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serves the main HTML page when a user visits the website."""
    with open("static/index.html") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.post("/build", response_class=HTMLResponse)
async def handle_build_request(prompt: str = Form(...)):
    """Receives the user's prompt, talks to the AI, builds the project, and returns a download link."""
    
    # --- 1. Talk to the AI ---
    messages_to_send = create_lesson(prompt)
    data = {
        "messages": messages_to_send, "model": "llama3-8b-8192",
        "temperature": 0.3, "max_tokens": 2048, "top_p": 1, "stream": False,
        "response_format": {"type": "json_object"}
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data )
        response.raise_for_status()
        response_json = response.json()
        ai_message_str = response_json['choices'][0]['message']['content']
        action_plan = json.loads(ai_message_str)
    except Exception as e:
        return f"<p class='error'>Error talking to AI: {e}</p>"

    # --- 2. Execute the AI's Plan ---
    actions_list = action_plan.get("actions")
    project_files = []
    if isinstance(actions_list, list):
        for action in actions_list:
            if action.get("tool_to_use") == "write_file_tool":
                params = action.get("parameters", {})
                filename = params.get("filename")
                content = params.get("content")
                if filename and content:
                    # We'll save all projects in a dedicated directory
                    project_path = os.path.join(PROJECTS_DIR, filename)
                    write_file_tool(project_path, content)
                    project_files.append(project_path)
    
    if not project_files:
        return "<p class='error'>The AI did not generate any files for this request.</p>"

    # --- 3. Zip the Project Files ---
    project_name = os.path.basename(os.path.dirname(project_files[0]))
    zip_path = os.path.join(PROJECTS_DIR, f"{project_name}.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file in project_files:
            # arcname makes sure the zip file doesn't have the full directory structure
            arcname = os.path.relpath(file, os.path.dirname(os.path.dirname(file)))
            zipf.write(file, arcname=arcname)

    # --- 4. Return a Download Link ---
    download_url = f"/download/{project_name}.zip"
    return f"""
        <div class='result'>
            <p>✅ Project '{project_name}' built successfully!</p>
            <a href='{download_url}' class='download-button'>Download Project (.zip)</a>
        </div>
    """

@app.get("/download/{zip_name}")
async def download_zip(zip_name: str):
    """Allows the user to download the generated zip file."""
    file_path = os.path.join(PROJECTS_DIR, zip_name)
    if os.path.exists(file_path):
        return FileResponse(path=file_path, media_type='application/zip', filename=zip_name)
    return HTMLResponse(content="File not found.", status_code=404)

