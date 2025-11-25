# Learning Frontier Recommendation Algorithm

## Overview

The recommendation algorithm automatically determines the optimal HSK level to focus on based on the child's current mastery rates, then suggests words at that "learning frontier."

## How It Works

### 1. Dynamic Target Level Detection

The algorithm:
1. Queries the knowledge graph for mastery rates by HSK level
2. Finds the **"learning frontier"** - the first level where mastery < 50%
3. Sets that level as the `target_level` for recommendations

**Example:**
- HSK 1: 29.7% mastered → Learning frontier!
- HSK 2: 20.1% mastered
- HSK 3: 15.3% mastered
- etc.

**Result:** `target_level = 1` (because HSK 1 is the first level with < 50% mastery)

### 2. Learning Frontier Algorithm

Words are scored based on:
- **HSK Level Priority:**
  - Target level: +100 points (highest priority)
  - Next level (target + 1): +50 points (medium priority)
  - Too hard (> target + 1): -500 points (penalized)
  - No HSK level: +10 points (small baseline)

- **Character Composition:**
  - Each known character adds 50 points * (ratio of known chars)
  - Example: 2/2 chars known = +50 points
  - Example: 1/3 chars known = +16.7 points

**Example Scoring:**
```
Word: 前天 (day before yesterday, HSK 1)
- HSK 1 (target): +100 points
- Known chars: 2/2: +50 points
- Total: 150 points ✅

Word: 小说 (novel, HSK 5)
- HSK 5 (> target + 1): -500 points
- Known chars: 1/2: +25 points
- Total: -475 points ❌ (too hard)
```

### 3. Final Recommendations

- Top 20 words by score
- Sorted by score (highest first)
- Only words with positive scores are included

---

## Current Configuration

**Profile:** Zhou Yiming (周一鸣）  
**Total Mastered:** 2,423 words

**Mastery Rates:**
- HSK 1: 29.7% (144/506) ← **Learning Frontier**
- HSK 2: 20.1% (151/750)
- HSK 3: 15.3% (146/953)
- HSK 4: 15.2% (148/972)
- HSK 5: 13.6% (144/1,059)
- HSK 6: 10.1% (113/1,123)
- HSK 7: 6.3% (351/5,606)

**Current Recommendations:** HSK 1 words

---

## Example Recommendations

Based on current mastery:

1. **前天** (qián tiān) - HSK 1, Score: 150.0, Chars: 2/2
2. **好听** (hǎo tīng) - HSK 1, Score: 150.0, Chars: 2/2
3. **马路** (mǎ lù) - HSK 1, Score: 150.0, Chars: 2/2
4. **好吃** (hǎo chī) - HSK 1, Score: 150.0, Chars: 2/2
5. **好看** (hǎo kàn) - HSK 1, Score: 150.0, Chars: 2/2

---

## Why No HSK 2 Words?

**Answer:** HSK 1 is the current learning frontier (29.7% mastered)!

As the child learns more HSK 1 words:
- When HSK 1 mastery reaches 50%, the frontier moves to HSK 2
- Recommendations will automatically shift to HSK 2 words

This ensures the child always learns at the optimal level - not too easy (already mastered), not too hard (premature).

---

## Algorithm Benefits

✅ **Adaptive:** Automatically adjusts as vocabulary grows  
✅ **Optimal:** Focuses on the current learning frontier  
✅ **Character-based:** Prioritizes words with known components  
✅ **Progressive:** Builds foundations before advancing  
✅ **Dynamic:** No manual configuration needed

---

*Last Updated: Based on current vocabulary mastery analysis*

