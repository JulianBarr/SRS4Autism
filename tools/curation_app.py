import streamlit as st
import pandas as pd
import os
from PIL import Image
from pathlib import Path

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "logs" / "vision_cleanup_report.csv"
IMAGE_DIR = BASE_DIR / "content" / "media" / "objects"  # Updated to hash-based storage

st.set_page_config(layout="wide", page_title="CUMA Curation Deck")

def load_data():
    if not CSV_PATH.exists():
        st.error(f"CSV not found: {CSV_PATH}")
        return pd.DataFrame()
    # Read as string to avoid NaN issues
    df = pd.read_csv(CSV_PATH, dtype=str).fillna("")
    if "Reviewed" not in df.columns:
        df["Reviewed"] = "False"
    return df

def save_data(df):
    df.to_csv(CSV_PATH, index=False)

def fix_extension(old_name, new_name):
    """Ensures new_name has the same extension as old_name."""
    if new_name == "DELETE": return new_name
    
    _, old_ext = os.path.splitext(old_name)
    root, _ = os.path.splitext(new_name)
    
    # Return filename with original extension
    return f"{root}{old_ext}"

# --- STATE MANAGEMENT ---
if 'df' not in st.session_state:
    st.session_state.df = load_data()

if 'ui_index' not in st.session_state:
    st.session_state.ui_index = 0

df = st.session_state.df
if df.empty:
    st.stop()

# --- FILTER LOGIC ---
st.sidebar.header("Navigation")
filter_mode = st.sidebar.radio("Show:", ["All Cards", "Review Needed (❌)", "Already Reviewed"])

if filter_mode == "Review Needed (❌)":
    filtered_indices = df[(df['Match?'] == 'False') & (df['Reviewed'] != 'True')].index
elif filter_mode == "Already Reviewed":
    filtered_indices = df[df['Reviewed'] == 'True'].index
else:
    filtered_indices = df.index

if len(filtered_indices) == 0:
    st.success("🎉 No cards match this filter!")
    st.stop()

# Safety check
if st.session_state.ui_index >= len(filtered_indices):
    st.session_state.ui_index = 0

# --- CALLBACKS ---

def prev_callback():
    """Go back one step."""
    if st.session_state.ui_index > 0:
        st.session_state.ui_index -= 1

def save_and_next_callback(idx, old_filename):
    """Saves inputs using DYNAMIC keys and advances."""
    key_zh = f"zh_{idx}"
    key_fn = f"fn_{idx}"
    key_match = f"match_{idx}"

    st.session_state.df.at[idx, 'Chinese'] = st.session_state[key_zh]
    
    # FORCE EXTENSION MATCH ON SAVE (Safety Net)
    raw_new_filename = st.session_state[key_fn]
    safe_filename = fix_extension(old_filename, raw_new_filename)
    
    st.session_state.df.at[idx, 'New_Filename'] = safe_filename
    st.session_state.df.at[idx, 'Match?'] = str(st.session_state[key_match])
    st.session_state.df.at[idx, 'Reviewed'] = "True"
    
    save_data(st.session_state.df)
    
    # Advance Index
    if st.session_state.ui_index < len(filtered_indices) - 1:
        st.session_state.ui_index += 1
    else:
        st.toast("🎉 End of list!")

def trash_callback(idx):
    """Marks image as delete and advances."""
    st.session_state.df.at[idx, 'New_Filename'] = "DELETE"
    st.session_state.df.at[idx, 'Reviewed'] = "True"
    save_data(st.session_state.df)
    
    if st.session_state.ui_index < len(filtered_indices) - 1:
        st.session_state.ui_index += 1

# --- SIDEBAR ---
selected_ui_index = st.sidebar.number_input(
    f"Card Index (0 to {len(filtered_indices)-1})", 
    min_value=0, 
    max_value=len(filtered_indices)-1,
    key="ui_index"
)

# Get Data
current_idx = filtered_indices[st.session_state.ui_index]
current_row = df.loc[current_idx]

# --- AUTO-CORRECT DISPLAY ---
# Before showing the filename, we fix the extension mismatch from the CSV
# so the user sees the CORRECT version immediately.
corrected_filename = fix_extension(current_row['Old_Filename'], current_row['New_Filename'])

# --- MAIN UI ---
col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader(f"Word: {current_row['English_Word']}")
    image_filename = current_row['Old_Filename']
    image_path = IMAGE_DIR / image_filename
    
    # Show info about hash-based storage
    st.info("ℹ️ **Hash-based storage**: Files are stored with hash-based names (e.g., `8f4b2e19.jpg`). 'Renaming' only adds a searchable alias in the knowledge graph.")
    
    if image_path.exists():
        try:
            img = Image.open(image_path)
            st.image(img, use_container_width=True, caption=image_filename)
        except:
            st.error("Image corrupted")
    else:
        st.warning(f"Image not found: {image_filename}")

    st.button("🗑️ Trash Image", on_click=trash_callback, args=(current_idx,), use_container_width=True)

with col2:
    st.info(f"AI Reason: {current_row['Reason']}")
    
    # DYNAMIC WIDGETS
    st.text_input("Chinese Translation", 
                  value=current_row['Chinese'], 
                  key=f"zh_{current_idx}")
    
    st.text_input("Searchable Alias (Optional)", 
                  value=corrected_filename, # <--- We show the FIXED version here
                  key=f"fn_{current_idx}",
                  help="This adds a searchable alias in the knowledge graph. The physical file keeps its hash-based name (e.g., 8f4b2e19.jpg) and is NOT renamed on disk.")
    
    st.checkbox("Image matches Word?", 
                value=(current_row['Match?'] == 'True'), 
                key=f"match_{current_idx}")
    
    st.markdown("---")
    
    # Navigation Buttons
    b_col1, b_col2 = st.columns(2)
    
    with b_col1:
        st.button("⬅️ Previous", 
                  on_click=prev_callback, 
                  use_container_width=True,
                  disabled=(st.session_state.ui_index == 0))
        
    with b_col2:
        st.button("💾 Save & Next ➡️", 
                  on_click=save_and_next_callback, 
                  args=(current_idx, image_filename), # Pass old filename for extension check
                  type="primary", 
                  use_container_width=True)

# Progress Bar
reviewed_count = len(df[df['Reviewed'] == 'True'])
st.progress(reviewed_count / len(df))
st.caption(f"Progress: {reviewed_count}/{len(df)} reviewed")