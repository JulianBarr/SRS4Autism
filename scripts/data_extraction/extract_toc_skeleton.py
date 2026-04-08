import os
import json
from pydantic import BaseModel
from typing import List
from google import genai
from google.genai import types

# Load .env variables if python-dotenv is available, as a best practice
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ------------------------------------------------------------------
# 1. Define the Pydantic Models for Structured Outputs
# ------------------------------------------------------------------

class PhasalObjective(BaseModel):
    index: str      # e.g., "1.1", "2.3"
    title: str      # The description/title of the item

class Objective(BaseModel):
    title: str      # e.g., "1. 发出不同声音"
    phasal_objectives: List[PhasalObjective]

class Submodule(BaseModel):
    title: str      # e.g., "语言表达篇" or "语言理解篇"
    objectives: List[Objective]

class CurriculumSkeleton(BaseModel):
    module: str = "语言"
    submodules: List[Submodule]

# ------------------------------------------------------------------
# 2. Main Execution Pipeline
# ------------------------------------------------------------------

def main():
    # File paths
    pdf_path = "scripts/data_extraction/21_HHH_lang_toc.pdf"
    output_json_path = "21_heep_hong_language_skeleton.json"

    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: Please set the GEMINI_API_KEY environment variable. (e.g. export GEMINI_API_KEY='your_key')")
        return

    client = genai.Client(api_key=api_key)

    uploaded_file = None
    try:
        # Step 1: Upload the Image PDF to Gemini File API
        print(f"Uploading {pdf_path} to Gemini...")
        uploaded_file = client.files.upload(file=pdf_path)
        print(f"Successfully uploaded file: {uploaded_file.name}")

        system_prompt = """
        You are an expert Special Education data structural extractor.
        Read the provided Image PDF of a Table of Contents.
        Your task is to extract a strictly formatted structural skeleton (the first 4 hierarchical levels) 
        from the provided Table of Contents (TOC) of a special education language curriculum.

        The original text is in Traditional Chinese. You MUST translate all extracted text into Simplified Chinese.

        The hierarchy is as follows:
        - Module (Level 1): Already defined as "语言" (Language).
        - Submodule (Level 2): e.g., "语言表达篇" (Expressive Language) or "语言理解篇" (Receptive Language).
        - Objective (Level 3): The main goals, typically numbered like "1. 发出不同声音" or "1 听觉专注".
        - Phasal Objective (Level 4): The sub-goals under each main goal, typically numbered like "1.1", "1.2", "2.1", etc.

        Instructions:
        1. Only extract the structural hierarchy based on the schema provided.
        2. Do NOT invent goals, materials, passing criteria, or anything else not in the TOC.
        3. Ensure the numbering scheme is correctly extracted and assigned.
        4. Group Phasal Objectives under their corresponding Objectives correctly.
        5. Group Objectives under their corresponding Submodules correctly.
        6. You MUST translate all extracted text into Simplified Chinese.
        """

        # Step 2: Use Multimodal Gemini Call
        print("Sending request to Gemini using Structured Outputs and Multimodal Input...")
        response = client.models.generate_content(
            model="gemini-3.1-pro-preview", # Note: change to gemini-2.5-pro if 3.1 is not yet deployed to your API tier
            contents=[
                uploaded_file,
                "Please extract the skeleton from the provided PDF Table of Contents. Ensure all output is in Simplified Chinese and strictly mapped to the provided schema."
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=CurriculumSkeleton,
                temperature=0.0,
            )
        )

        # genai SDK parses Pydantic models automatically when response_schema is provided
        skeleton_data = None
        if hasattr(response, 'parsed') and response.parsed is not None:
            skeleton_data = response.parsed
        else:
            # Fallback just in case
            skeleton_data = CurriculumSkeleton.model_validate_json(response.text)

        # Step 3: Export to JSON
        print(f"Saving extracted skeleton to {output_json_path}...")
        with open(output_json_path, 'w', encoding='utf-8') as f:
            # Output pretty-printed JSON ensuring CJK characters are correctly handled
            json.dump(skeleton_data.model_dump(), f, ensure_ascii=False, indent=4)
        print("Done! Skeleton JSON created successfully.")

    except Exception as e:
        print(f"Error during processing: {e}")
    finally:
        # Step 4: Cleanup
        if uploaded_file:
            print(f"Cleaning up: deleting {uploaded_file.name} from Gemini servers...")
            try:
                client.files.delete(name=uploaded_file.name)
                print("Cleanup complete.")
            except Exception as e:
                print(f"Error deleting file: {e}")

if __name__ == "__main__":
    main()
