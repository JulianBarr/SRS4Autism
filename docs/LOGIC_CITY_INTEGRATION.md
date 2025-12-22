# Logic City Vocabulary Integration Guide

This document describes how to integrate the Logic City Vocabulary Gallery into the CUMA application.

## Backend Implementation

### API Endpoint
- **URL:** `GET /literacy/logic-city`
- **Response:** List of `LogicCityWord` objects with:
  - `english`: English word text
  - `chinese`: Chinese translation (optional)
  - `pinyin`: Pinyin pronunciation (optional)
  - `image_path`: Path to associated image (optional)

### Service Function
The backend queries Fuseki SPARQL endpoint for all words tagged with `srs-kg:learningTheme = "Logic City"`. Images are served via the `/media` static mount.

## Frontend Implementation

### Component Location
`frontend/src/components/widgets/LogicCityGallery.js`

### Integration Options

#### Option 1: Add to MariosWorld (Logic Lab Island)

In `MariosWorld.js`, add a button in the Logic Lab actions section:

```javascript
// Add import at top
import LogicCityGallery from './widgets/LogicCityGallery';

// In the Logic Lab actions section (around line 474), add:
{activeIsland?.id === 'logic' && (
  <button
    onClick={() => {
      setActiveIsland(null);
      onNavigateToContent('logic-city');
    }}
    style={{
      padding: '12px 24px',
      backgroundColor: '#8b5cf6',
      color: 'white',
      border: 'none',
      borderRadius: '12px',
      fontSize: '14px',
      fontWeight: 'bold',
      cursor: 'pointer'
    }}
  >
    {language === 'zh' ? '🏛️ 逻辑城市词汇' : '🏛️ Logic City Vocabulary'}
  </button>
)}
```

#### Option 2: Add as Standalone Page in App.js

In `App.js`, add the component to the content view routing:

```javascript
// Add import at top
import LogicCityGallery from './components/widgets/LogicCityGallery';

// In the render section, add a case for 'logic-city':
{activeContentView === 'logic-city' && (
  <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
    <button
      onClick={() => setActiveContentView(null)}
      style={{
        marginBottom: '16px',
        padding: '8px 16px',
        backgroundColor: '#6b7280',
        color: 'white',
        border: 'none',
        borderRadius: '8px',
        cursor: 'pointer'
      }}
    >
      ← Back
    </button>
    <LogicCityGallery />
  </div>
)}
```

#### Option 3: Direct Integration in MariosWorld

Show the gallery directly when Logic Lab is active:

```javascript
// Add import
import LogicCityGallery from './widgets/LogicCityGallery';

// In the content section (around line 203), add:
{activeIsland?.id === 'logic' && (
  <div style={{ marginTop: '24px' }}>
    <LogicCityGallery />
  </div>
)}
```

## Styling

The component uses the existing theme system (`frontend/src/styles/theme.js`) and `BaseWidget` for consistent styling. Images are displayed in a responsive CSS Grid layout.

## Image Handling

- Images are served from `/media` mount point
- Missing images show a placeholder
- Image paths are converted from KG format (`content/media/images/...`) to URL format (`/media/...`)

## Testing

1. Ensure Fuseki is running with `world_model_complete.ttl` loaded
2. Verify words are tagged with `learningTheme="Logic City"` using the tagging script
3. Test the API endpoint: `curl http://localhost:8000/literacy/logic-city`
4. Verify images are accessible: `curl http://localhost:8000/media/visual_images/[filename]`



