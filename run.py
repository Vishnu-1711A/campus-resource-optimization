"""
Campus Resource Optimization System - Launcher Script
Starts the web server and automatically opens the dashboard in the default browser.
"""

import sys
import webbrowser
import threading
import time
import uvicorn

def open_browser():
    time.sleep(1.5)
    print("\n>>> Opening Campus Resource Optimization System Dashboard in your browser: http://127.0.0.1:8000\n")
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
