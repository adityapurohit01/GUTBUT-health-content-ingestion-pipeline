@echo off
echo Starting GutBut Health RAG Web UI...
start http://localhost:8000
.\venv\Scripts\python web_ui.py
pause

