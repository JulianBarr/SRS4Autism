# UI Reorganization Plan

## Overview
Reorganize the UI to be more structured, consistent, and user-friendly with a widget-based bottom-up design approach.

## 1. Content Categories (Featuring)

### Main Navigation Structure
```
Language Learning
├── Chinese Vocabulary
├── English Vocabulary  
├── Chinese Grammar
├── English Grammar
└── Recommendations

Math
├── Number Concepts
├── Operations
└── Problem Solving

Common Knowledge
├── Science
├── Social Studies
└── General Knowledge

Culture
├── Stories & Characters
├── Traditions
└── Arts
```

## 2. Widget-Based Design System

### Base Widget Component
- Consistent styling
- Reusable across all content types
- Responsive layout
- Color-coded by category

### Widget Types
1. **RecommendationWidget** - Shows learning recommendations
2. **MasteryWidget** - Manages mastered items
3. **ProgressWidget** - Shows learning progress
4. **ContentWidget** - Displays content items
5. **ChatWidget** - Interactive chat (no page refresh)

## 3. Color Coding Scheme

### Category Colors
- **Language**: Blue (#1976d2)
- **Math**: Green (#4CAF50)
- **Common Knowledge**: Orange (#FF9800)
- **Culture**: Purple (#9C27B0)

### Status Colors
- **Mastered**: Green (#4CAF50)
- **In Progress**: Yellow (#FFC107)
- **Not Started**: Gray (#9E9E9E)
- **Recommended**: Blue (#2196F3)

## 4. Account Considerations

### UI Structure (No Auth Required)
- Profile selector at top (if multiple profiles)
- Current profile indicator
- Profile switching without reload
- All data scoped to selected profile

## 5. Interactivity Improvements

### Chat Assistant
- No page refresh on message send
- Real-time message updates
- Optimistic UI updates
- WebSocket or polling for new cards

### Recommendations
- Inline updates
- Smooth transitions
- Loading states
- Error handling without page reload

## 6. Localization Fixes

### Missing Translations
- "Manage Mastered Words" → 管理已掌握词汇
- "Get Word Recommendations" → 获取词汇推荐
- "Manage Mastered Grammar" → 管理已掌握语法
- "Get Grammar Recommendations" → 获取语法推荐
- All button labels
- All status messages
- All form labels

## Implementation Steps

1. Create widget components
2. Create color theme system
3. Reorganize App.js with new navigation
4. Update ProfileManager with widgets
5. Fix ChatAssistant interactivity
6. Add missing translations
7. Test and refine

