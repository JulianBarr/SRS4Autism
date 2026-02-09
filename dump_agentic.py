import os

def dump_files(directory="agentic", output_file="agentic_context.txt"):
    with open(output_file, "w", encoding="utf-8") as outfile:
        # Walk through the directory
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith(".py") and "__pycache__" not in root:
                    path = os.path.join(root, file)
                    
                    # Write Header
                    outfile.write(f"\n{'='*20}\n")
                    outfile.write(f"FILE: {path}\n")
                    outfile.write(f"{'='*20}\n\n")
                    
                    # Write Content
                    try:
                        with open(path, "r", encoding="utf-8") as infile:
                            outfile.write(infile.read())
                    except Exception as e:
                        outfile.write(f"# Error reading file: {e}\n")
                    
                    outfile.write("\n\n")
    
    print(f"✅ All files from '{directory}/' dumped into '{output_file}'")

if __name__ == "__main__":
    dump_files()
