import streamlit as st
import requests
import pandas as pd
from pathlib import Path
import math
import os

# --- CONFIGURATION ---
FUSEKI_QUERY_URL = "http://localhost:3030/srs4autism/query"
DECISIONS_FILE = Path("data/content_db/logic_city_decisions.csv")
ITEMS_PER_PAGE = 50

# Define Project Root for finding images (assuming script is in scripts/curation/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

st.set_page_config(page_title="Logic City Curator (Level 2)", layout="wide")
st.title("🛡️ Logic City Curator (Level 2)")

# --- HELPER: RESOLVE IMAGE PATH ---
def find_image_file(image_path_str):
    """
    Locates the actual image file on disk using logic from literacy.py
    """
    if not image_path_str: return None
    
    # Normalize path strings from Graph
    path = image_path_str.strip()
    if path.startswith("content/media/"):
        path = path.replace("content/media/", "")
    elif path.startswith("/content/media/"):
        path = path.replace("/content/media/", "")
    elif path.startswith("/media/"):
        path = path.replace("/media/", "")
        
    filename = Path(path).name
    
    # Search locations
    media_dirs = [
        PROJECT_ROOT / "content" / "media" / "images",
        PROJECT_ROOT / "media" / "images",
        PROJECT_ROOT / "media" / "visual_images",
        PROJECT_ROOT / "media" / "pinyin",
        PROJECT_ROOT / "media"
    ]
    
    for d in media_dirs:
        candidate = d / filename
        if candidate.exists():
            return str(candidate)
            
    return None

# --- LOAD / SAVE CSV ---
def load_decisions():
    if DECISIONS_FILE.exists():
        return pd.read_csv(DECISIONS_FILE)
    return pd.DataFrame(columns=["English", "Selected_URI", "Selected_Text", "Status"])

def save_decision(english, uri, text):
    df = load_decisions()
    df = df[df["English"] != english]
    new_row = pd.DataFrame([{
        "English": english, 
        "Selected_URI": uri, 
        "Selected_Text": text,
        "Status": "Pending Apply"
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    DECISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DECISIONS_FILE, index=False)
    return df

# --- FETCH DATA ---
@st.cache_data
def fetch_collisions():
    # Updated Query: Now fetches ?imagePath
    query = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT ?enWord ?zhNode ?zhText ?imagePath WHERE {
        # 1. Get English Word
        ?enNode a srs-kg:Word ; srs-kg:text ?enWord .
        FILTER(lang(?enWord) = "en")
        
        # 2. Link to Concept
        ?enNode srs-kg:means ?concept .
        
        # 3. Link to Chinese Word (Level 2)
        ?zhNode srs-kg:means ?concept ;
                srs-kg:text ?zhText ;
                srs-kg:learningLevel 2 .
        FILTER(lang(?zhText) = "zh")

        # 4. Get Image (Optional)
        OPTIONAL {
            ?concept srs-kg:hasVisualization ?imgNode .
            ?imgNode srs-kg:imageFilePath ?imagePath .
        }
    } ORDER BY ?enWord
    """
    try:
        response = requests.post(FUSEKI_QUERY_URL, data={"query": query}, headers={"Accept": "application/json"})
        if response.status_code != 200: return {}
        
        bindings = response.json()['results']['bindings']
        grouped = {}
        for b in bindings:
            en = b['enWord']['value']
            
            # Extract basic data
            item = {
                "uri": b['zhNode']['value'], 
                "text": b['zhText']['value'],
                "image_raw": b.get('imagePath', {}).get('value')
            }
            
            if en not in grouped: grouped[en] = []
            
            # Avoid duplicates (sometimes multiple images cause row duplication)
            if not any(x['uri'] == item['uri'] for x in grouped[en]):
                grouped[en].append(item)
        
        return {k: v for k, v in grouped.items() if len(v) > 1}
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return {}

# --- MAIN UI ---
collisions = fetch_collisions()
decisions_df = load_decisions()

# Sidebar
with st.sidebar:
    st.header("Settings")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    st.write("---")
    total_items = len(collisions)
    fixed_count = len(decisions_df[decisions_df["English"].isin(collisions.keys())])
    st.metric("Progress", f"{fixed_count} / {total_items}")
    
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1) if total_pages > 1 else 1

# List Render
if not collisions:
    st.success("✅ No collisions found in Level 2!")
else:
    items_list = list(collisions.items())
    start_idx = (page - 1) * ITEMS_PER_PAGE
    current_page_items = items_list[start_idx : start_idx + ITEMS_PER_PAGE]

    st.write(f"Showing items {start_idx + 1}-{min(start_idx + ITEMS_PER_PAGE, total_items)}")

    for en_word, candidates in current_page_items:
        current_decision = decisions_df[decisions_df["English"] == en_word]
        is_done = not current_decision.empty
        label_icon = "✅" if is_done else "⚠️"
        
        with st.expander(f"{label_icon} **{en_word}** ({len(candidates)} options)", expanded=not is_done):
            
            # Create a Grid Layout for candidates
            # We display them side-by-side if there are few, or rows if many
            cols = st.columns(len(candidates))
            
            selected_uri = None
            
            # 1. VISUALIZATION ROW
            # We show each candidate with its specific image (if available) so you see the context
            for idx, c in enumerate(candidates):
                with cols[min(idx, len(cols)-1)]:
                    # Try to resolve image
                    img_path = find_image_file(c['image_raw'])
                    if img_path:
                        st.image(img_path, caption=c['text'], width=150)
                    else:
                        st.markdown(f"**{c['text']}**")
                        st.caption("(No Image)")

            st.write("---")

            # 2. SELECTION ROW
            c1, c2 = st.columns([4, 1])
            with c1:
                options = {c['uri']: f"{c['text']} ({'Has Image' if c['image_raw'] else 'No Image'})" for c in candidates}
                
                default_idx = 0
                if is_done:
                    saved_uri = current_decision.iloc[0]["Selected_URI"]
                    if saved_uri in options:
                        default_idx = list(options.keys()).index(saved_uri)

                selected_uri = st.radio(
                    f"Select Correct Definition for '{en_word}':",
                    options.keys(),
                    format_func=lambda x: options[x],
                    index=default_idx,
                    key=f"rad_{en_word}",
                    horizontal=True
                )
            
            with c2:
                st.write("")
                if st.button("Save", key=f"btn_{en_word}"):
                    # Map back to simple text for CSV
                    simple_text = next(c['text'] for c in candidates if c['uri'] == selected_uri)
                    save_decision(en_word, selected_uri, simple_text)
                    st.toast(f"Fixed: {en_word}")
                    st.rerun()  # <--- ADD THIS LINE to force instant update
