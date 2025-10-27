#!/usr/bin/env python3
"""
Run script for SRS4Autism backend
"""
import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 8000))
    
    print(f"Starting SRS4Autism API server on {host}:{port}")
    print("Make sure to set GEMINI_API_KEY in your .env file for AI features")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )

