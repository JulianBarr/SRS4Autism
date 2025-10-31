#!/usr/bin/env python3
"""
Run script for SRS4Autism backend
"""
import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('gemini.env')

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
    
    print(f"Starting Curious Mario API server on {host}:{port}")
    print("Make sure to set GEMINI_API_KEY in your .env file for AI features")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )

