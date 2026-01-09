import os
import shutil

# --- CONFIGURATION ---
# Path to your downloaded mp3 folder (from your screenshot)
SOURCE_DIR = "/Users/maxent/src/mp3-chinese-pinyin-sound/mp3"

# Path to Anki Media folder (Default location on macOS)
# Check if your profile is "User 1" or something else
ANKI_MEDIA_DIR = os.path.expanduser("~/Library/Application Support/Anki2/CUMA_Test/collection.media")

def main():
    if not os.path.exists(SOURCE_DIR):
        print(f"Error: Source directory not found: {SOURCE_DIR}")
        return

    if not os.path.exists(ANKI_MEDIA_DIR):
        print(f"Error: Anki media directory not found: {ANKI_MEDIA_DIR}")
        return

    count = 0
    print(f"Copying from: {SOURCE_DIR}")
    print(f"Copying to:   {ANKI_MEDIA_DIR}")
    print("-" * 50)

    for filename in os.listdir(SOURCE_DIR):
        if filename.endswith(".mp3"):
            # 1. Define source file path
            src_file = os.path.join(SOURCE_DIR, filename)
            
            # 2. Define new filename with underscore prefix
            new_filename = "_" + filename
            dst_file = os.path.join(ANKI_MEDIA_DIR, new_filename)

            # 3. Copy file
            try:
                shutil.copy2(src_file, dst_file)
                # Optional: Print every file (can be spammy if 1000s of files)
                # print(f"Copied: {filename} -> {new_filename}")
                count += 1
            except Exception as e:
                print(f"Failed to copy {filename}: {e}")

    print("-" * 50)
    print(f"✅ Success! Copied and renamed {count} files.")

if __name__ == "__main__":
    main()
