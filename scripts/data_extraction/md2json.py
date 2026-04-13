import json
import re
import os

def parse_md_to_json(input_file, output_file):
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    data = {
        "module": "",
        "submodules": []
    }

    current_submodule = None
    current_objective = None
    current_phasal = None
    current_goal = None
    
    current_state = None
    shared_precautions_text = ""
    current_activities = []

    # Regex patterns for matching hierarchical headers
    h1_pat = re.compile(r'^#\s+Module:\s*(.*)')
    h2_pat = re.compile(r'^##\s+Submodule:\s*(.*)')
    h3_pat = re.compile(r'^###\s+Objective:\s*(.*)')
    h4_pat = re.compile(r'^####\s+(.*)')
    h5_pat = re.compile(r'^#####\s+(.*)')

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Header parsing
        m1 = h1_pat.match(line)
        if m1:
            data["module"] = m1.group(1).strip()
            current_state = None
            continue

        m2 = h2_pat.match(line)
        if m2:
            current_submodule = {"title": m2.group(1).strip(), "objectives": []}
            data["submodules"].append(current_submodule)
            current_objective = None
            current_phasal = None
            current_goal = None
            current_state = None
            continue

        m3 = h3_pat.match(line)
        if m3:
            current_objective = {"title": m3.group(1).strip(), "phasal_objectives": []}
            if current_submodule is not None:
                current_submodule["objectives"].append(current_objective)
            current_phasal = None
            current_goal = None
            current_state = None
            continue

        m4 = h4_pat.match(line)
        if m4:
            raw_title = m4.group(1).strip()
            index = ""
            title = raw_title
            
            # Extract "1.1" or "项目一：" as the section index
            idx_match = re.match(r'^([\d\.]+)\s+(.*)', raw_title)
            if idx_match:
                index = idx_match.group(1)
                title = idx_match.group(2)
            else:
                idx_match2 = re.match(r'^(项目[一二三四五六七八九十]+)：\s*(.*)', raw_title)
                if idx_match2:
                    index = idx_match2.group(1)
                    title = idx_match2.group(2)

            current_phasal = {
                "index": index,
                "title": title,
                "goals": []
            }
            if current_objective is not None:
                current_objective["phasal_objectives"].append(current_phasal)
            
            current_goal = None
            shared_precautions_text = ""  # Reset shared precautions for the new section
            current_state = None
            continue

        m5 = h5_pat.match(stripped)
        if m5:
            # Save the activities belonging to the previous goal before moving to the next
            if current_goal is not None and current_activities:
                current_goal["activity_suggestions"] = "\n".join(current_activities)
            
            raw_desc = m5.group(1).strip()
            
            # 1. Format the prefix letter from "[A]" to "A.", or remove empty "[]"
            letter_match = re.match(r'^\[([A-Z])\]\s*(.*)', raw_desc)
            if letter_match:
                raw_desc = f"{letter_match.group(1)}. {letter_match.group(2)}"
            else:
                empty_match = re.match(r'^\[\]\s*(.*)', raw_desc)
                if empty_match:
                    raw_desc = empty_match.group(1).strip()
                
            # 2. Standardize the separator to '/' so the frontend can extract the age
            if '|' in raw_desc:
                parts = raw_desc.rsplit('|', 1)
                goal_desc = f"{parts[0].strip()} / {parts[1].strip()}"
            else:
                # Normalize spacing if it's already using '/'
                match = re.search(r'\s*/\s*([\d>\-]+\s*(?:岁|个月).*)$', raw_desc)
                if match:
                    goal_desc = f"{raw_desc[:match.start()].strip()} / {match.group(1).strip()}"
                else:
                    goal_desc = raw_desc
            
            precautions_val = shared_precautions_text.strip() if shared_precautions_text.strip() else None

            current_goal = {
                "description": goal_desc,
                "materials": [],
                "passing_criteria": None,
                "precautions": precautions_val,
                "activity_suggestions": None
            }
            current_activities = []
            
            if current_phasal is not None:
                current_phasal["goals"].append(current_goal)
            
            current_state = None
            continue

        # Field triggers
        if stripped.startswith("**Shared Precautions:**"):
            current_state = "shared_precautions"
            sp = stripped.replace("**Shared Precautions:**", "").strip()
            if sp:
                shared_precautions_text += sp
            continue

        if stripped.startswith("**Precautions:**"):
            current_state = "precautions"
            prec_str = stripped.replace("**Precautions:**", "").strip()
            if prec_str and current_goal is not None:
                if current_goal["precautions"]:
                    current_goal["precautions"] += "\n" + prec_str
                else:
                    current_goal["precautions"] = prec_str
            continue

        if stripped.startswith("**Materials:**"):
            current_state = "materials"
            mat_str = stripped.replace("**Materials:**", "").strip()
            if mat_str and current_goal is not None:
                # Strip bullet points if they happen to be on the same line
                clean_mat_str = re.sub(r'^[\*\-]\s+', '', mat_str)
                mat_list = [m.strip() for m in re.split(r'[,，、]', clean_mat_str) if m.strip()]
                current_goal["materials"].extend(mat_list)
            continue

        if stripped.startswith("**Activities:**"):
            current_state = "activities"
            continue

        # Accumulate multi-line content based on the current state
        if current_state == "shared_precautions":
            val = stripped
            if val.startswith("* ") or val.startswith("- "):
                val = val[2:]
            shared_precautions_text += ("\n" + val if shared_precautions_text else val)

        elif current_state == "precautions" and current_goal is not None:
            val = stripped
            if val.startswith("* ") or val.startswith("- "):
                val = val[2:]
            if current_goal["precautions"]:
                current_goal["precautions"] += "\n" + val
            else:
                current_goal["precautions"] = val

        elif current_state == "materials" and current_goal is not None:
            # Clean up bullet markers if materials span multiple lines
            clean_line = re.sub(r'^[\*\-]\s+', '', stripped)
            mat_list = [m.strip() for m in re.split(r'[,，、]', clean_line) if m.strip()]
            current_goal["materials"].extend(mat_list)

        elif current_state == "activities" and current_goal is not None:
            # Strip markdown list formatting but keep text
            clean_line = re.sub(r'^[\*\-]\s+', '', stripped)
            if clean_line:
                current_activities.append(clean_line)

    # Catch the last goal's activities at EOF
    if current_goal is not None and current_activities:
        current_goal["activity_suggestions"] = "\n".join(current_activities)

    # Save to JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Successfully converted {input_file} to {output_file}")

if __name__ == "__main__":
    # Update to match your specific filenames
    input_filename = "language_workspace_reworked.md"
    output_filename = "language_workspace_reworked.json"
    parse_md_to_json(input_filename, output_filename)
