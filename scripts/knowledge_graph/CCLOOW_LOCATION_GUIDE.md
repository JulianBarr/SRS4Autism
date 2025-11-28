# CCLOOW Dataset Location Guide

## Overview
CCLOOW (Chinese Children's Lexicon of Oral Words) is a lexical database for Age of Acquisition (AoA) data for Chinese words, based on animated movies and TV series for children aged 3-9.

**Paper:** Li, L., Zhao, W., Song, M., Wang, J., & Cai, Q. (2023). CCLOOW: Chinese children's lexicon of oral words. *Behavior Research Methods*.

## Potential Sources

### 1. Official Website (May be broken)
- **URL:** https://www.learn2read.cn/ccloow
- **Status:** Link may be broken or require registration
- **Action:** Try accessing directly or contact the website administrators

### 2. Paper Supplementary Materials
- **Paper PDF:** Available at: https://slangscience.github.io/slang/papers/Chinese%20children's%20lexicon%20of%20oral%20words.pdf
- **Action:** Check the paper's supplementary materials section for dataset download links

### 3. Contact Authors Directly
**Authors:**
- Luan Li
- Wentao Zhao
- Ming Song
- Jing Wang
- Qing Cai

**Institution:** Chinese Academy of Sciences (Institute of Psychology)

**Action:** Email the corresponding author (usually listed in the paper) to request the dataset

### 4. Academic Platforms
- **ResearchGate:** Search for the paper or authors
- **Academia.edu:** Check author profiles
- **Google Scholar:** Find the paper and check for dataset links

### 5. Institutional Repositories
- Check the Chinese Academy of Sciences repository
- Check Behavior Research Methods journal supplementary materials

## Alternative Solutions

### Option 1: Use English AoA as Proxy (Already Implemented)
The project already has a fallback mechanism that propagates English AoA to Chinese words via translations:

```bash
python scripts/knowledge_graph/propagate_aoa_to_chinese.py --merge
```

This script:
1. Finds Chinese words with English translations in the KG
2. Looks up AoA for those English words (from Kuperman et al. dataset)
3. Assigns the English AoA to the Chinese words

**Pros:**
- Already implemented and working
- Uses existing English AoA data (Kuperman et al.)
- No need to wait for CCLOOW

**Cons:**
- Less accurate than native Chinese AoA data
- Only works for words with English translations
- May not reflect actual Chinese children's acquisition patterns

### Option 2: Manual Data Collection
If CCLOOW is unavailable, you could:
1. Extract AoA data from the paper's tables/appendices
2. Use frequency data from SUBTLEX-CH as a proxy (higher frequency ≈ lower AoA)
3. Use MELD-SCH concreteness as a proxy (more concrete ≈ lower AoA)

### Option 3: Wait and Use Fallback
1. Continue using the English AoA propagation for now
2. Keep trying to obtain CCLOOW
3. When available, run the integration script

## Integration Script

Once you have the CCLOOW dataset (CSV or TSV format), use:

```bash
python scripts/knowledge_graph/integrate_chinese_metadata.py \
    --ccloow-file /path/to/CCLOOW.csv \
    --merge
```

The script expects a file with columns:
- `Word` (or `word`): Chinese word
- `AoA` (or `aoa`, `Age`, `age`, `AgeOfAcquisition`): Age of acquisition in years

## Recommended Next Steps

1. **Try the official website:** https://www.learn2read.cn/ccloow
2. **Check the paper PDF** for supplementary materials links
3. **Use the fallback** (`propagate_aoa_to_chinese.py`) for immediate functionality
4. **Contact authors** if you need the native Chinese AoA data
5. **Proceed with MELD-SCH** (concreteness) integration, which doesn't depend on CCLOOW

## Current Status

- ✅ SUBTLEX-CH (Frequency): **Integrated** (20,813 words updated)
- ⏳ MELD-SCH (Concreteness): **Pending** (need dataset file)
- ⏳ CCLOOW (AoA): **Pending** (link broken, use fallback for now)


