# Debugging "Sync to Anki" Button

## Why Nothing Happens When You Click "Sync to Anki"

The button might be **disabled** or the **workflow isn't complete**. Here's how to use it:

## ✅ Correct Workflow

### Step 1: Generate Cards
1. Go to **Chat Assistant** tab
2. Type: "Create flashcards about colors"
3. Click **Send**
4. Cards will be generated

### Step 2: Approve Cards
1. Go to **Card Curation** tab
2. Scroll to **Pending Cards** section
3. **Check the boxes** next to cards you want
4. Click **"Approve Selected"** button
5. Cards move to **Approved Cards** section

### Step 3: Sync to Anki
1. In **Card Curation** tab
2. Select **Anki Profile** from dropdown (e.g., "Default")
3. **Check the boxes** next to approved cards
4. Click **"Sync to Anki"** button
5. Cards will be added to Anki!

## Why the Button Might Be Disabled

The "Sync to Anki" button is disabled when:

1. ❌ **No cards selected** - You must check the checkboxes
2. ❌ **No Anki profile selected** - Choose from the dropdown
3. ❌ **Cards not approved** - Must approve cards first

## Check Browser Console

Open browser DevTools (F12 or Cmd+Option+I) and check:

1. **Console tab** - Look for these messages:
   ```
   🔵 Sync to Anki clicked!
   Selected profile: Default
   Selected cards: [...]
   Cards to sync: [...]
   ```

2. **Network tab** - Look for POST to `/anki/sync`

## Test AnkiConnect

### From Terminal:
```bash
curl http://localhost:8000/anki/test
```

Should return:
```json
{
  "status": "connected",
  "message": "AnkiConnect is running",
  "decks": ["Default", ...]
}
```

### From Python:
```bash
cd anki_integration
python anki_connect.py
```

Should show:
```
✅ Connected to AnkiConnect successfully!
Available decks: [...]
```

## Common Issues

### Issue 1: Button is Grayed Out
**Cause:** Button is disabled
**Solution:** 
- Select an Anki profile from dropdown
- Check card checkboxes
- Approve cards first

### Issue 2: "Please select approved cards"
**Cause:** Selected cards are still "pending" status
**Solution:**
1. Select cards in Pending section
2. Click "Approve Selected"
3. Then select them again in Approved section
4. Click "Sync to Anki"

### Issue 3: "Cannot connect to Anki"
**Cause:** AnkiConnect not running
**Solution:**
1. Open Anki application
2. Install AnkiConnect add-on (code: 2055492159)
3. Restart Anki
4. Keep Anki running

## Debug Mode

To see what's happening:

1. **Open Browser Console** (F12 or Cmd+Option+I)
2. **Click "Sync to Anki"**
3. **Look for console logs**:
   - 🔵 Button clicked
   - ❌ Validation errors
   - ✅ API responses

## Quick Test

Try this to test the full workflow:

1. **Chat tab**: "Create flashcards about animals"
2. **Curation tab**: 
   - Check all pending cards
   - Click "Approve Selected"
3. **Still in Curation tab**:
   - Select "Default" from Anki Profile dropdown
   - Check approved cards
   - Click "Sync to Anki"
4. **Check Anki**: Open "SRS4Autism" deck

## Backend Logs

Check the backend terminal for:
```
🤖 SENDING TO GEMINI: ...
✨ GEMINI RESPONSE: ...
POST /anki/sync ...
```

If you see errors, they'll show here!

