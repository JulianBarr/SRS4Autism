# Import Instructions for Pinyin Sample Deck

## Important: Audio Files Import

The `.apkg` file **does include all audio files** (verified - 8 audio files are packaged). However, if audio files don't appear after import, try these steps:

### Method 1: Standard Import (Recommended)
1. Open Anki
2. **File → Import**
3. Select `Pinyin_Sample_Deck.apkg`
4. Click **Import**
5. Check if audio files are in Anki's media folder:
   - Go to **Tools → Check Media...**
   - Look for: `a1.mp3`, `a2.mp3`, `a3.mp3`, `a4.mp3`, `a.mp3`, `mo1.mp3`, `mā.mp3`, `mā mā.mp3`

### Method 2: If Audio Files Are Missing After Import

If the audio files don't appear after import, you can manually add them:

1. **Find Anki's media folder:**
   - Go to **Tools → Check Media...**
   - Click **Open Media Folder** button
   - This opens Anki's media directory

2. **Copy audio files manually:**
   - Copy all files from: `/Users/maxent/src/SRS4Autism/media/audio/pinyin/`
   - Paste them into Anki's media folder
   - Files needed:
     - `a1.mp3`
     - `a2.mp3`
     - `a3.mp3`
     - `a4.mp3`
     - `a.mp3`
     - `mo1.mp3`
     - `mā.mp3`
     - `mā mā.mp3`

3. **Verify in Anki:**
   - Go to **Tools → Check Media...**
   - The audio files should now appear

### Verification

After import, verify:
- [ ] Note types are created: "CUMA - Pinyin Element" and "CUMA - Pinyin Syllable"
- [ ] Sample notes appear in deck "拼音学习样本 (Pinyin Sample)"
- [ ] Audio files are accessible (check Tools → Check Media)
- [ ] Images display correctly (ahh.png, mommy.png)
- [ ] Audio playback works when clicking buttons

### Troubleshooting

**If audio doesn't play:**
1. Check that audio files are in Anki's media folder
2. Verify file names match exactly (case-sensitive on some systems)
3. Check Anki's media database: **Tools → Check Media...**
4. Try re-importing the .apkg file

**If templates don't update:**
1. Delete existing note types if they exist
2. Re-import the .apkg file
3. Or manually update templates from the template files

## File Locations

- **.apkg file**: `/Users/maxent/src/SRS4Autism/data/pinyin_sample_deck/Pinyin_Sample_Deck.apkg`
- **Audio files**: `/Users/maxent/src/SRS4Autism/media/audio/pinyin/`
- **Image files**: `/Users/maxent/src/SRS4Autism/media/pinyin/`







