# Chinese Word Metadata Integration

This document describes how to integrate Chinese word metadata from three key datasets into the knowledge graph for PPR-based recommendations.

## Datasets

### 1. SUBTLEX-CH (Frequency Data)
**Purpose:** Word frequency rankings based on film and TV subtitles (spoken language)

**Download:**
- **Official Source:** [SUBTLEX-CH Database](https://www.ugent.be/pp/experimentele-psychologie/en/research/documents/subtlexch)
- **Alternative:** Search for "SUBTLEX-CH" on academic databases
- **Format:** Tab-separated or CSV file with columns: `Word`, `Freq`, `CD`, `FreqCD`, etc.

**Usage:**
```bash
python scripts/knowledge_graph/integrate_chinese_metadata.py \
    --sublex-file /path/to/SUBTLEX-CH.txt \
    --merge
```

### 2. MELD-SCH (Concreteness Ratings)
**Purpose:** Concreteness/abstractness ratings for Chinese words (critical for filtering abstract concepts)

**Download:**
- **Official Source:** [MELD-SCH Database](https://github.com/lingfeat/MELD-SCH) or search academic databases
- **Format:** CSV file with columns: `Word`, `Concreteness` (1-7 scale, will be normalized to 1-5)
- **Coverage:** ~9,877 two-character Chinese words

**Usage:**
```bash
python scripts/knowledge_graph/integrate_chinese_metadata.py \
    --meld-file /path/to/MELD-SCH.csv \
    --merge
```

### 3. CCLOOW (Age of Acquisition)
**Purpose:** Age of Acquisition data for Chinese words (when Chinese children learn words)

**Download:**
- **Official Source:** Search for "CCLOOW" or "Chinese Children's Lexicon of Oral Words" on academic databases
- **Format:** CSV file with columns: `Word`, `AoA` (in years)
- **Note:** If not available, the system can fallback to English AoA via `propagate_aoa_to_chinese.py`

**Usage:**
```bash
python scripts/knowledge_graph/integrate_chinese_metadata.py \
    --ccloow-file /path/to/CCLOOW.csv \
    --merge
```

## Complete Integration

To integrate all three datasets at once:

```bash
python scripts/knowledge_graph/integrate_chinese_metadata.py \
    --sublex-file /path/to/SUBTLEX-CH.txt \
    --meld-file /path/to/MELD-SCH.csv \
    --ccloow-file /path/to/CCLOOW.csv \
    --merge
```

## Options

- `--merge`: Merge with `world_model_merged.ttl` instead of `world_model_cwn.ttl`
- `--skip-existing`: Skip words that already have metadata (prevents overwriting)
- `--output`: Specify custom output file path

## What Gets Updated

The script updates Chinese words in the knowledge graph with:

1. **Frequency Rank** (`srs-kg:frequencyRank`): From SUBTLEX-CH
   - Lower rank = more frequent
   - Used for prioritizing common words

2. **Concreteness** (`srs-kg:concreteness`): From MELD-SCH
   - Scale: 1-5 (normalized from 1-7 if needed)
   - Higher = more concrete = easier for beginners
   - Used for filtering abstract concepts

3. **Age of Acquisition** (`srs-kg:ageOfAcquisition`): From CCLOOW
   - Value in years (e.g., 3.5 = learned at age 3.5)
   - Used for filtering words too advanced for mental age
   - Fallback: English AoA via `propagate_aoa_to_chinese.py` if CCLOOW unavailable

## Data Format Requirements

The script is flexible and tries to auto-detect:
- **Delimiter:** Tab (`\t`) or comma (`,`)
- **Column names:** Tries common variations:
  - Frequency: `Word`, `word`, `Freq`, `frequency`, `FreqCD`
  - Concreteness: `Word`, `word`, `Concreteness`, `concreteness`, `Conc`, `Rating`
  - AoA: `Word`, `word`, `AoA`, `aoa`, `Age`, `age`, `AgeOfAcquisition`

## After Integration

Once metadata is integrated:

1. **Build similarity graph:**
   ```bash
   python scripts/knowledge_graph/build_chinese_word_similarity.py
   ```

2. **Adapt PPR service** to support Chinese words (similar to English)

3. **Test recommendations** with Chinese words

## Notes

- The script normalizes Chinese words by removing spaces and punctuation
- Only words with Chinese characters (Unicode range \u4e00-\u9fff) are processed
- Existing metadata is preserved unless `--skip-existing` is used
- A backup is automatically created before saving


