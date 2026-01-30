# MedForce Agent - Server Startup Script
# Installs dependencies and starts the enhanced agent-2.9 server

Write-Host "🏥 MedForce Agent - Starting Enhanced Server (agent-2.9 architecture)" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "Checking Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
Write-Host "  ✓ $pythonVersion" -ForegroundColor Green

# Install/upgrade dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
Write-Host "  • FAISS (vector search)" -ForegroundColor Gray
Write-Host "  • LangChain (RAG framework)" -ForegroundColor Gray
Write-Host "  • scikit-learn (embeddings)" -ForegroundColor Gray
Write-Host ""

pip install -q -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Dependencies installed successfully" -ForegroundColor Green
} else {
    Write-Host "  ✗ Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Create vector cache directory
Write-Host ""
Write-Host "Setting up vector cache..." -ForegroundColor Yellow
if (!(Test-Path "vector_cache")) {
    New-Item -ItemType Directory -Path "vector_cache" | Out-Null
    Write-Host "  ✓ Created vector_cache directory" -ForegroundColor Green
} else {
    Write-Host "  ✓ vector_cache directory exists" -ForegroundColor Green
}

# Start server
Write-Host ""
Write-Host "🚀 Starting server on http://localhost:8080" -ForegroundColor Cyan
Write-Host ""
Write-Host "Features available:" -ForegroundColor Yellow
Write-Host "  • FAISS RAG - Semantic search over patient data" -ForegroundColor Gray
Write-Host "  • Tool Orchestration - Navigate, create tasks, schedules" -ForegroundColor Gray
Write-Host "  • EASL Integration - Medical guideline queries" -ForegroundColor Gray
Write-Host "  • Report Generation - DILI, patient, legal reports" -ForegroundColor Gray
Write-Host "  • Canvas Tools - Board manipulation (focus, create, navigate)" -ForegroundColor Gray
Write-Host ""
Write-Host "Test UI: http://localhost:8080/ui/integrated-test.html" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host ""

# Run server
python -m uvicorn server:app --host 0.0.0.0 --port 8080 --reload
