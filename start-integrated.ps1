# MedForce Agent - Complete Startup Script
# Integrates Agent-2.9 architecture with Chat & Voice capabilities

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  MedForce Agent - Integrated System Startup" -ForegroundColor Cyan
Write-Host "  Agent-2.9 + Chat + Voice + Canvas Operations" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "Checking Python version..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Python is not installed or not in PATH!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ $pythonVersion" -ForegroundColor Green
Write-Host ""

# Check for .env file
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  No .env file found! Creating template..." -ForegroundColor Yellow
    @"
# API Keys
GOOGLE_API_KEY=your_google_api_key_here

# Patient Configuration
DEFAULT_PATIENT_ID=p0001

# Canvas Board URL
CANVAS_URL=https://iso-clinic-v3.vercel.app

# Vertex AI Configuration (for Gemini Live voice)
PROJECT_ID=medforce-pilot-backend

# Server Configuration
PORT=8080
"@ | Out-File -FilePath ".env" -Encoding UTF8
    Write-Host "✅ Created .env template. Please fill in your API keys!" -ForegroundColor Green
    Write-Host ""
}

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install dependencies!" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Dependencies installed" -ForegroundColor Green
Write-Host ""

# Create required directories
Write-Host "Creating required directories..." -ForegroundColor Yellow
$directories = @("output", "vector_cache", "ui")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  ✅ Created $dir/" -ForegroundColor Green
    } else {
        Write-Host "  ✓ $dir/ exists" -ForegroundColor Gray
    }
}
Write-Host ""

# System Architecture Info
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  SYSTEM ARCHITECTURE" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "📦 Core Modules:" -ForegroundColor Yellow
Write-Host "  • patient_manager.py    - Patient ID management (singleton)" -ForegroundColor White
Write-Host "  • canvas_ops.py          - Canvas API operations" -ForegroundColor White
Write-Host "  • side_agent.py          - Tool orchestration (11+ functions)" -ForegroundColor White
Write-Host "  • helper_model.py        - Clinical generation" -ForegroundColor White
Write-Host "  • chat_model.py          - Chat orchestration" -ForegroundColor White
Write-Host "  • chat_agent.py          - Full-featured chat agent" -ForegroundColor White
Write-Host "  • websocket_agent.py     - Real-time chat WebSocket" -ForegroundColor White
Write-Host "  • voice_websocket_handler.py - Gemini Live voice" -ForegroundColor White
Write-Host "  • rag.py                 - FAISS vector retrieval" -ForegroundColor White
Write-Host ""

Write-Host "🎯 Available Operations:" -ForegroundColor Yellow
Write-Host "  • Parse tool intent (side_agent_parser.md)" -ForegroundColor White
Write-Host "  • Resolve object IDs (objectid_parser.md)" -ForegroundColor White
Write-Host "  • EASL integration (trigger_easl)" -ForegroundColor White
Write-Host "  • Task generation (task_generator.md)" -ForegroundColor White
Write-Host "  • DILI diagnosis (dili_diagnosis_prompt.md)" -ForegroundColor White
Write-Host "  • Patient reports (patient_report_prompt.md)" -ForegroundColor White
Write-Host "  • Clinical responses (clinical_agent.md)" -ForegroundColor White
Write-Host "  • Context generation (context_agent.md)" -ForegroundColor White
Write-Host "  • Question expansion (question_gen.md)" -ForegroundColor White
Write-Host "  • Schedule creation" -ForegroundColor White
Write-Host "  • Notifications" -ForegroundColor White
Write-Host ""

Write-Host "🌐 API Endpoints:" -ForegroundColor Yellow
Write-Host "  Chat & Agent:" -ForegroundColor Cyan
Write-Host "    POST   /send-chat               - Agent-2.9 chat endpoint" -ForegroundColor White
Write-Host "    POST   /chat                    - Full-featured chat" -ForegroundColor White
Write-Host "    GET    /chat/{patient_id}       - Chat history" -ForegroundColor White
Write-Host "    POST   /chat/{patient_id}/reset - Clear history" -ForegroundColor White
Write-Host ""
Write-Host "  Canvas Operations:" -ForegroundColor Cyan
Write-Host "    POST   /generate_diagnosis      - Generate DILI diagnosis" -ForegroundColor White
Write-Host "    POST   /generate_report         - Generate patient report" -ForegroundColor White
Write-Host "    POST   /generate_legal          - Generate legal report" -ForegroundColor White
Write-Host ""
Write-Host "  Patient Management:" -ForegroundColor Cyan
Write-Host "    GET    /patient/current         - Get current patient" -ForegroundColor White
Write-Host "    POST   /patient/switch          - Switch patient" -ForegroundColor White
Write-Host ""
Write-Host "  WebSocket (Real-time):" -ForegroundColor Cyan
Write-Host "    WS     /ws/chat/{patient_id}    - Real-time chat" -ForegroundColor White
Write-Host "    WS     /ws/voice/{patient_id}   - Voice with Gemini Live" -ForegroundColor White
Write-Host "    WS     /ws/pre-consult/{id}     - Pre-consultation" -ForegroundColor White
Write-Host ""
Write-Host "  UI:" -ForegroundColor Cyan
Write-Host "    GET    /ui/{file_path}          - Serve UI files" -ForegroundColor White
Write-Host ""

Write-Host "🎨 Available Test UIs:" -ForegroundColor Yellow
Write-Host "  • /ui/integrated-test-agent.html  - Chat + Voice integrated UI" -ForegroundColor White
Write-Host "  • /ui/test-agent-2.9.html         - Agent-2.9 chat test UI" -ForegroundColor White
Write-Host "  • /ui/chat-voice.html             - Original voice UI" -ForegroundColor White
Write-Host ""

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  STARTING SERVER" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Starting uvicorn server on port 8080..." -ForegroundColor Yellow
Write-Host ""
Write-Host "📱 Access the system at:" -ForegroundColor Green
Write-Host "   Main UI:     http://localhost:8080/ui/integrated-test-agent.html" -ForegroundColor Cyan
Write-Host "   Agent-2.9:   http://localhost:8080/ui/test-agent-2.9.html" -ForegroundColor Cyan
Write-Host "   Board:       https://iso-clinic-v3.vercel.app/board/p0001" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host ""

# Start the server
python -m uvicorn server:app --host 0.0.0.0 --port 8080 --reload
