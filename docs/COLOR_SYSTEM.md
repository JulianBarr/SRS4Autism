# Color System Design

## Overview
This document defines a consistent color coding scheme for the SRS4Autism application to improve visual consistency and user experience.

## Color Philosophy

### Semantic Colors
Colors should have **semantic meaning** that users can learn and recognize:
- **Primary Actions** (Blue): Main actions, navigation, links
- **Success/Positive** (Green): Approve, save, mastered, completed
- **Warning/Caution** (Orange/Yellow): Pending, in-progress, needs attention
- **Danger/Destructive** (Red): Delete, error, critical actions
- **Neutral/Secondary** (Gray): Secondary actions, disabled states, borders

## Color Palette

### Primary Actions (Blue)
- **Primary Blue**: `#1976d2` (Material Blue 700)
- **Light Blue**: `#64B5F6` (Material Blue 300)
- **Dark Blue**: `#0D47A1` (Material Blue 900)
- **Background**: `#E3F2FD` (Material Blue 50)

**Usage:**
- Active tab navigation
- Primary buttons (Send, Sync, Generate)
- Links and interactive elements
- Category: Language

### Success/Positive (Green)
- **Primary Green**: `#4CAF50` (Material Green 500)
- **Light Green**: `#81C784` (Material Green 300)
- **Dark Green**: `#2E7D32` (Material Green 800)
- **Background**: `#E8F5E9` (Material Green 50)

**Usage:**
- Approve buttons
- Mastered status indicators
- Success messages
- Category: Math
- Completed/achieved states

### Warning/Caution (Orange/Yellow)
- **Primary Orange**: `#FF9800` (Material Orange 500)
- **Light Orange**: `#FFB74D` (Material Orange 300)
- **Dark Orange**: `#E65100` (Material Orange 900)
- **Background**: `#FFF3E0` (Material Orange 50)

**Usage:**
- Pending status
- In-progress indicators
- "Already mastered" badges (warning that item is already known)
- Category: Common Knowledge
- Caution messages

### Danger/Destructive (Red)
- **Primary Red**: `#F44336` (Material Red 500)
- **Light Red**: `#EF5350` (Material Red 400)
- **Dark Red**: `#C62828` (Material Red 800)
- **Background**: `#FFEBEE` (Material Red 50)

**Usage:**
- Delete buttons
- Error messages
- Critical warnings
- Destructive actions

### Neutral/Secondary (Gray)
- **Primary Gray**: `#757575` (Material Gray 600)
- **Light Gray**: `#BDBDBD` (Material Gray 400)
- **Dark Gray**: `#424242` (Material Gray 800)
- **Background**: `#F5F5F5` (Material Gray 100)
- **Border**: `#E0E0E0` (Material Gray 300)

**Usage:**
- Secondary buttons
- Disabled states
- Borders and dividers
- Placeholder text
- Background surfaces

### Info/Recommended (Cyan/Blue)
- **Primary Cyan**: `#2196F3` (Material Blue 500)
- **Light Cyan**: `#64B5F6` (Material Blue 300)
- **Background**: `#E0F7FA` (Material Cyan 50)

**Usage:**
- Information messages
- Recommended items
- Info badges

### Culture (Purple)
- **Primary Purple**: `#9C27B0` (Material Purple 500)
- **Light Purple**: `#BA68C8` (Material Purple 300)
- **Dark Purple**: `#6A1B9A` (Material Purple 800)
- **Background**: `#F3E5F5` (Material Purple 50)

**Usage:**
- Category: Culture

## Action Button Colors

### Primary Actions
- **Send Message**: Blue (`#1976d2`)
- **Sync to Anki**: Blue (`#1976d2`)
- **Generate Image**: Blue (`#1976d2`)
- **Get Recommendations**: Blue (`#1976d2`)

### Positive Actions
- **Approve**: Green (`#4CAF50`)
- **Save**: Green (`#4CAF50`)
- **Add to Mastered**: Green (`#4CAF50`)

### Destructive Actions
- **Delete**: Red (`#F44336`)
- **Remove**: Red (`#F44336`)

### Secondary Actions
- **Edit**: Gray (`#757575`)
- **Cancel**: Gray (`#757575`)
- **Select All/Deselect**: Gray (`#757575`)
- **Clear History**: Gray (`#757575`)

## Status Colors

### Card Status
- **Pending**: Orange (`#FF9800`) with yellow background (`#FFF3E0`)
- **Approved**: Green (`#4CAF50`) with light green background (`#E8F5E9`)
- **Synced**: Blue (`#2196F3`) with light blue background (`#E3F2FD`)

### Learning Status
- **Mastered**: Green (`#4CAF50`)
- **In Progress**: Yellow (`#FFC107`)
- **Not Started**: Gray (`#9E9E9E`)
- **Recommended**: Blue (`#2196F3`)
- **Already Mastered** (warning): Orange (`#FF9800`)

## Text Colors

### Primary Text
- **Main Content**: `#212121` (almost black)
- **Headings**: `#212121`

### Secondary Text
- **Labels**: `#757575` (gray)
- **Hints**: `#9E9E9E` (light gray)
- **Disabled**: `#BDBDBD` (very light gray)

## Implementation Guidelines

### 1. Use Theme File
Always import and use colors from `theme.js` instead of hard-coding hex values.

**Bad:**
```javascript
style={{ backgroundColor: '#4CAF50', color: 'white' }}
```

**Good:**
```javascript
import theme from '../styles/theme';
style={{ backgroundColor: theme.status.success, color: 'white' }}
```

### 2. Semantic Naming
Use semantic names that describe the purpose, not the color:
- `theme.actions.primary` (not `theme.colors.blue`)
- `theme.status.success` (not `theme.colors.green`)
- `theme.status.warning` (not `theme.colors.orange`)

### 3. Consistent Button Styles
Create reusable button components with consistent styling:
- Primary buttons: Blue background, white text
- Success buttons: Green background, white text
- Danger buttons: Red background, white text
- Secondary buttons: Gray background, dark text

### 4. Status Indicators
Use consistent colors for status:
- Pending = Orange
- Approved/Success = Green
- Error/Danger = Red
- Info = Blue

### 5. Category Colors
Each content category has its own color:
- Language: Blue
- Math: Green
- Common Knowledge: Orange
- Culture: Purple

## Migration Plan

1. **Phase 1**: Update `theme.js` with comprehensive color system
2. **Phase 2**: Create reusable button components
3. **Phase 3**: Refactor components to use theme colors
4. **Phase 4**: Update CSS classes to use theme variables

## Examples

### Button Component
```javascript
<Button variant="primary">Send</Button>
<Button variant="success">Approve</Button>
<Button variant="danger">Delete</Button>
<Button variant="secondary">Cancel</Button>
```

### Status Badge
```javascript
<Badge status="pending">Pending</Badge>
<Badge status="approved">Approved</Badge>
<Badge status="synced">Synced</Badge>
```

