# Agent-2.9 Server Startup Script

Write-Host "�� Agent-2.9 Architecture - Starting Server" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "Checking Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
Write-Host "  � $pythonVersion" -ForegroundColor Green

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -q -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "  � Dependencies installed successfully" -ForegroundColor Green
} else {
    Write-Host "  � Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Create output directory
Write-Host ""
Write-Host "Setting up output directory..." -ForegroundColor Yellow
if (!(Test-Path "output")) {
    New-Item -ItemType Directory -Path "output" | Out-Null
    Write-Host "  � Created output directory" -ForegroundColor Green
} else {
    Write-Host "  � output directory exists" -ForegroundColor Green
}

# Create vector cache directory
if (!(Test-Path "vector_cache")) {
    New-Item -ItemType Directory -Path "vector_cache" | Out-Null
    Write-Host "  � Created vector_cache directory" -ForegroundColor Green
} else {
    Write-Host "  � vector_cache directory exists" -ForegroundColor Green
}

# Start server
Write-Host ""
Write-Host "� Starting Agent-2.9 server on http://localhost:8080" -ForegroundColor Cyan
Write-Host ""
Write-Host "Agent-2.9 Features:" -ForegroundColor Yellow
Write-Host "  • FAISS RAG - Semantic search over patient data" -ForegroundColor Gray
Write-Host "  • Tool Parser - Routes to 11+ tool operations" -ForegroundColor Gray
Write-Host "  • Side Agent - EASL, tasks, reports orchestration" -ForegroundColor Gray
Write-Host "  • Helper Model - Clinical generation with system prompts" -ForegroundColor Gray
Write-Host "  • Patient Manager - Dynamic patient ID handling" -ForegroundColor Gray
Write-Host ""
Write-Host "Endpoints:" -ForegroundColor Yellow
Write-Host "  POST /send-chat - Main chat endpoint" -ForegroundColor Gray
Write-Host "  POST /generate_diagnosis - DILI diagnosis" -ForegroundColor Gray
Write-Host "  POST /generate_report - Patient report" -ForegroundColor Gray
Write-Host "  POST /generate_legal - Legal report" -ForegroundColor Gray
Write-Host "  GET  /patient/current - Current patient ID" -ForegroundColor Gray
Write-Host "  POST /patient/switch - Switch patient" -ForegroundColor Gray
Write-Host ""
Write-Host "Test UI: http://localhost:8080/ui/test-agent-2.9.html" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host ""

# Run server
python -m uvicorn server:app --host 0.0.0.0 --port 8080 --reload
