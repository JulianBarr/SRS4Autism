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

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

st.set_page_config(page_title="Logic City Curator (Level 2)", layout="wide")
st.title("🛡️ Logic City Curator (Level 2)")

# --- HELPER: RESOLVE IMAGE PATH ---
def find_image_file(image_path_str):
    if not image_path_str: return None
    path = image_path_str.strip()
    for prefix in ["content/media/", "/content/media/", "/media/"]:
        if path.startswith(prefix):
            path = path.replace(prefix, "")
    
    filename = Path(path).name
    media_dirs = [
        PROJECT_ROOT / "content" / "media" / "images",
        PROJECT_ROOT / "media" / "images",
        PROJECT_ROOT / "media" / "visual_images",
        PROJECT_ROOT / "media" / "pinyin",
        PROJECT_ROOT / "media"
    ]
    for d in media_dirs:
        candidate = d / filename
        if candidate.exists(): return str(candidate)
    return None

# --- LOAD / SAVE CSV ---
def load_decisions():
    if DECISIONS_FILE.exists():
        # Ensure 'Selected_Text' column exists (for backward compatibility)
        df = pd.read_csv(DECISIONS_FILE)
        if "Selected_Text" not in df.columns:
            df["Selected_Text"] = ""
        return df
    return pd.DataFrame(columns=["English", "Selected_URI", "Selected_Text", "Status"])

def save_decision(english, uri, text):
    df = load_decisions()
    df = df[df["English"] != english]
    new_row = pd.DataFrame([{
        "English": english, 
        "Selected_URI": uri, 
        "Selected_Text": text, # Save the edited text
        "Status": "Pending Apply"
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    DECISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DECISIONS_FILE, index=False)
    return df

# --- FETCH DATA ---
@st.cache_data
def fetch_collisions():
    query = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT ?enWord ?zhNode ?zhText ?imagePath WHERE {
        ?enNode a srs-kg:Word ; srs-kg:text ?enWord .
        FILTER(lang(?enWord) = "en")
        ?enNode srs-kg:means ?concept .
        ?zhNode srs-kg:means ?concept ;
                srs-kg:text ?zhText ;
                srs-kg:learningLevel 2 .
        FILTER(lang(?zhText) = "zh")
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
            item = {
                "uri": b['zhNode']['value'], 
                "text": b['zhText']['value'],
                "image_raw": b.get('imagePath', {}).get('value')
            }
            if en not in grouped: grouped[en] = []
            if not any(x['uri'] == item['uri'] for x in grouped[en]):
                grouped[en].append(item)
        return {k: v for k, v in grouped.items() if len(v) > 1}
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return {}

# --- MAIN UI ---
collisions = fetch_collisions()
decisions_df = load_decisions()

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
            
            # 1. VISUALIZATION ROW
            cols = st.columns(len(candidates))
            for idx, c in enumerate(candidates):
                with cols[min(idx, len(cols)-1)]:
                    img_path = find_image_file(c['image_raw'])
                    if img_path:
                        st.image(img_path, caption=c['text'], width=150)
                    else:
                        st.markdown(f"**{c['text']}**")
                        st.caption("(No Image)")

            st.write("---")

            # 2. SELECTION & EDITING
            c1, c2 = st.columns([4, 1])
            with c1:
                options = {c['uri']: c['text'] for c in candidates}
                
                # Determine Selection
                default_idx = 0
                saved_text_val = "" # For pre-filling text box
                
                if is_done:
                    saved_uri = current_decision.iloc[0]["Selected_URI"]
                    saved_text_val = current_decision.iloc[0]["Selected_Text"]
                    if saved_uri in options:
                        default_idx = list(options.keys()).index(saved_uri)
                
                selected_uri = st.radio(
                    f"Select Base Translation for '{en_word}':",
                    options.keys(),
                    format_func=lambda x: f"{options[x]} (Original)",
                    index=default_idx,
                    key=f"rad_{en_word}",
                    horizontal=True
                )
                
                # Logic to determine what text to show in the edit box
                # If we just switched selection, use that candidate's text.
                # If we loaded a saved decision, use the saved text.
                current_candidate_text = options[selected_uri]
                display_text = saved_text_val if (is_done and saved_uri == selected_uri) else current_candidate_text

                edited_text = st.text_input(
                    f"Edit '{current_candidate_text}' (if incorrect):", 
                    value=display_text,
                    key=f"txt_{en_word}"
                )

            with c2:
                st.write("")
                st.write("")
                st.write("") # Spacing
                if st.button("Save", key=f"btn_{en_word}"):
                    save_decision(en_word, selected_uri, edited_text)
                    st.toast(f"Fixed: {en_word} -> {edited_text}")
                    st.rerun()
