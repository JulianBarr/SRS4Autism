#!/usr/bin/env python3
"""
Run script for SRS4Autism backend
"""
import uvicorn
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Resolve paths relative to this file
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

# Add project root to Python path so agentic module can be found
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables from backend/gemini.env (same directory as this script)
env_path = BASE_DIR / 'gemini.env'
load_dotenv(env_path)

# Check if GEMINI_API_KEY is set
gemini_key = os.getenv('GEMINI_API_KEY')
if not gemini_key or gemini_key == 'your_actual_gemini_api_key_here':
    print("⚠️  WARNING: GEMINI_API_KEY not set or using placeholder value!")
    print("   Please set your actual Gemini API key in backend/gemini.env")
    print("   Get your API key from: https://aistudio.google.com/app/apikey")
    print("   Image generation will be disabled without this key.")
else:
    print(f"✅ GEMINI_API_KEY loaded: {gemini_key[:10]}...")
    print("✅ Image generation enabled with Gemini 2.5 Pro")

if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 8000))
    
    # Log file path
    log_dir = PROJECT_ROOT / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "backend.log"
    
    print(f"Starting Curious Mario API server on {host}:{port}")
    print(f"📝 Backend logs will be written to: {log_file}")
    print("Make sure to set GEMINI_API_KEY in your .env file for AI features")
    
    # Redirect stdout and stderr to log file
    import sys
    from datetime import datetime
    
    class TeeOutput:
        """Write to both file and stdout"""
        def __init__(self, file, stream):
            self.file = file
            self.stream = stream
        
        def write(self, text):
            self.file.write(text)
            self.file.flush()
            self.stream.write(text)
            self.stream.flush()
        
        def flush(self):
            self.file.flush()
            self.stream.flush()
        
        def isatty(self):
            """Return False since we're writing to a file"""
            return False
        
        def fileno(self):
            """Return the original stream's fileno"""
            return self.stream.fileno()
    
    # Open log file in append mode
    log_file_handle = open(log_file, 'a', encoding='utf-8')
    log_file_handle.write(f"\n{'='*80}\n")
    log_file_handle.write(f"Backend started at {datetime.now().isoformat()}\n")
    log_file_handle.write(f"{'='*80}\n")
    
    # Create tee for stdout and stderr
    sys.stdout = TeeOutput(log_file_handle, sys.__stdout__)
    sys.stderr = TeeOutput(log_file_handle, sys.__stderr__)
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )

