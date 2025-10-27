# AI Agent

The core AI agent that powers the SRS4Autism learning ecosystem.

## Components

### MCP (Model Context Protocol)
- `knowledge_tracer.py`: Tracks child's learning progress and knowledge state
- `context_manager.py`: Manages context for AI interactions

### Content Generation
- `text_generator.py`: Generates text content using LLMs
- `audio_generator.py`: Creates audio content using TTS
- `image_generator.py`: Generates visual content using AI image models

### Recommendation Engine
- `engine.py`: Main recommendation logic
- `algorithms/`: Various recommendation algorithms

## Purpose

The agent acts as a bridge between:
1. **Child's Internal World**: Real-time understanding of knowledge state and learning patterns
2. **External World Model**: Structured knowledge representation

It finds the most effective path to help the child's internal model grow and align with the external world.

