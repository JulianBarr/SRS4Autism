# Interactive Cloze Note Type Setup Guide

This guide will help you set up the Interactive Cloze note type in Anki to display images and interactive blanks.

## Prerequisites

- Anki desktop app installed
- AnkiConnect add-on installed

## Step-by-Step Setup

### 1. Create the Note Type

1. Open Anki
2. Click **Tools** → **Manage Note Types**
3. Click **Add**
4. Select **Add: Basic** (we'll customize it)
5. Name it: `Interactive Cloze`
6. Click **OK**

### 2. Add Fields

1. With "Interactive Cloze" selected, click **Fields...**
2. You should see: `Front` and `Back`
3. **Rename** `Front` to `Text`
4. **Rename** `Back` to `Extra`
5. Click **Save**

### 3. Edit Card Templates

1. Click **Cards...**
2. You'll see three sections: **Front Template**, **Styling**, **Back Template**

#### A. Front Template

**Delete everything** and paste this:

```html
<!-- Interactive Cloze Card - Front Template -->
<div class="card interactive-cloze">
  <div class="content">
    {{Text}}
  </div>
  
  {{#Extra}}
  <div class="extra">
    {{Extra}}
  </div>
  {{/Extra}}
  
  <div class="controls">
    <button id="showAll" class="show-all-btn">Show All</button>
  </div>
</div>

<script>
// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', function() {
  // Get the text content from the Text field
  const contentDiv = document.querySelector('.content');
  if (!contentDiv) return;
  
  // Get the raw HTML content (includes images)
  let html = contentDiv.innerHTML;
  
  // Replace [[c1::answer]] with clickable blanks
  let counter = 1;
  html = html.replace(/\[\[c(\d+)::([^\]]+)\]\]/g, function(match, num, answer) {
    return `<span class="cloze-blank" data-answer="${answer}" data-num="${num}">[...]</span>`;
  });
  
  // Update the content with the processed HTML
  contentDiv.innerHTML = html;
  
  // Add click handlers to blanks
  const blanks = document.querySelectorAll('.cloze-blank');
  blanks.forEach(blank => {
    blank.addEventListener('click', function() {
      if (!this.classList.contains('revealed')) {
        this.textContent = this.getAttribute('data-answer');
        this.classList.add('revealed');
      }
    });
  });
  
  // Show all button
  const showAllBtn = document.getElementById('showAll');
  if (showAllBtn) {
    showAllBtn.addEventListener('click', function(e) {
      e.preventDefault();
      blanks.forEach(blank => {
        if (!blank.classList.contains('revealed')) {
          blank.textContent = blank.getAttribute('data-answer');
          blank.classList.add('revealed');
        }
      });
    });
  }
});
</script>
```

#### B. Styling

**Delete everything** and paste the CSS from `Interactive_Cloze_Styling.css`

**CRITICAL:** Make sure this section includes:
```css
/* Image styling - CRITICAL for showing pasted images */
.content img,
.extra img {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 15px 0;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
```

#### C. Back Template

**Delete everything** and paste this:

```html
<!-- Interactive Cloze Card - Back Template -->
{{FrontSide}}

<hr id="answer">

<div class="back-content">
  <p style="color: #28a745; font-weight: bold;">All answers revealed!</p>
</div>
```

### 4. Save and Test

1. Click **Save**
2. Close the template editor
3. Close "Manage Note Types"
4. **Restart Anki** (important!)

### 5. Verify Setup

1. Go to your SRS4Autism frontend
2. Generate a card with `@notetype:Interactive_Cloze`
3. Edit the card and paste an image
4. Sync to Anki
5. Open Anki and check the card
6. **Images should now display!** ✓

## How It Works

### Text Field Format

```
Captain Jack Sparrow decided to [[c1::banish]] the traitor from his ship.

杰克·斯派罗船长决定把叛徒逐出他的船。

[Image of Jack Sparrow pasted here]
```

### What Happens

1. **HTML Content**: The `{{Text}}` field renders HTML, including `<img>` tags
2. **JavaScript Processing**: Converts `[[c1::answer]]` to clickable blanks
3. **CSS Styling**: Makes images responsive and beautiful
4. **Interactive Blanks**: Click to reveal, or click "Show All"

## Troubleshooting

### Images Don't Show

**Check:**
1. Is the CSS section in the template?
2. Did you restart Anki after editing templates?
3. Is the image embedded as base64 data URL? (It should be from our app)

**Verify in Anki:**
1. Browse → Select a card
2. Click **Cards** button
3. Check if `<img src="data:image/...">` is in the HTML

### Blanks Don't Work

**Check:**
1. Is the JavaScript in the Front Template?
2. Did you save and close the template editor?
3. Are you using `[[c1::word]]` syntax (double brackets)?

## Features

✅ **Images from clipboard** - Pasted images display perfectly  
✅ **Interactive blanks** - Click to reveal answers  
✅ **Chinese + English** - Full bilingual support  
✅ **Responsive** - Works on desktop and mobile  
✅ **Beautiful styling** - Professional card design  

## Example Card

**Input (Text field):**
```html
The pirate captain decided to [[c1::banish]] the traitor.

海盗船长决定[[c1::驱逐]]叛徒。

<img src="data:image/png;base64,iVBORw0KG...">
```

**Result:**
- Image displays at top
- English sentence with clickable `[...]` blank
- Chinese sentence with clickable `[...]` blank
- Click blank → reveals "banish" or "驱逐"
- Click "Show All" → reveals all answers

---

**Done!** Your Interactive Cloze cards now support images! 🎉

