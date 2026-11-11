# Starts the FastAPI Backend (port 8000) and Vite React UI (port 5173)
Write-Host "Starting Harmonika Werkbank API on http://127.0.0.1:8000 ..."
Start-Process -NoNewWindow -FilePath ".\.venv-torch\Scripts\python.exe" -ArgumentList "-m uvicorn harmonica_pipeline.api:app --host 127.0.0.1 --port 8000"
Write-Host "Starting React Frontend on http://localhost:5173 ..."
Set-Location web
npm run dev
