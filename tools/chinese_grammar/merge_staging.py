import json
from pathlib import Path

# Define paths
BASE_DIR = Path(__file__).parent
EPUB_JSON = BASE_DIR / "grammar_staging.json"
PDF_JSON = BASE_DIR / "grammar_staging_pdf.json"

def merge_data():
    # 1. Load existing main data (EPUB)
    if EPUB_JSON.exists():
        with open(EPUB_JSON, 'r', encoding='utf-8') as f:
            main_data = json.load(f)
    else:
        main_data = []

    # 2. Load new PDF data
    if not PDF_JSON.exists():
        print(f"❌ PDF data not found at {PDF_JSON}")
        return

    with open(PDF_JSON, 'r', encoding='utf-8') as f:
        pdf_data = json.load(f)

    print(f"📄 Main Staging: {len(main_data)} items")
    print(f"📄 PDF Staging:  {len(pdf_data)} items")

    # 3. Merge (Avoid duplicates based on Title)
    # We use a dictionary map to ensure we don't add the same grammar point twice
    existing_titles = {item['grammar_point_cn'] for item in main_data}
    
    new_count = 0
    for item in pdf_data:
        if item['grammar_point_cn'] not in existing_titles:
            # Optional: Add a tag to know it came from PDF
            item['source_type'] = 'pdf' 
            main_data.append(item)
            existing_titles.add(item['grammar_point_cn'])
            new_count += 1
    
    # 4. Save back to main file
    with open(EPUB_JSON, 'w', encoding='utf-8') as f:
        json.dump(main_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Merged! Added {new_count} new items from PDF.")
    print(f"📊 Total Staging Items: {len(main_data)}")

if __name__ == "__main__":
    merge_data()
