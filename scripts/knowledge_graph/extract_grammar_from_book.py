#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract Chinese Grammar Points from EPUB or PDF Books using Gemini API.

This script reads a book (EPUB or PDF), splits it into chunks, and uses
the Gemini API to extract grammar points with their structure, explanations,
and examples. The output is saved as a JSON file that can be used to
populate the knowledge graph.
"""

import os
import json
import sys
import google.generativeai as genai
import time
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Try importing PDF libraries
PDF_AVAILABLE = False
PDF_PLUMBER_AVAILABLE = False
try:
    import pdfplumber
    PDF_PLUMBER_AVAILABLE = True
    PDF_AVAILABLE = True
except ImportError:
    try:
        import PyPDF2
        PDF_AVAILABLE = True
    except ImportError:
        PDF_AVAILABLE = False

# Load variables from the .env file
load_dotenv()

# --- Configuration ---
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print("Error: GOOGLE_API_KEY environment variable not set.")
    print("Please create a .env file with GOOGLE_API_KEY='your_key_here'")
    exit(1)

MODEL_NAME = "gemini-2.5-pro"
OUTPUT_FILENAME = "chinese_grammar_knowledge_graph.json"
# Can be overridden via command-line argument
INPUT_FILENAME = "book.epub"  # Can be .epub, .pdf, or .txt
# Set a max character size for each chunk sent to the API
CHUNK_SIZE = 15000

def configure_api():
    """Configures the Google Generative AI client."""
    try:
        genai.configure(api_key=API_KEY)
        print("Google API configured successfully.")
    except Exception as e:
        print(f"Error configuring Google API: {e}")
        exit(1)

def read_pdf_content(filepath):
    """
    Reads content from a PDF file using PyPDF2 or pdfplumber.
    Returns the extracted text as a string.
    """
    print(f"📄 Reading content from PDF file: '{filepath}'...")
    
    if not PDF_AVAILABLE:
        print("Error: No PDF library available. Please install one:")
        print("  pip install PyPDF2")
        print("  or")
        print("  pip install pdfplumber")
        return None
    
    try:
        content = []
        page_count = 0
        
        if PDF_PLUMBER_AVAILABLE:
            # Use pdfplumber (generally better for text extraction)
            import pdfplumber
            print("   Using pdfplumber for extraction...")
            with pdfplumber.open(filepath) as pdf:
                total_pages = len(pdf.pages)
                print(f"   📑 Found {total_pages} pages")
                for page_num, page in enumerate(pdf.pages, 1):
                    if page_num % 50 == 0:
                        print(f"   📄 Processing page {page_num}/{total_pages}...")
                        sys.stdout.flush()
                    text = page.extract_text()
                    if text:
                        content.append(text)
                    page_count = page_num
            print(f"✅ Successfully extracted text from {page_count} pages using pdfplumber.")
            print(f"   Total characters extracted: {sum(len(c) for c in content):,}")
        else:
            # Use PyPDF2
            print("   Using PyPDF2 for extraction...")
            with open(filepath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                print(f"   📑 Found {total_pages} pages")
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    if page_num % 50 == 0:
                        print(f"   📄 Processing page {page_num}/{total_pages}...")
                        sys.stdout.flush()
                    text = page.extract_text()
                    if text:
                        content.append(text)
                page_count = total_pages
            print(f"✅ Successfully extracted text from {page_count} pages using PyPDF2.")
            print(f"   Total characters extracted: {sum(len(c) for c in content):,}")
        
        return "\n\n".join(content)
    except Exception as e:
        print(f"❌ Error reading PDF file: {e}")
        return None

def read_book_content(filepath):
    """
    Reads content from a .txt, .epub, or .pdf file.
    For EPUBs, it extracts and combines text from all chapters.
    For PDFs, it extracts text from all pages.
    """
    if not os.path.exists(filepath):
        print(f"Error: Input file not found at '{filepath}'")
        return None

    _, extension = os.path.splitext(filepath.lower())

    if extension == '.txt':
        print(f"Reading content from plain text file: '{filepath}'...")
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    elif extension == '.epub':
        print(f"Reading content from EPUB file: '{filepath}'...")
        try:
            book = epub.read_epub(filepath)
            content = []
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                content.append(soup.get_text(separator='\n\n', strip=True))
            print("Successfully extracted text from EPUB.")
            return "\n\n".join(content)
        except Exception as e:
            print(f"Error reading EPUB file: {e}")
            return None
    elif extension == '.pdf':
        return read_pdf_content(filepath)
    else:
        print(f"Error: Unsupported file format '{extension}'. Please provide a .txt, .epub, or .pdf file.")
        return None

def chunk_text(text, max_chunk_size):
    """
    Splits the text into chunks of a maximum size, intelligently trying to split
    at paragraph or sentence endings to keep context together.
    """
    print(f"Splitting text into chunks of max ~{max_chunk_size} characters...")
    chunks = []
    current_pos = 0
    while current_pos < len(text):
        end_pos = min(current_pos + max_chunk_size, len(text))
        chunk = text[current_pos:end_pos]

        # If we are not at the end of the book, try to find a better split point
        if end_pos < len(text):
            # Look for the last good place to split (paragraph, then sentence)
            split_pos = chunk.rfind('\n\n')
            if split_pos == -1:
                split_pos = chunk.rfind('.')
            
            # If we found a good split point, adjust the end position
            if split_pos > 0:
                end_pos = current_pos + split_pos + 1
        
        final_chunk = text[current_pos:end_pos].strip()
        if final_chunk:
            chunks.append(final_chunk)
        current_pos = end_pos

    print(f"Found {len(chunks)} chunks to process.")
    return chunks

def generate_knowledge_graph_nodes(text_chunk, chunk_num, total_chunks):
    """
    Uses the Gemini API to analyze a chunk of text and extract grammar points.
    """
    import sys
    sys.stdout.flush()  # Ensure output is flushed
    
    print(f"\n    📤 Sending chunk {chunk_num}/{total_chunks} to Gemini API ({len(text_chunk):,} characters)...")
    print(f"    ⏳ Waiting for API response...")
    
    model = genai.GenerativeModel(MODEL_NAME)
    json_schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "grammar_point": {"type": "STRING"}, 
                "level": {"type": "STRING"},
                "structure": {"type": "STRING"}, 
                "explanation": {"type": "STRING"},
                "examples": {
                    "type": "ARRAY", 
                    "items": {
                        "type": "OBJECT", 
                        "properties": {
                            "chinese": {"type": "STRING"}, 
                            "pinyin": {"type": "STRING"},
                            "english": {"type": "STRING"}
                        }, 
                        "required": ["chinese", "pinyin", "english"]
                    }
                }
            }, 
            "required": ["grammar_point", "level", "structure", "explanation", "examples"]
        }
    }
    prompt = f"""
    You are a linguistics expert specializing in Chinese grammar.
    Analyze the following text and extract any grammar points discussed.
    For each grammar point, provide its name, level (if mentioned), structure, a clear explanation, and all associated examples.
    If no specific grammar point is found, return an empty list.
    Text to analyze: --- {text_chunk} ---
    """
    response = None  # Define response here to have it in scope for the except block
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=json_schema
            )
        )
        print(f"    ✅ API response received!")
        nodes = json.loads(response.text)
        if nodes:
            print(f"    📝 Extracted {len(nodes)} grammar point(s):")
            for i, node in enumerate(nodes[:3], 1):  # Show first 3
                print(f"       {i}. {node.get('grammar_point', 'N/A')} (Level: {node.get('level', 'N/A')})")
            if len(nodes) > 3:
                print(f"       ... and {len(nodes) - 3} more")
        else:
            print(f"    ℹ️  No grammar points found in this chunk.")
        return nodes
    except Exception as e:
        print(f"    ❌ Error occurred while processing API response: {e}")
        # Check if the response object exists and has text to print for debugging
        if response and hasattr(response, 'text') and response.text:
            print("    --- BEGIN Corrupted API Response Text ---")
            print(response.text[:500])  # Only show first 500 chars
            print("    --- END Corrupted API Response Text ---")
        else:
            # This might happen if the error was a network failure before a response was received
            print("    Could not retrieve response text for debugging.")
        return []

def main():
    """Main function to run the knowledge graph generation process."""
    
    # Allow input filename to be specified as command-line argument
    input_filename = INPUT_FILENAME
    if len(sys.argv) > 1:
        input_filename = sys.argv[1]
        print(f"Using input file from command line: {input_filename}")
    
    configure_api()
    
    # Get the script directory and construct paths
    # Go up two levels from scripts/knowledge_graph/ to project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '../..'))
    
    # Allow input file to be specified relative to script dir or project root
    if os.path.exists(input_filename):
        input_path = input_filename
    elif os.path.exists(os.path.join(script_dir, input_filename)):
        input_path = os.path.join(script_dir, input_filename)
    elif os.path.exists(os.path.join(project_root, input_filename)):
        input_path = os.path.join(project_root, input_filename)
    elif os.path.exists(os.path.join(project_root, 'data', 'content_db', input_filename)):
        input_path = os.path.join(project_root, 'data', 'content_db', input_filename)
    else:
        print(f"Error: Could not find input file '{input_filename}'")
        print(f"  Tried: {input_filename}")
        print(f"  Tried: {os.path.join(script_dir, input_filename)}")
        print(f"  Tried: {os.path.join(project_root, input_filename)}")
        print(f"  Tried: {os.path.join(project_root, 'data', 'content_db', input_filename)}")
        return
    
    book_text = read_book_content(input_path)
    if not book_text:
        return

    text_chunks = chunk_text(book_text, CHUNK_SIZE)
    knowledge_graph = []
    total_chunks = len(text_chunks)
    
    print(f"\n{'='*70}")
    print(f"🚀 Starting grammar extraction from {total_chunks} chunks")
    print(f"{'='*70}\n")
    
    for i, chunk in enumerate(text_chunks, 1):
        print(f"\n{'─'*70}")
        print(f"📖 Processing chunk {i}/{total_chunks}")
        print(f"{'─'*70}")
        
        # Show a preview of the chunk
        preview = chunk[:200].replace('\n', ' ')
        print(f"   Preview: {preview}...")
        
        time.sleep(1)  # Respect API rate limits
        nodes = generate_knowledge_graph_nodes(chunk, i, total_chunks)
        
        if nodes:
            knowledge_graph.extend(nodes)
            print(f"   ✅ Added {len(nodes)} grammar point(s) to collection")
            print(f"   📊 Total grammar points so far: {len(knowledge_graph)}")
        else:
            print(f"   ⚠️  No grammar points found in this chunk")
        
        # Save progress periodically (every 5 chunks)
        if i % 5 == 0:
            output_dir = os.path.join(project_root, 'data', 'content_db')
            os.makedirs(output_dir, exist_ok=True)
            temp_output = os.path.join(output_dir, f"{OUTPUT_FILENAME}.tmp")
            try:
                with open(temp_output, 'w', encoding='utf-8') as f:
                    json.dump(knowledge_graph, f, ensure_ascii=False, indent=2)
                print(f"\n   💾 Progress saved: {len(knowledge_graph)} grammar points saved to temporary file")
            except Exception as e:
                print(f"\n   ⚠️  Could not save progress: {e}")
        
        sys.stdout.flush()  # Ensure output is flushed

    # Save output to the data/content_db directory (where populate_grammar.py expects it)
    output_dir = os.path.join(project_root, 'data', 'content_db')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, OUTPUT_FILENAME)
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(knowledge_graph, f, ensure_ascii=False, indent=4)
        print(f"\n✅ Success! Knowledge graph saved to '{output_path}'")
        print(f"   You can now run populate_grammar.py to add these to the knowledge graph.")
    except Exception as e:
        print(f"\nError saving the knowledge graph to file: {e}")

if __name__ == "__main__":
    main()

