import os
import json
import google.generativeai as genai
import time
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
# Import the dotenv library to load environment variables
from dotenv import load_dotenv

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
INPUT_FILENAME = "book.epub"
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

def read_book_content(filepath):
    """
    Reads content from a .txt or .epub file.
    For EPUBs, it extracts and combines text from all chapters.
    """
    if not os.path.exists(filepath):
        print(f"Error: Input file not found at '{filepath}'")
        return None

    _, extension = os.path.splitext(filepath)

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
    else:
        print(f"Error: Unsupported file format '{extension}'. Please provide a .txt or .epub file.")
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

def generate_knowledge_graph_nodes(text_chunk):
    """
    Uses the Gemini API to analyze a chunk of text and extract grammar points.
    """
    print(f"    Sending chunk to Gemini API ({len(text_chunk)} characters)...")
    
    model = genai.GenerativeModel(MODEL_NAME)
    json_schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "grammar_point": {"type": "STRING"}, "level": {"type": "STRING"},
                "structure": {"type": "STRING"}, "explanation": {"type": "STRING"},
                "examples": {
                    "type": "ARRAY", "items": {
                        "type": "OBJECT", "properties": {
                            "chinese": {"type": "STRING"}, "pinyin": {"type": "STRING"},
                            "english": {"type": "STRING"}
                        }, "required": ["chinese", "pinyin", "english"]
                    }
                }
            }, "required": ["grammar_point", "level", "structure", "explanation", "examples"]
        }
    }
    prompt = f"""
    You are a linguistics expert specializing in Chinese grammar.
    Analyze the following text and extract any grammar points discussed.
    For each grammar point, provide its name, level (if mentioned), structure, a clear explanation, and all associated examples.
    If no specific grammar point is found, return an empty list.
    Text to analyze: --- {text_chunk} ---
    """
    response = None # Define response here to have it in scope for the except block
    try:
        response = model.generate_content(
            prompt,
            # --- FIX: Corrected the typo from generation__config to generation_config ---
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=json_schema
            )
        )
        print("    ...API response received.")
        return json.loads(response.text)
    except Exception as e:
        print(f"    An error occurred while processing API response: {e}")
        # Check if the response object exists and has text to print for debugging
        if response and hasattr(response, 'text') and response.text:
            print("    --- BEGIN Corrupted API Response Text ---")
            print(response.text)
            print("    --- END Corrupted API Response Text ---")
        else:
            # This might happen if the error was a network failure before a response was received
            print("    Could not retrieve response text for debugging.")
        return []

def main():
    """Main function to run the knowledge graph generation process."""
    configure_api()
    book_text = read_book_content(INPUT_FILENAME)
    if not book_text: return

    text_chunks = chunk_text(book_text, CHUNK_SIZE)
    knowledge_graph = []
    
    for i, chunk in enumerate(text_chunks):
        print(f"\nProcessing chunk {i+1}/{len(text_chunks)}...")
        time.sleep(1) # Respect API rate limits
        nodes = generate_knowledge_graph_nodes(chunk)
        
        if nodes:
            print(f"  -> Successfully extracted {len(nodes)} grammar point(s) from this chunk.")
            knowledge_graph.extend(nodes)
        else:
            print("  -> No grammar points found in this chunk.")

    try:
        with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(knowledge_graph, f, ensure_ascii=False, indent=4)
        print(f"\n✅ Success! Knowledge graph saved to '{OUTPUT_FILENAME}'")
    except Exception as e:
        print(f"\nError saving the knowledge graph to file: {e}")

if __name__ == "__main__":
    main()
