from __future__ import annotations

import asyncio
import json
import uuid
import time
from typing import Any, AsyncIterator

from ..schemas import (
    ModelTier,
    NodeExecution,
    OrchestrationRun,
    TaskGraph,
    TaskNode,
    TaskStatus,
    TraceRole,
    WorkerResult,
    WorkerType,
    Artifact,
)
from ..telemetry.tracing import now_ms, trace_emit

# Define high-quality mock templates for different prompt keywords
MOCK_PROJECTS = {
    "todo": {
        "architecture": (
            "### Architecture Blueprint: Todo Application\n\n"
            "We are building a clean, modern Todo application featuring:\n"
            "1. **FastAPI Backend (`backend/app.py`)**: REST API to create, list, and delete todo tasks.\n"
            "2. **Frontend UI (`frontend/index.html`)**: Beautiful, responsive, OpenAI-style dashboard to interact with the backend.\n"
            "3. **Documentation (`README.md`)**: Complete setup, configuration, and API reference guidelines.\n\n"
            "Agent Workflow Routing:\n"
            "- Architect defines the contracts and schema.\n"
            "- Worker 1 creates the FastAPI backend. (We will simulate a verifier issue & correction here!)\n"
            "- Worker 2 creates the HTML/JS frontend interface.\n"
            "- Worker 3 generates the documentation.\n"
            "- Verifier reviews and passes the final consistency check."
        ),
        "files": [
            {
                "id": "node_backend",
                "title": "FastAPI Backend API",
                "filename": "backend/app.py",
                "worker_type": WorkerType.backend,
                "description": "FastAPI REST server managing todo database with GET/POST/DELETE endpoints.",
                "code_fail": (
                    "from fastapi import FastAPI, HTTPException\n"
                    "from pydantic import BaseModel\n\n"
                    "app = FastAPI(title='Todo API', version='1.0.0')\n\n"
                    "class Todo(BaseModel):\n"
                    "    id: int\n"
                    "    title: str\n"
                    "    completed: bool = False\n\n"
                    "todos_db = []\n\n"
                    "# DELIBERATE FAILURE FOR SIMULATION DEMO:\n"
                    "# The verifier will flag this function as not implemented (only has a pass statement)\n"
                    "@app.get('/todos')\n"
                    "async def get_todos():\n"
                    "    pass\n"
                ),
                "fail_issues": ["Function 'get_todos' has an empty body (only contains 'pass'). Implementation is missing."],
                "code_pass": (
                    "from fastapi import FastAPI, HTTPException\n"
                    "from pydantic import BaseModel\n"
                    "from typing import List\n\n"
                    "app = FastAPI(title='Todo API', version='1.0.0')\n\n"
                    "class Todo(BaseModel):\n"
                    "    id: int\n"
                    "    title: str\n"
                    "    completed: bool = False\n\n"
                    "todos_db: List[Todo] = [\n"
                    "    Todo(id=1, title='Learn CogniRoute agent patterns', completed=True),\n"
                    "    Todo(id=2, title='Deploy multi-service project to Vercel', completed=False),\n"
                    "    Todo(id=3, title='Build simulated portfolio demos', completed=False)\n"
                    "]\n\n"
                    "@app.get('/todos', response_model=List[Todo])\n"
                    "async def get_todos():\n"
                    "    return todos_db\n\n"
                    "@app.post('/todos', response_model=Todo)\n"
                    "async def add_todo(todo: Todo):\n"
                    "    todos_db.append(todo)\n"
                    "    return todo\n\n"
                    "@app.delete('/todos/{todo_id}')\n"
                    "async def delete_todo(todo_id: int):\n"
                    "    for idx, item in enumerate(todos_db):\n"
                    "        if item.id == todo_id:\n"
                    "            return todos_db.pop(idx)\n"
                    "    raise HTTPException(status_code=404, detail='Todo not found')\n"
                )
            },
            {
                "id": "node_frontend",
                "title": "Interactive Todo Frontend UI",
                "filename": "frontend/index.html",
                "worker_type": WorkerType.frontend,
                "description": "Vanilla CSS & JavaScript dashboard with glassmorphic style and real-time backend synchronization.",
                "code_pass": (
                    "<!DOCTYPE html>\n"
                    "<html lang='en'>\n"
                    "<head>\n"
                    "    <meta charset='UTF-8'>\n"
                    "    <title>Premium Todo App</title>\n"
                    "    <style>\n"
                    "        :root {\n"
                    "            --bg: #0a0a0a;\n"
                    "            --card-bg: rgba(255, 255, 255, 0.03);\n"
                    "            --accent: #10a37f;\n"
                    "            --border: rgba(255, 255, 255, 0.08);\n"
                    "            --text: #ececec;\n"
                    "        }\n"
                    "        body {\n"
                    "            background: var(--bg);\n"
                    "            color: var(--text);\n"
                    "            font-family: system-ui, sans-serif;\n"
                    "            display: flex;\n"
                    "            justify-content: center;\n"
                    "            align-items: center;\n"
                    "            height: 100vh;\n"
                    "            margin: 0;\n"
                    "        }\n"
                    "        .todo-card {\n"
                    "            background: var(--card-bg);\n"
                    "            border: 1px solid var(--border);\n"
                    "            padding: 24px;\n"
                    "            border-radius: 16px;\n"
                    "            width: 360px;\n"
                    "            backdrop-filter: blur(20px);\n"
                    "        }\n"
                    "        input {\n"
                    "            background: rgba(255, 255, 255, 0.05);\n"
                    "            border: 1px solid var(--border);\n"
                    "            color: white;\n"
                    "            padding: 8px 12px;\n"
                    "            border-radius: 8px;\n"
                    "            width: calc(100% - 26px);\n"
                    "        }\n"
                    "        button {\n"
                    "            background: var(--accent);\n"
                    "            color: white;\n"
                    "            border: none;\n"
                    "            padding: 8px 12px;\n"
                    "            border-radius: 8px;\n"
                    "            margin-top: 10px;\n"
                    "            cursor: pointer;\n"
                    "            width: 100%;\n"
                    "        }\n"
                    "    </style>\n"
                    "</head>\n"
                    "<body>\n"
                    "    <div class='todo-card'>\n"
                    "        <h2>Simulated Task Manager</h2>\n"
                    "        <input type='text' id='todoInput' placeholder='Enter new task...'>\n"
                    "        <button onclick='addTodo()'>Add Task</button>\n"
                    "        <ul id='todoList' style='margin-top: 15px; padding-left: 20px;'></ul>\n"
                    "    </div>\n"
                    "    <script>\n"
                    "        let db = [\n"
                    "            {id: 1, title: 'Learn CogniRoute agent patterns', completed: true},\n"
                    "            {id: 2, title: 'Deploy multi-service project to Vercel', completed: false}\n"
                    "        ];\n"
                    "        function render() {\n"
                    "            const ul = document.getElementById('todoList');\n"
                    "            ul.innerHTML = db.map(t => `<li style=\"margin-bottom: 8px;\">${t.title} ${t.completed ? '✅' : '⏳'}</li>`).join('');\n"
                    "        }\n"
                    "        function addTodo() {\n"
                    "            const input = document.getElementById('todoInput');\n"
                    "            if (!input.value.trim()) return;\n"
                    "            db.push({ id: Date.now(), title: input.value, completed: false });\n"
                    "            input.value = '';\n"
                    "            render();\n"
                    "        }\n"
                    "        render();\n"
                    "    </script>\n"
                    "</body>\n"
                    "</html>\n"
                )
            },
            {
                "id": "node_readme",
                "title": "Documentation",
                "filename": "README.md",
                "worker_type": WorkerType.file,
                "description": "Project guide outlining installation, FastAPI backend structure, and frontend execution.",
                "code_pass": (
                    "# Simulated Todo Application 🚀\n\n"
                    "This is a demonstration codebase generated automatically by the CogniRoute multi-agent framework.\n\n"
                    "## Setup Instructions\n\n"
                    "1. Install the backend dependencies:\n"
                    "```bash\n"
                    "pip install fastapi uvicorn pydantic\n"
                    "```\n\n"
                    "2. Run the FastAPI dev server:\n"
                    "```bash\n"
                    "uvicorn app:app --reload\n"
                    "```\n\n"
                    "3. Run the Frontend:\n"
                    "Simply open `frontend/index.html` in any browser to interact with the todo list.\n"
                    "The backend endpoint will automatically synchronize data in real-time.\n"
                )
            }
        ]
    },
    "weather": {
        "architecture": (
            "### Architecture Blueprint: Weather Forecast Dashboard\n\n"
            "We are building a responsive Weather application:\n"
            "1. **Weather API Backend (`backend/weather.py`)**: Fetches live data from public APIs or mock services.\n"
            "2. **Dashboard UI (`frontend/index.html`)**: Beautiful, high-end visualization showing hourly temperatures and weather icons.\n"
            "3. **Documentation (`README.md`)**: API specs and client deployment guide.\n\n"
            "Agent Routing Loop:\n"
            "- Architect blueprints the endpoints.\n"
            "- Worker 1 implements weather retrieval. (Will simulate a missing import retry loop!)\n"
            "- Worker 2 creates the beautiful dashboard.\n"
            "- Worker 3 produces instructions.\n"
            "- Verifier validates syntax and structure."
        ),
        "files": [
            {
                "id": "node_backend",
                "title": "Weather API Fetcher",
                "filename": "backend/weather.py",
                "worker_type": WorkerType.backend,
                "description": "FastAPI weather retrieval engine utilizing external open-meteo endpoints.",
                "code_fail": (
                    "from fastapi import FastAPI\n\n"
                    "app = FastAPI(title='Weather API')\n\n"
                    "@app.get('/weather')\n"
                    "async def get_weather():\n"
                    "    # DELIBERATE FAILURE FOR SIMULATION:\n"
                    "    # We are calling httpx.get() but we forgot to import httpx!\n"
                    "    res = await httpx.get('https://api.open-meteo.com/v1/forecast?latitude=38.9&longitude=-77.0&current_weather=true')\n"
                    "    return res.json()\n"
                ),
                "fail_issues": ["NameError: name 'httpx' is not defined. Missing import statement for 'httpx'."],
                "code_pass": (
                    "from fastapi import FastAPI\n"
                    "import httpx\n\n"
                    "app = FastAPI(title='Weather API', version='1.0.0')\n\n"
                    "@app.get('/weather')\n"
                    "async def get_weather(lat: float = 38.9, lon: float = -77.0):\n"
                    "    async with httpx.AsyncClient() as client:\n"
                    "        # Fetches DC weather by default\n"
                    "        res = await client.get(f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true')\n"
                    "        if res.status_code != 200:\n"
                    "            return {'temperature': 22.5, 'weathercode': 1, 'windspeed': 10.2, 'source': 'Mock Fallback'}\n"
                    "        return res.json().get('current_weather', {})\n"
                )
            },
            {
                "id": "node_frontend",
                "title": "Weather Dashboard UI",
                "filename": "frontend/index.html",
                "worker_type": WorkerType.frontend,
                "description": "Visual dashboard with dynamic widgets, matching temperature gradients, and localized forecasts.",
                "code_pass": (
                    "<!DOCTYPE html>\n"
                    "<html lang='en'>\n"
                    "<head>\n"
                    "    <title>Premium Weather Dashboard</title>\n"
                    "    <style>\n"
                    "        body {\n"
                    "            background: linear-gradient(135deg, #1e293b, #0f172a);\n"
                    "            color: white;\n"
                    "            font-family: system-ui, sans-serif;\n"
                    "            display: flex;\n"
                    "            justify-content: center;\n"
                    "            align-items: center;\n"
                    "            height: 100vh;\n"
                    "            margin: 0;\n"
                    "        }\n"
                    "        .weather-card {\n"
                    "            background: rgba(255, 255, 255, 0.05);\n"
                    "            border: 1px solid rgba(255, 255, 255, 0.1);\n"
                    "            border-radius: 20px;\n"
                    "            padding: 30px;\n"
                    "            text-align: center;\n"
                    "            box-shadow: 0 10px 30px rgba(0,0,0,0.5);\n"
                    "        }\n"
                    "        .temp { font-size: 4rem; font-weight: bold; margin: 15px 0; color: #f59e0b; }\n"
                    "    </style>\n"
                    "</head>\n"
                    "<body>\n"
                    "    <div class='weather-card'>\n"
                    "        <h2>Washington, D.C.</h2>\n"
                    "        <div class='temp'>72.5°F</div>\n"
                    "        <p style='color: #94a3b8;'>Partly Cloudy · Wind 10.2 mph</p>\n"
                    "    </div>\n"
                    "</body>\n"
                    "</html>\n"
                )
            },
            {
                "id": "node_readme",
                "title": "Documentation",
                "filename": "README.md",
                "worker_type": WorkerType.file,
                "description": "Developer setup documentation and configuration guide.",
                "code_pass": (
                    "# Weather Dashboard Backend\n\n"
                    "Generated automatically via CogniRoute.\n\n"
                    "## Setup\n"
                    "```bash\n"
                    "pip install fastapi httpx uvicorn\n"
                    "uvicorn weather:app --reload\n"
                    "```\n"
                )
            }
        ]
    },
    "chat": {
        "architecture": (
            "### Architecture Blueprint: OpenAI-Style Chat Interface\n\n"
            "We are building a real-time conversational chat application:\n"
            "1. **FastAPI Server (`backend/chat.py`)**: SSE server to stream bot replies.\n"
            "2. **Frontend UI (`frontend/index.html`)**: Beautiful chat bubble feed mimicking ChatGPT.\n"
            "3. **Documentation (`README.md`)**: Config guidelines.\n\n"
            "Agent Workflow:\n"
            "- Architect outlines stream routing.\n"
            "- Worker 1 writes the streaming backend. (Will simulate custom verifier retry!)\n"
            "- Worker 2 designs the chat interface.\n"
            "- Worker 3 generates documentation.\n"
            "- Verifier runs final verification checks."
        ),
        "files": [
            {
                "id": "node_backend",
                "title": "Streaming Chat Service",
                "filename": "backend/chat.py",
                "worker_type": WorkerType.backend,
                "description": "FastAPI SSE server returning mock LLM text completions streamed token-by-token.",
                "code_fail": (
                    "from fastapi import FastAPI\n"
                    "from fastapi.responses import StreamingResponse\n\n"
                    "app = FastAPI(title='Chat Service')\n\n"
                    "@app.post('/chat')\n"
                    "async def chat():\n"
                    "    # DELIBERATE FAILURE FOR SIMULATION:\n"
                    "    # We are returning raw text but client expects an SSE event-stream generator\n"
                    "    return 'Hello, I am CogniRoute bot. How can I help you?'\n"
                ),
                "fail_issues": ["Response mismatch: Expected SSE text/event-stream response structure, but endpoint returns raw string."],
                "code_pass": (
                    "from fastapi import FastAPI\n"
                    "from fastapi.responses import StreamingResponse\n"
                    "from fastapi.middleware.cors import CORSMiddleware\n"
                    "import asyncio\n"
                    "import json\n\n"
                    "app = FastAPI(title='Chat Service', version='1.0.0')\n"
                    "app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'])\n\n"
                    "async def reply_generator(prompt: str):\n"
                    "    tokens = f'This is a simulated token-by-token response for: \"{prompt}\"'.split(' ')\n"
                    "    for token in tokens:\n"
                    "        yield f'data: {json.dumps({\"token\": token + \" \"})}\\n\\n'\n"
                    "        await asyncio.sleep(0.15)\n\n"
                    "@app.post('/chat')\n"
                    "async def chat(data: dict):\n"
                    "    prompt = data.get('prompt', '')\n"
                    "    return StreamingResponse(reply_generator(prompt), media_type='text/event-stream')\n"
                )
            },
            {
                "id": "node_frontend",
                "title": "Chat Frontend Dashboard",
                "filename": "frontend/index.html",
                "worker_type": WorkerType.frontend,
                "description": "OpenAI-style high-fidelity chat layout with animated messages and custom scrollbars.",
                "code_pass": (
                    "<!DOCTYPE html>\n"
                    "<html lang='en'>\n"
                    "<head>\n"
                    "    <title>Premium Chat UI</title>\n"
                    "    <style>\n"
                    "        body { background: #0a0a0a; color: #ececec; font-family: sans-serif; margin: 0; padding: 20px; }\n"
                    "        .chat-container { max-width: 600px; margin: 0 auto; display: flex; flex-col: column; gap: 15px; }\n"
                    "        .bubble { padding: 12px 16px; border-radius: 12px; max-width: 80%; line-height: 1.5; }\n"
                    "        .user { background: #2f2f2f; align-self: flex-end; margin-left: auto; }\n"
                    "        .assistant { background: #10a37f; color: white; }\n"
                    "    </style>\n"
                    "</head>\n"
                    "<body>\n"
                    "    <div class='chat-container'>\n"
                    "        <div class='bubble user'>Build a streaming chat bot.</div>\n"
                    "        <div class='bubble assistant'>Sure, here is the setup...</div>\n"
                    "    </div>\n"
                    "</body>\n"
                    "</html>\n"
                )
            },
            {
                "id": "node_readme",
                "title": "Documentation",
                "filename": "README.md",
                "worker_type": WorkerType.file,
                "description": "Installation requirements and configuration guide.",
                "code_pass": (
                    "# Chat Service Demo\n\n"
                    "Multi-agent output from CogniRoute.\n\n"
                    "## Setup\n"
                    "```bash\n"
                    "pip install fastapi uvicorn\n"
                    "uvicorn chat:app --reload --port 8000\n"
                    "```\n"
                )
            }
        ]
    },
    "generic": {
        "architecture": (
            "### Architecture Blueprint: CogniRoute Microservice\n\n"
            "We are building a robust microservice foundation:\n"
            "1. **Main Server Service (`backend/main.py`)**: Root FastAPI controller with health checks.\n"
            "2. **Landing Page (`frontend/index.html`)**: Beautiful glassmorphic showcase representing the product.\n"
            "3. **Documentation (`README.md`)**: Complete repository guide.\n\n"
            "Agent Plan:\n"
            "- Architect creates the folder layout.\n"
            "- Worker 1 implements backend endpoints. (Will simulate syntax repair retry!)\n"
            "- Worker 2 designs the layout.\n"
            "- Worker 3 writes instructions.\n"
            "- Verifier reviews logic correctness."
        ),
        "files": [
            {
                "id": "node_backend",
                "title": "FastAPI Server Core",
                "filename": "backend/main.py",
                "worker_type": WorkerType.backend,
                "description": "Microservice with route prefix mappings, CORS filters, and custom log handlers.",
                "code_fail": (
                    "from fastapi import FastAPI\n\n"
                    "app = FastAPI(title='Core Server')\n\n"
                    "# DELIBERATE SYNTAX ERROR FOR SIMULATION:\n"
                    "def get_status()\n"
                    "    return {'status': 'active'}\n"
                ),
                "fail_issues": ["SyntaxError: expected ':' at line 6 (def get_status() missing colon)."],
                "code_pass": (
                    "from fastapi import FastAPI\n"
                    "from fastapi.middleware.cors import CORSMiddleware\n\n"
                    "app = FastAPI(title='Core Server', version='1.0.0')\n\n"
                    "app.add_middleware(\n"
                    "    CORSMiddleware,\n"
                    "    allow_origins=['*'],\n"
                    "    allow_methods=['*'],\n"
                    "    allow_headers=['*']\n"
                    ")\n\n"
                    "@app.get('/')\n"
                    "async def get_status():\n"
                    "    return {'status': 'active', 'framework': 'FastAPI'}\n"
                )
            },
            {
                "id": "node_frontend",
                "title": "Landing Page UI",
                "filename": "frontend/index.html",
                "worker_type": WorkerType.frontend,
                "description": "Modern landing page with sleek animations, glassmorphic layout, and dynamic CTA actions.",
                "code_pass": (
                    "<!DOCTYPE html>\n"
                    "<html lang='en'>\n"
                    "<head>\n"
                    "    <title>Sleek Landing Page</title>\n"
                    "    <style>\n"
                    "        body { background: #070708; color: #f3f4f6; font-family: system-ui, sans-serif; text-align: center; padding: 100px 20px; }\n"
                    "        h1 { font-size: 3rem; background: linear-gradient(to right, #10a37f, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }\n"
                    "        p { color: #9ca3af; max-width: 500px; margin: 20px auto; line-height: 1.6; }\n"
                    "        .cta { background: #10a37f; color: white; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; }\n"
                    "    </style>\n"
                    "</head>\n"
                    "<body>\n"
                    "    <h1>Future of Multi-Agent Systems</h1>\n"
                    "    <p>Empowering developers to create completely self-healing multi-agent codebases in seconds using advanced LLM routing logic.</p>\n"
                    "    <a href='#' class='cta'>Get Started Free</a>\n"
                    "</body>\n"
                    "</html>\n"
                )
            },
            {
                "id": "node_readme",
                "title": "Documentation",
                "filename": "README.md",
                "worker_type": WorkerType.file,
                "description": "General repo layout and deployment guide.",
                "code_pass": (
                    "# CogniRoute Showcase Repository\n\n"
                    "This represents the microservice codebase.\n\n"
                    "## Setup\n"
                    "```bash\n"
                    "pip install fastapi uvicorn\n"
                    "uvicorn main:app --reload\n"
                    "```\n"
                )
            }
        ]
    }
}


def _select_mock_project(prompt: str) -> dict:
    prompt_lower = prompt.lower()
    if "todo" in prompt_lower or "task" in prompt_lower:
        return MOCK_PROJECTS["todo"]
    elif "weather" in prompt_lower or "temp" in prompt_lower:
        return MOCK_PROJECTS["weather"]
    elif "chat" in prompt_lower or "bot" in prompt_lower or "ai" in prompt_lower:
        return MOCK_PROJECTS["chat"]
    else:
        return MOCK_PROJECTS["generic"]


async def run_generate_stream_simulation(prompt: str) -> AsyncIterator[str]:
    """
    Streams a highly realistic multi-agent code generation simulation.
    Includes Architect planning, Code Workers, Verifier failures/retries (self-healing),
    and final cross-file checks.
    """
    project = _select_mock_project(prompt)
    graph_id = f"graph_{uuid.uuid4().hex[:8]}"

    # Event helper
    def fmt(evt: dict) -> str:
        return f"data: {json.dumps(evt)}\n\n"

    # Step 1: Architect analysis
    yield fmt({"type": "status", "message": "Architect is analyzing the project..."})
    await asyncio.sleep(1.8)

    yield fmt({"type": "reasoning", "content": project["architecture"]})
    await asyncio.sleep(1.0)

    # Yield Plan
    plan_files = []
    for f in project["files"]:
        plan_files.append({
            "node_id": f["id"],
            "title": f["title"],
            "filename": f["filename"],
            "worker_type": f["worker_type"].value,
            "status": "pending"
        })
    yield fmt({
        "type": "plan",
        "graph_id": graph_id,
        "files": plan_files
    })
    await asyncio.sleep(0.8)

    # Step 2: Loop files and simulate generation
    for f_idx, file_node in enumerate(project["files"]):
        node_id = file_node["id"]
        filename = file_node["filename"]
        title = file_node["title"]

        yield fmt({
            "type": "file_start",
            "node_id": node_id,
            "filename": filename,
            "title": title
        })
        await asyncio.sleep(0.5)

        # If it's the backend node, we simulate a FAIL then RETRY to demonstrate self-healing!
        if "code_fail" in file_node:
            # Attempt 1: Start
            yield fmt({
                "type": "worker_start",
                "node_id": node_id,
                "attempt": 1,
                "message": "Worker generating code..."
            })
            # Stream/Write code chunks
            await asyncio.sleep(1.5)
            yield fmt({
                "type": "file_generated",
                "node_id": node_id,
                "filename": filename,
                "content": file_node["code_fail"],
                "attempt": 1
            })
            await asyncio.sleep(0.5)

            # Verifier Check
            yield fmt({
                "type": "verify_start",
                "node_id": node_id,
                "filename": filename,
                "message": "Verifier checking code quality..."
            })
            await asyncio.sleep(1.2)
            yield fmt({
                "type": "file_verified",
                "node_id": node_id,
                "filename": filename,
                "status": "FAIL",
                "issues": file_node["fail_issues"]
            })
            await asyncio.sleep(1.0)

            # Propose Retry
            yield fmt({
                "type": "file_retry",
                "node_id": node_id,
                "attempt": 2,
                "issues": file_node["fail_issues"]
            })
            await asyncio.sleep(0.8)

            # Attempt 2: Fixed Code
            yield fmt({
                "type": "worker_start",
                "node_id": node_id,
                "attempt": 2,
                "message": "Worker self-healing code (attempt 2)..."
            })
            await asyncio.sleep(1.5)
            yield fmt({
                "type": "file_generated",
                "node_id": node_id,
                "filename": filename,
                "content": file_node["code_pass"],
                "attempt": 2
            })
            await asyncio.sleep(0.5)

            # Verifier Check 2
            yield fmt({
                "type": "verify_start",
                "node_id": node_id,
                "filename": filename,
                "message": "Verifier re-checking code..."
            })
            await asyncio.sleep(1.0)
            yield fmt({
                "type": "file_verified",
                "node_id": node_id,
                "filename": filename,
                "status": "PASS"
            })
            await asyncio.sleep(0.5)

        else:
            # Standard single PASS flow
            yield fmt({
                "type": "worker_start",
                "node_id": node_id,
                "attempt": 1,
                "message": "Worker generating code..."
            })
            await asyncio.sleep(1.5)
            yield fmt({
                "type": "file_generated",
                "node_id": node_id,
                "filename": filename,
                "content": file_node["code_pass"],
                "attempt": 1
            })
            await asyncio.sleep(0.5)

            # Verify
            yield fmt({
                "type": "verify_start",
                "node_id": node_id,
                "filename": filename,
                "message": "Verifier checking code quality..."
            })
            await asyncio.sleep(1.0)
            yield fmt({
                "type": "file_verified",
                "node_id": node_id,
                "filename": filename,
                "status": "PASS"
            })
            await asyncio.sleep(0.5)

    # Step 3: Final verification
    yield fmt({"type": "status", "message": "Running final verification..."})
    await asyncio.sleep(1.5)

    # Generate full mock final result response
    nodes = []
    execution = {}
    total_latency = 7200 # simulated

    # Add Architect node to graph
    nodes.append(TaskNode(
        id="node_architect",
        title="Architect planner",
        description="Creates plans",
        worker_type=WorkerType.verifier, # dummy
        model_tier=ModelTier.architect,
    ))

    # Add file task nodes
    for f in project["files"]:
        nodes.append(TaskNode(
            id=f["id"],
            title=f["title"],
            description=f["description"],
            worker_type=f["worker_type"],
            model_tier=ModelTier.worker,
        ))
        execution[f["id"]] = NodeExecution(
            node_id=f["id"],
            status=TaskStatus.succeeded,
            started_at_ms=now_ms() - total_latency,
            ended_at_ms=now_ms(),
            artifacts={"filename": f["filename"], "content": f["code_pass"]}
        )

    # Add final verifier node
    nodes.append(TaskNode(
        id="node_final_verifier",
        title="Consistency verifier",
        description="Runs final verification",
        worker_type=WorkerType.verifier,
        model_tier=ModelTier.verifier,
    ))
    execution["node_final_verifier"] = NodeExecution(
        node_id="node_final_verifier",
        status=TaskStatus.succeeded,
        started_at_ms=now_ms() - 1000,
        ended_at_ms=now_ms(),
        artifacts={"verifier_report": {"status": "PASS", "issues": []}}
    )

    task_graph = TaskGraph(
        graph_id=graph_id,
        user_goal=prompt,
        nodes=nodes
    )

    result = OrchestrationRun(
        run_id=f"run_{uuid.uuid4().hex[:8]}",
        prompt=prompt,
        plan=task_graph,
        execution=execution,
        spans=[],
        trace=[],
        routing_log=[],
        verifier_report={"status": "PASS", "issues": []},
        plan_markdown="# Mock Plan\nSimulated output.",
        contracts_markdown="# Mock Contracts\nSimulated output."
    )

    yield fmt({
        "type": "complete",
        "run": json.loads(result.model_dump_json())
    })


async def run_generate_simulation(prompt: str) -> OrchestrationRun:
    """
    Synchronous simulation call. Fast-forwards events and returns the resulting OrchestrationRun object.
    """
    project = _select_mock_project(prompt)
    graph_id = f"graph_{uuid.uuid4().hex[:8]}"

    nodes = []
    execution = {}

    nodes.append(TaskNode(
        id="node_architect",
        title="Architect planner",
        description="Creates plans",
        worker_type=WorkerType.verifier,
        model_tier=ModelTier.architect,
    ))

    for f in project["files"]:
        nodes.append(TaskNode(
            id=f["id"],
            title=f["title"],
            description=f["description"],
            worker_type=f["worker_type"],
            model_tier=ModelTier.worker,
        ))
        execution[f["id"]] = NodeExecution(
            node_id=f["id"],
            status=TaskStatus.succeeded,
            started_at_ms=now_ms() - 2000,
            ended_at_ms=now_ms(),
            artifacts={"filename": f["filename"], "content": f["code_pass"]}
        )

    nodes.append(TaskNode(
        id="node_final_verifier",
        title="Consistency verifier",
        description="Runs final verification",
        worker_type=WorkerType.verifier,
        model_tier=ModelTier.verifier,
    ))
    execution["node_final_verifier"] = NodeExecution(
        node_id="node_final_verifier",
        status=TaskStatus.succeeded,
        started_at_ms=now_ms() - 100,
        ended_at_ms=now_ms(),
        artifacts={"verifier_report": {"status": "PASS", "issues": []}}
    )

    task_graph = TaskGraph(
        graph_id=graph_id,
        user_goal=prompt,
        nodes=nodes
    )

    return OrchestrationRun(
        run_id=f"run_{uuid.uuid4().hex[:8]}",
        prompt=prompt,
        plan=task_graph,
        execution=execution,
        spans=[],
        trace=[],
        routing_log=[],
        verifier_report={"status": "PASS", "issues": []},
        plan_markdown="# Mock Plan\nSimulated output.",
        contracts_markdown="# Mock Contracts\nSimulated output."
    )
