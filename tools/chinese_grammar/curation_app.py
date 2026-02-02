import json
import streamlit as st
from pathlib import Path
from typing import List, Dict, Any

# === Configuration ===
STAGING_FILE = Path(__file__).parent / "grammar_staging.json"
APPROVED_FILE = Path(__file__).parent / "grammar_approved.json"

st.set_page_config(layout="wide", page_title="CUMA Grammar Curator")

# === Data Logic ===

def load_staging_data() -> List[Dict[str, Any]]:
    if not STAGING_FILE.exists():
        return []
    with open(STAGING_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_staging_data(data: List[Dict[str, Any]]) -> None:
    with open(STAGING_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def update_approved_file(record: Dict[str, Any], remove: bool = False) -> None:
    """
    Syncs the record with grammar_approved.json.
    - If remove=True: Deletes the record from approved file.
    - If remove=False: Updates/Appends the record.
    """
    approved_data = []
    if APPROVED_FILE.exists():
        with open(APPROVED_FILE, 'r', encoding='utf-8') as f:
            try:
                approved_data = json.load(f)
            except:
                approved_data = []
    
    # 1. Remove existing instance of this ID
    approved_data = [x for x in approved_data if x.get('id') != record.get('id')]
    
    # 2. Add back if not removing
    if not remove:
        clean_record = {
            'id': record.get('id'),
            'grammar_point_cn': record.get('grammar_point_cn'),
            'anchor_example': record.get('anchor_example'),
            'summary_cn': record.get('summary_cn'),
            'mandatory_keywords': record.get('mandatory_keywords', []),
            'pragmatic_scenarios': record.get('pragmatic_scenarios', []),
            'is_useful_for_child': record.get('is_useful_for_child', False)
        }
        approved_data.append(clean_record)
    
    # 3. Save
    with open(APPROVED_FILE, 'w', encoding='utf-8') as f:
        json.dump(approved_data, f, ensure_ascii=False, indent=2)

def parse_list(text: str) -> List[str]:
    return [x.strip() for x in text.replace('，', ',').split('\n') if x.strip()]

def format_list(items: List[str]) -> str:
    return '\n'.join(items) if items else ''

# === Initialization ===

if 'staging_data' not in st.session_state:
    st.session_state.staging_data = load_staging_data()
    st.session_state.current_index = None

# Refresh data reference
data = st.session_state.staging_data

# === Sidebar: Filter & Navigation ===
st.sidebar.title("🔍 CUMA Curator")

# 1. Filter Status
view_mode = st.sidebar.radio("View:", ["Pending", "Approved", "Discarded"], index=0)
status_key = view_mode.lower()

# 2. Filter Items based on View
filtered_items = [(i, d) for i, d in enumerate(data) if d.get('status') == status_key]

st.sidebar.markdown(f"**{len(filtered_items)} items in {view_mode}**")

# 3. Auto-Select Logic
# If current selection is None, or matches the wrong status, pick the first one from the current view
current_record = None
if st.session_state.current_index is not None:
    # Check if current index is valid and matches current view
    if 0 <= st.session_state.current_index < len(data):
        if data[st.session_state.current_index].get('status') != status_key:
            st.session_state.current_index = None

if st.session_state.current_index is None and filtered_items:
    st.session_state.current_index = filtered_items[0][0]

# 4. Navigation List
if filtered_items:
    options = [f[0] for f in filtered_items]
    try:
        default_idx = options.index(st.session_state.current_index) if st.session_state.current_index in options else 0
    except:
        default_idx = 0
        
    selected_idx = st.sidebar.selectbox(
        "Select Item:",
        options,
        format_func=lambda x: f"{data[x]['grammar_point_cn']}",
        index=default_idx
    )
    
    if selected_idx != st.session_state.current_index:
        st.session_state.current_index = selected_idx
        st.rerun()

# === Main Area ===

if st.session_state.current_index is None:
    st.info(f"No {view_mode} items found.")
    if st.button("Reload Data"):
        st.session_state.staging_data = load_staging_data()
        st.rerun()
    st.stop()

# Load Record
idx = st.session_state.current_index
item = data[idx]

st.header(f"{view_mode}: {item.get('grammar_point_cn', 'Untitled')}")

with st.expander("Source Context", expanded=False):
    st.info(item.get('source_header', 'No Header'))
    st.text(item.get('source_content_preview', ''))

# Form
with st.form(key="curate_form"):
    c1, c2 = st.columns([1, 1])
    
    with c1:
        new_title = st.text_input("Title (CN)", item['grammar_point_cn'])
        new_anchor = st.text_input("Anchor Example", item['anchor_example'])
        new_keywords = st.text_area("Keywords (Line separated)", format_list(item['mandatory_keywords']), height=100)
        is_useful = st.checkbox("Useful for Child?", value=item['is_useful_for_child'])
        
    with c2:
        new_summary = st.text_area("Summary", item['summary_cn'], height=100)
        new_scenarios = st.text_area("Scenarios (Line separated)", format_list(item['pragmatic_scenarios']), height=150)

    # Dynamic Buttons based on View Mode
    b1, b2 = st.columns([1, 4])
    
    with b1:
        if view_mode == "Pending":
            submit_label = "✅ Approve"
            submit_type = "primary"
        elif view_mode == "Approved":
            submit_label = "💾 Update"
            submit_type = "primary"
        else: # Discarded
            submit_label = "♻️ Restore to Pending"
            submit_type = "secondary"
            
        submit = st.form_submit_button(submit_label, type=submit_type)

    with b2:
        if view_mode != "Discarded":
            discard = st.form_submit_button("🗑️ Discard")
        else:
            discard = False # Can't discard what is already discarded

    # Logic Implementation
    if submit:
        # Update Memory
        data[idx]['grammar_point_cn'] = new_title
        data[idx]['anchor_example'] = new_anchor
        data[idx]['summary_cn'] = new_summary
        data[idx]['mandatory_keywords'] = parse_list(new_keywords)
        data[idx]['pragmatic_scenarios'] = parse_list(new_scenarios)
        data[idx]['is_useful_for_child'] = is_useful

        if view_mode == "Discarded":
            data[idx]['status'] = 'pending' # Restore
            st.toast("Restored to Pending")
        else:
            data[idx]['status'] = 'approved'
            # Sync to Approved File
            if is_useful:
                update_approved_file(data[idx], remove=False)
                st.toast(f"Saved: {new_title}")
            else:
                # If marked not useful but approved (weird case), remove from file
                update_approved_file(data[idx], remove=True)
                
        save_staging_data(data)
        
        # Advance logic: Only advance if we moved it OUT of the current view
        # If updating an Approved item while in Approved view, stay there.
        # If Approving a Pending item, it moves to Approved, so we need to advance.
        if view_mode == "Pending" or view_mode == "Discarded":
            st.session_state.current_index = None # Force pick next
        st.rerun()

    if discard:
        data[idx]['status'] = 'discarded'
        save_staging_data(data)
        # Remove from approved file if it was previously there
        update_approved_file(data[idx], remove=True)
        
        st.toast("Discarded")
        st.session_state.current_index = None # Force pick next
        st.rerun()
