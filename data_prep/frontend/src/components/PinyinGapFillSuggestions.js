import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8001';
// Main backend for operations that require database access (like applying suggestions)
const MAIN_API_BASE = process.env.REACT_APP_MAIN_API_URL || 'http://localhost:8000';

/**
 * Normalize pinyin to ensure spaces between syllables.
 * Handles cases where pinyin might come without spaces or with inconsistent formatting.
 * Format: "bàn tiān" (space between syllables)
 * 
 * Examples:
 * - "dàlóu" -> "dà lóu"
 * - "gōnglù" -> "gōng lù"
 * - "bàntiān" -> "bàn tiān"
 */
const normalizePinyin = (pinyin) => {
  if (!pinyin || typeof pinyin !== 'string') return '';
  
  // Remove extra whitespace and normalize
  let normalized = pinyin.trim().replace(/\s+/g, ' ');
  
  // If pinyin doesn't have spaces, try to add them between syllables
  if (!normalized.includes(' ')) {
    // Tone marks: ā, á, ǎ, à, ē, é, ě, è, ī, í, ǐ, ì, ō, ó, ǒ, ò, ū, ú, ǔ, ù, ǖ, ǘ, ǚ, ǜ
    // Syllable pattern: (optional initial) + final with tone mark
    // Split after tone marks when followed by a consonant or certain vowels
    
    // First, handle numeric tones (e.g., "da4lou2" -> "da4 lou2")
    normalized = normalized.replace(/([a-zü]+[1-5])([a-zü])/gi, '$1 $2');
    
    // Then handle tone marks - split after tone mark when followed by consonant that starts new syllable
    // Be careful: 'n' and 'ng' can be part of finals (an, en, ang, eng, ong, etc.)
    // Also be careful: 'o', 'u', 'i' can be part of finals (ao, ou, ai, ei, etc.)
    // Pattern: tone mark followed by consonant (but check if it's part of final first)
    normalized = normalized.replace(/([āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ])([a-zü]+)/gi, (match, toneMark, afterTone) => {
      // Common finals that should NOT be split: ao, ou, ai, ei, an, en, ang, eng, ong, etc.
      // Check if the character after tone mark is part of a valid final
      const validFinals = /^(ao|ou|ai|ei|an|en|ang|eng|ong|ia|iao|ian|iang|iong|ua|uo|uai|ui|uan|uang|un|üe|üan|ün|er)/i;
      if (validFinals.test(afterTone)) {
        // This is part of the same syllable's final, don't split
        return match;
      }
      
      // Check if tone mark vowel + afterTone forms a valid final
      // This handles cases like "kēng" where tone is on 'e' and 'ng' follows
      const toneMarkVowel = toneMark.toLowerCase().replace(/[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]/g, (m) => {
        const map = {'ā':'a','á':'a','ǎ':'a','à':'a','ē':'e','é':'e','ě':'e','è':'e',
                     'ī':'i','í':'i','ǐ':'i','ì':'i','ō':'o','ó':'o','ǒ':'o','ò':'o',
                     'ū':'u','ú':'u','ǔ':'u','ù':'u','ǖ':'ü','ǘ':'ü','ǚ':'ü','ǜ':'ü'};
        return map[m] || m;
      });
      
      // Check if tone mark vowel + afterTone forms a complete valid final
      // This handles cases like "kēng" (ē + ng = eng) or "bǎo" (ǎ + o = ao)
      const potentialFinal = toneMarkVowel + afterTone.toLowerCase();
      const validFinalsWithTone = /^(ang|eng|ong|an|en|ao|ou|ai|ei|ia|iao|ian|iang|iong|ua|uo|uai|ui|uan|uang|un|üe|üan|ün|er)$/i;
      
      // If it's a complete valid final (ends the syllable), don't split
      if (validFinalsWithTone.test(potentialFinal)) {
        return match;
      }
      
      // Special case: if afterTone starts with 'ng' or 'n' followed by a consonant
      // This means 'ng'/'n' ends the current syllable and the consonant starts a new one
      // Example: "kēngbǎo" -> "kēng bǎo" (ng ends first syllable, b starts second)
      if (afterTone.match(/^ng?[bpmfdtnlgkhjqxzcsrzhchshyw]/i)) {
        // Check if 'ng'/'n' is part of a valid final by checking the tone mark vowel
        // If tone is on a/e/o and followed by ng, it's likely ang/eng/ong (valid final)
        // But if ng is followed by a consonant, that consonant starts a new syllable
        const ngMatch = afterTone.match(/^(ng?)([bpmfdtnlgkhjqxzcsrzhchshyw].*)/i);
        if (ngMatch) {
          // Check if this forms a valid final (ang, eng, ong, an, en)
          const ngFinal = toneMarkVowel + ngMatch[1].toLowerCase();
          const validFinalsWithNg = /^(ang|eng|ong|an|en)/i;
          if (validFinalsWithNg.test(ngFinal)) {
            // Valid final, but ng is followed by consonant, so split
            return toneMark + ngMatch[1] + ' ' + ngMatch[2];
          }
        }
      }
      
      // If after tone mark starts with consonant (not 'n' which might be part of final)
      // Check for common syllable-starting consonants
      const syllableStarters = /^[bpmfdtnlgkhjqxzcsrzhchshyw]/i;
      
      // If starts with consonant (and not 'n' or 'ng'), split
      if (syllableStarters.test(afterTone) && !afterTone.match(/^n/i)) {
        return toneMark + ' ' + afterTone;
      }
      
      // Don't split on single vowels after tone marks - they're likely part of the final
      // Only split if it's clearly a new syllable (consonant or capital letter)
      
      return match;
    });
    
    // Also handle capital letters (e.g., "Biébie" -> "Bié bie")
    normalized = normalized.replace(/([āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ])([A-Z])/g, '$1 $2');
    
    // Clean up extra spaces
    normalized = normalized.replace(/\s+/g, ' ').trim();
  }
  
  // Ensure consistent spacing: exactly one space between syllables
  normalized = normalized.replace(/\s+/g, ' ').trim();
  
  return normalized;
};

/**
 * Convert numbered pinyin to tone-marked pinyin
 * Example: "hua1 bao4" -> "huā bào"
 */
const convertNumberedPinyinToToneMarks = (pinyin) => {
  if (!pinyin || typeof pinyin !== 'string') return pinyin;
  
  // Tone mark maps: vowel -> [tone1, tone2, tone3, tone4]
  const TONE_MARKS = {
    'a': ['ā', 'á', 'ǎ', 'à'],
    'o': ['ō', 'ó', 'ǒ', 'ò'],
    'e': ['ē', 'é', 'ě', 'è'],
    'i': ['ī', 'í', 'ǐ', 'ì'],
    'u': ['ū', 'ú', 'ǔ', 'ù'],
    'ü': ['ǖ', 'ǘ', 'ǚ', 'ǜ'],
    'A': ['Ā', 'Á', 'Ǎ', 'À'],
    'O': ['Ō', 'Ó', 'Ǒ', 'Ò'],
    'E': ['Ē', 'É', 'Ě', 'È'],
    'I': ['Ī', 'Í', 'Ǐ', 'Ì'],
    'U': ['Ū', 'Ú', 'Ǔ', 'Ù'],
    'Ü': ['Ǖ', 'Ǘ', 'Ǚ', 'Ǜ']
  };
  
  // Split by spaces and process each syllable
  return pinyin.split(/\s+/).map(syllable => {
    // Extract tone number (1-4) from end of syllable
    const toneMatch = syllable.match(/([1-4])$/);
    if (!toneMatch) {
      return syllable; // No tone number, return as is
    }
    
    const tone = parseInt(toneMatch[1]);
    const syllableWithoutTone = syllable.slice(0, -1);
    const syllableLower = syllableWithoutTone.toLowerCase();
    
    // Special case: i and u together (i u 并列标在后)
    // For 'iu', tone goes on 'u' (the second one)
    // For 'ui', tone goes on 'i' (the second one)
    if (syllableLower.includes('iu')) {
      const mark = TONE_MARKS['u'][tone - 1];
      if (mark) {
        // Find position of 'iu' and replace 'u' with tone mark
        const iuIndex = syllableLower.indexOf('iu');
        const uIndex = iuIndex + 1;
        const beforeU = syllableWithoutTone.substring(0, uIndex);
        const afterU = syllableWithoutTone.substring(uIndex + 1);
        // Preserve case
        const uChar = syllableWithoutTone[uIndex];
        const markToUse = uChar === 'U' ? TONE_MARKS['U'][tone - 1] : mark;
        return beforeU + markToUse + afterU;
      }
    } else if (syllableLower.includes('ui')) {
      const mark = TONE_MARKS['i'][tone - 1];
      if (mark) {
        // Find position of 'ui' and replace 'i' with tone mark
        const uiIndex = syllableLower.indexOf('ui');
        const iIndex = uiIndex + 1;
        const beforeI = syllableWithoutTone.substring(0, iIndex);
        const afterI = syllableWithoutTone.substring(iIndex + 1);
        // Preserve case
        const iChar = syllableWithoutTone[iIndex];
        const markToUse = iChar === 'I' ? TONE_MARKS['I'][tone - 1] : mark;
        return beforeI + markToUse + afterI;
      }
    }
    
    // Regular priority order: a > o > e > i > u > ü
    const vowels_priority = ['a', 'o', 'e', 'i', 'u', 'ü', 'A', 'O', 'E', 'I', 'U', 'Ü'];
    
    for (const vowel of vowels_priority) {
      if (syllableWithoutTone.includes(vowel)) {
        const mark = TONE_MARKS[vowel.toLowerCase()][tone - 1];
        if (mark) {
          // Replace first occurrence of vowel with tone mark (preserve case)
          const vowelIndex = syllableWithoutTone.indexOf(vowel);
          if (vowelIndex !== -1) {
            const beforeVowel = syllableWithoutTone.substring(0, vowelIndex);
            const afterVowel = syllableWithoutTone.substring(vowelIndex + 1);
            // Preserve case: if vowel is uppercase, use uppercase mark
            const markToUse = (vowel === vowel.toUpperCase() && TONE_MARKS[vowel] && TONE_MARKS[vowel][tone - 1]) 
              ? TONE_MARKS[vowel][tone - 1] 
              : mark;
            return beforeVowel + markToUse + afterVowel;
          }
        }
      }
    }
    
    // No vowel found to mark, return original without tone number
    return syllableWithoutTone;
  }).join(' ');
};

/**
 * Image preview component for English vocab suggestions
 */
const EnglishVocabImagePreview = ({ englishWord }) => {
  const [imageFile, setImageFile] = useState(null);
  
  useEffect(() => {
    // Fetch the actual image filename from backend
    axios.get(`${API_BASE}/pinyin/find-image-by-english-word`, {
      params: { english_word: englishWord },
      timeout: 2000
    })
    .then(response => {
      if (response.data.image_file) {
        setImageFile(response.data.image_file);
      }
    })
    .catch(() => {
      // Image not found - that's ok
    });
  }, [englishWord]);
  
  if (!imageFile) return null;
  
  return (
    <img
      src={`${API_BASE}/media/pinyin/${imageFile}`}
      alt={englishWord}
      style={{
        width: '24px',
        height: '24px',
        objectFit: 'cover',
        borderRadius: '2px',
        display: 'block'
      }}
      onError={(e) => { e.target.style.display = 'none'; }}
    />
  );
};

/**
 * Pinyin Gap Fill Suggestions Component
 * 
 * Allows users to review, edit, and approve suggestions for filling missing pinyin syllables.
 * Approved suggestions can be saved and applied to the pinyin deck.
 */
const PinyinGapFillSuggestions = ({ profile, onProfileUpdate }) => {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [applying, setApplying] = useState(false);
  const [selectedSuggestions, setSelectedSuggestions] = useState(new Set());
  const [editingSuggestion, setEditingSuggestion] = useState(null);
  const [filter, setFilter] = useState('all'); // 'all', 'approved', 'pending', 'no_match'
  const [searchTerm, setSearchTerm] = useState('');
  const [message, setMessage] = useState(null);
  // Track which image path alternative is being tried for each image to prevent infinite loops
  const [imagePathIndices, setImagePathIndices] = useState(new Map());
  // English vocabulary suggestions
  const [englishVocabSuggestions, setEnglishVocabSuggestions] = useState({});
  const [loadingEnglishVocab, setLoadingEnglishVocab] = useState(false);

  useEffect(() => {
    loadSuggestions();
    loadEnglishVocabSuggestions();
  }, []);

  const loadEnglishVocabSuggestions = async () => {
    setLoadingEnglishVocab(true);
    try {
      const response = await axios.get(`${API_BASE}/pinyin/english-vocab-suggestions`, {
        timeout: 10000
      });
      setEnglishVocabSuggestions(response.data.matches || {});
    } catch (error) {
      console.error('Error loading English vocab suggestions:', error);
      // Don't show error to user - just continue without suggestions
    } finally {
      setLoadingEnglishVocab(false);
    }
  };

  const handleEnglishVocabSelection = async (syllable, selectedMatch) => {
    // Only allow selection for pending items (not approved)
    const suggestionIndex = suggestions.findIndex(s => s.Syllable === syllable);
    if (suggestionIndex === -1) return;
    
    const suggestion = suggestions[suggestionIndex];
    
    // Skip if already approved
    if (suggestion.approved) {
      return;
    }
    
    // Find the image file for this English word in media/pinyin/
    let imageFile = '';
    try {
      const imageResponse = await axios.get(`${API_BASE}/pinyin/find-image-by-english-word`, {
        params: { english_word: selectedMatch.english },
        timeout: 3000
      });
      imageFile = imageResponse.data.image_file || '';
    } catch (error) {
      console.error('Error finding image:', error);
      // Continue without image - will try to find it later
    }
    
    // Convert numbered pinyin to tone-marked pinyin
    const pinyinWithTones = convertNumberedPinyinToToneMarks(selectedMatch.pinyin);
    
    // Update the suggestion with the selected English vocab match (REPLACES old suggestion)
    const updated = [...suggestions];
    const updatedSuggestion = {
      ...suggestion,
      'Suggested Word': selectedMatch.chinese,
      'Word Pinyin': normalizePinyin(pinyinWithTones), // Convert to tone marks and normalize spacing
      'HSK Level': '-', // Will be updated if available
      'Concreteness': selectedMatch.concreteness ? String(selectedMatch.concreteness) : '-',
      'Has Image': imageFile ? 'Yes' : 'No',
      'Image File': imageFile,
      'approved': '', // Clear approval status so user can review
      edited: true
    };
    
    updated[suggestionIndex] = updatedSuggestion;
    setSuggestions(updated);
    
    // Auto-select this item so it can be saved
    const newSelected = new Set(selectedSuggestions);
    newSelected.add(suggestionIndex);
    setSelectedSuggestions(newSelected);
    
    // AUTO-SAVE: Immediately save this single suggestion to prevent data loss
    // This ensures user's work is saved right away, not just when they click "Save selection"
    try {
      const singleSuggestionToSave = {
        [updatedSuggestion.Syllable]: updatedSuggestion
      };
      
      // Save to backend immediately
      await axios.put(`${API_BASE}/pinyin/gap-fill-suggestions`, {
        suggestions: [updatedSuggestion]
      }, {
        timeout: 5000
      });
      
      // Also backup to localStorage as safety net
      try {
        const backup = JSON.parse(localStorage.getItem('pinyin_suggestions_backup') || '{}');
        backup[updatedSuggestion.Syllable] = {
          ...updatedSuggestion,
          saved_at: new Date().toISOString()
        };
        localStorage.setItem('pinyin_suggestions_backup', JSON.stringify(backup));
      } catch (e) {
        // localStorage backup failed - not critical
      }
      
      setMessage({ 
        type: 'success', 
        text: `✅ 已保存: ${syllable} → ${selectedMatch.chinese} (${selectedMatch.english})` 
      });
      
      // Reload to get fresh data from backend
      await loadSuggestions();
    } catch (error) {
      console.error('Auto-save failed:', error);
      // If auto-save fails, still show message and select the item
      setMessage({ 
        type: 'warning', 
        text: `已更新 ${syllable}: ${selectedMatch.chinese}. 请点击"保存选择"以保存更改。` 
      });
    }
  };

  const loadSuggestions = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const response = await axios.get(`${API_BASE}/pinyin/gap-fill-suggestions`, {
        timeout: 30000 // 30 second timeout (response can be large with 230+ suggestions)
      });
      const loaded = response.data.suggestions || [];
      
      // Initialize approval status for each suggestion
      const suggestionsWithStatus = loaded.map(s => ({
        ...s,
        approved: s.approved || false,
        edited: s.edited || false
      }));
      
      setSuggestions(suggestionsWithStatus);
    } catch (error) {
      console.error('Error loading suggestions:', error);
      setMessage({ type: 'error', text: `加载失败: ${error.response?.data?.detail || error.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (index) => {
    setEditingSuggestion({ index, ...suggestions[index] });
  };

  const handleWordChange = (newWord) => {
    if (!editingSuggestion) return;
    
    // Simple text update - no auto-fetch to avoid IME interference
    setEditingSuggestion({
      ...editingSuggestion,
      'Suggested Word': newWord
    });
  };

  const handleSaveEdit = async () => {
    if (!editingSuggestion) return;
    
    // Create a new object to avoid mutating state
    let updatedSuggestion = { ...editingSuggestion };
    
    // Fetch pinyin only when saving
    const word = updatedSuggestion['Suggested Word']?.trim();
    if (word && word !== '') {
      try {
        const response = await axios.get(`${API_BASE}/pinyin/word-info`, {
          params: { word: word },
          timeout: 5000 // 5 second timeout - reduce from 10s to fail faster
        });
        
        if (response.data.pinyin) {
          // Normalize pinyin format: ensure spaces between syllables
          updatedSuggestion['Word Pinyin'] = normalizePinyin(response.data.pinyin);
          if (response.data.hsk_level) {
            updatedSuggestion['HSK Level'] = response.data.hsk_level;
          }
        } else {
          // If API didn't return pinyin, normalize any manually entered pinyin
          if (updatedSuggestion['Word Pinyin']) {
            updatedSuggestion['Word Pinyin'] = normalizePinyin(updatedSuggestion['Word Pinyin']);
          } else {
            updatedSuggestion['Word Pinyin'] = '';
          }
        }
      } catch (error) {
        console.error('Error fetching pinyin:', error);
        // Normalize manually entered pinyin even if API call fails
        if (updatedSuggestion['Word Pinyin']) {
          updatedSuggestion['Word Pinyin'] = normalizePinyin(updatedSuggestion['Word Pinyin']);
        }
      }
    }
    
    // Always normalize pinyin before saving (ensures consistency even if manually edited or from API)
    if (updatedSuggestion['Word Pinyin']) {
      updatedSuggestion['Word Pinyin'] = normalizePinyin(updatedSuggestion['Word Pinyin']);
    }
    
    const updated = [...suggestions];
    updated[updatedSuggestion.index] = {
      ...updatedSuggestion,
      edited: true
    };
    setSuggestions(updated);
    setEditingSuggestion(null);
  };

  const handleCancelEdit = () => {
    setEditingSuggestion(null);
  };

  const toggleApproval = (index) => {
    const updated = [...suggestions];
    updated[index].approved = !updated[index].approved;
    setSuggestions(updated);
    
    // Update selected set
    const newSelected = new Set(selectedSuggestions);
    if (updated[index].approved) {
      newSelected.add(index);
    } else {
      newSelected.delete(index);
    }
    setSelectedSuggestions(newSelected);
  };

  const selectAllApproved = () => {
    const approvedIndices = suggestions
      .map((s, i) => s.approved ? i : null)
      .filter(i => i !== null);
    setSelectedSuggestions(new Set(approvedIndices));
  };

  const selectAllValid = () => {
    const validIndices = suggestions
      .map((s, i) => {
        if (s['Suggested Word'] !== 'NONE' && s['Suggested Word'] && s['Suggested Word'].trim() !== '') {
          return i;
        }
        return null;
      })
      .filter(i => i !== null);
    setSelectedSuggestions(new Set(validIndices));
  };

  const clearSelection = () => {
    setSelectedSuggestions(new Set());
  };

  const saveSuggestions = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const approvedSuggestions = suggestions
        .map((s, index) => ({ ...s, index }))
        .filter((s, index) => selectedSuggestions.has(index))
        .map(s => {
          // Clean up the suggestion before sending - ensure all fields are properly formatted
          const cleaned = { ...s };
          // Remove the 'index' field before sending (not part of CSV schema)
          delete cleaned.index;
          // Ensure Image File is a string and properly set Has Image
          if (cleaned['Image File']) {
            cleaned['Image File'] = String(cleaned['Image File']).trim();
            cleaned['Has Image'] = cleaned['Image File'] ? 'Yes' : 'No';
          } else {
            cleaned['Has Image'] = 'No';
            cleaned['Image File'] = '';
          }
          return cleaned;
        });
      
      console.log('💾 Saving suggestions:', approvedSuggestions.map(s => ({
        syllable: s.Syllable,
        imageFile: s['Image File'],
        hasImage: s['Has Image']
      })));
      
      await axios.put(`${API_BASE}/pinyin/gap-fill-suggestions`, {
        suggestions: approvedSuggestions
      }, {
        timeout: 10000 // 10 second timeout
      });
      
      setMessage({ type: 'success', text: `已保存 ${approvedSuggestions.length} 条建议` });
      // Reload suggestions to get updated data
      // Reset image path indices so images start fresh from first path
      setImagePathIndices(new Map());
      await loadSuggestions();
    } catch (error) {
      console.error('Error saving suggestions:', error);
      const errorMsg = error.code === 'ECONNABORTED' 
        ? '保存超时，请检查后端服务'
        : error.response?.data?.detail || error.message;
      setMessage({ type: 'error', text: `保存失败: ${errorMsg}` });
    } finally {
      setSaving(false);
    }
  };

  const applySuggestions = async () => {
    if (selectedSuggestions.size === 0) {
      setMessage({ type: 'warning', text: '请先选择要应用的建议' });
      return;
    }

    if (!window.confirm(`确定要将 ${selectedSuggestions.size} 条建议应用到拼音牌组吗？`)) {
      return;
    }

    setApplying(true);
    setMessage(null);
    try {
      const approvedSuggestions = suggestions
        .filter((s, index) => selectedSuggestions.has(index))
        .map(s => ({
          syllable: s.Syllable,
          word: s['Suggested Word'],
          pinyin: s['Word Pinyin'],
          hsk_level: s['HSK Level'] !== '-' ? parseInt(s['HSK Level']) : null,
          has_image: s['Has Image'] === 'Yes',
          image_file: s['Image File'] || null,
          concreteness: s.Concreteness !== '-' ? parseFloat(s.Concreteness) : null,
          aoa: s.AoA !== '-' ? parseFloat(s.AoA) : null
        }));

      // Apply endpoint is in the main backend (port 8000) because it needs database access
      // Notes are created in shared table accessible by all profiles (profile_id not needed)
      await axios.post(`${MAIN_API_BASE}/pinyin/apply-suggestions`, {
        suggestions: approvedSuggestions
        // profile_id not needed - data preparation is for all profiles
      });

      setMessage({ type: 'success', text: `成功应用 ${approvedSuggestions.length} 条建议到拼音牌组！` });
      
      // Reload suggestions to reflect changes
      setTimeout(() => {
        loadSuggestions();
        if (onProfileUpdate) {
          onProfileUpdate();
        }
      }, 1000);
    } catch (error) {
      console.error('Error applying suggestions:', error);
      setMessage({ type: 'error', text: `应用失败: ${error.response?.data?.detail || error.message}` });
    } finally {
      setApplying(false);
    }
  };

  // Filter suggestions
  const filteredSuggestions = suggestions.filter(s => {
    // Filter by status
    if (filter === 'approved' && !s.approved) return false;
    if (filter === 'pending' && s.approved) return false;
    if (filter === 'no_match' && s['Suggested Word'] !== 'NONE') return false;
    
    // Filter by search term
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      return (
        s.Syllable?.toLowerCase().includes(term) ||
        s['Suggested Word']?.toLowerCase().includes(term) ||
        s['Word Pinyin']?.toLowerCase().includes(term)
      );
    }
    
    return true;
  });

  const approvedCount = suggestions.filter(s => s.approved).length;
  const selectedCount = selectedSuggestions.size;

  if (loading) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <p>加载中...</p>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>拼音音节填充建议</h2>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button onClick={loadSuggestions} style={{ padding: '8px 16px' }}>
            刷新
          </button>
        </div>
      </div>

      {message && (
        <div style={{
          padding: '12px',
          marginBottom: '20px',
          borderRadius: '4px',
          backgroundColor: message.type === 'error' ? '#fee' : message.type === 'warning' ? '#ffe' : '#efe',
          color: message.type === 'error' ? '#c00' : message.type === 'warning' ? '#880' : '#060',
          border: `1px solid ${message.type === 'error' ? '#fcc' : message.type === 'warning' ? '#ffc' : '#cfc'}`
        }}>
          {message.text}
        </div>
      )}

      {/* Filters and Actions */}
      <div style={{ 
        marginBottom: '20px', 
        padding: '15px', 
        backgroundColor: '#f5f5f5', 
        borderRadius: '8px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '10px'
      }}>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="text"
            placeholder="搜索音节、汉字或拼音..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ccc', minWidth: '200px' }}
          />
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ccc' }}
          >
            <option value="all">全部 ({suggestions.length})</option>
            <option value="approved">已批准 ({approvedCount})</option>
            <option value="pending">待处理 ({suggestions.length - approvedCount})</option>
            <option value="no_match">无匹配 ({suggestions.filter(s => s['Suggested Word'] === 'NONE').length})</option>
          </select>
        </div>
        
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button onClick={selectAllApproved} style={{ padding: '8px 16px' }}>
            选择全部已批准
          </button>
          <button onClick={selectAllValid} style={{ padding: '8px 16px' }}>
            选择全部有效
          </button>
          <button onClick={clearSelection} style={{ padding: '8px 16px' }}>
            清除选择
          </button>
          <button 
            onClick={saveSuggestions} 
            disabled={saving || selectedCount === 0}
            style={{ 
              padding: '8px 16px',
              backgroundColor: selectedCount > 0 ? '#4CAF50' : '#ccc',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: selectedCount > 0 ? 'pointer' : 'not-allowed'
            }}
          >
            {saving ? '保存中...' : `保存选择 (${selectedCount})`}
          </button>
          <button 
            onClick={applySuggestions} 
            disabled={applying || selectedCount === 0}
            style={{ 
              padding: '8px 16px',
              backgroundColor: selectedCount > 0 ? '#2196F3' : '#ccc',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: selectedCount > 0 ? 'pointer' : 'not-allowed'
            }}
          >
            {applying ? '应用中...' : `应用到牌组 (${selectedCount})`}
          </button>
        </div>
      </div>

      {/* Suggestions Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', backgroundColor: 'white' }}>
          <thead>
            <tr style={{ backgroundColor: '#f0f0f0' }}>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd', width: '50px' }}>
                <input
                  type="checkbox"
                  checked={selectedCount > 0 && selectedCount === filteredSuggestions.filter((s, i) => {
                    const actualIdx = suggestions.indexOf(s);
                    return s['Suggested Word'] !== 'NONE' && s['Suggested Word'] && s['Suggested Word'].trim() !== '';
                  }).length}
                  onChange={(e) => {
                    if (e.target.checked) {
                      // Select all valid suggestions (not NONE) in filtered list
                      const validIndices = filteredSuggestions
                        .map((s, i) => {
                          const actualIdx = suggestions.indexOf(s);
                          if (s['Suggested Word'] !== 'NONE' && s['Suggested Word'] && s['Suggested Word'].trim() !== '') {
                            return actualIdx;
                          }
                          return null;
                        })
                        .filter(i => i !== null);
                      setSelectedSuggestions(new Set(validIndices));
                    } else {
                      clearSelection();
                    }
                  }}
                />
              </th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>音节</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>建议汉字</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>拼音</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>HSK</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>具体性</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>AoA</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>图片</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {filteredSuggestions.map((suggestion, index) => {
              const actualIndex = suggestions.indexOf(suggestion);
              const isSelected = selectedSuggestions.has(actualIndex);
              const isEditing = editingSuggestion?.index === actualIndex;
              
              return (
                <tr 
                  key={actualIndex}
                  style={{ 
                    backgroundColor: suggestion.approved ? '#e8f5e9' : 'white',
                    opacity: suggestion['Suggested Word'] === 'NONE' ? 0.6 : 1
                  }}
                >
                  <td style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {
                        const newSelected = new Set(selectedSuggestions);
                        if (isSelected) {
                          newSelected.delete(actualIndex);
                        } else {
                          newSelected.add(actualIndex);
                        }
                        setSelectedSuggestions(newSelected);
                      }}
                      disabled={suggestion['Suggested Word'] === 'NONE' || !suggestion['Suggested Word'] || suggestion['Suggested Word'].trim() === ''}
                    />
                  </td>
                  <td style={{ padding: '12px', border: '1px solid #ddd', fontWeight: 'bold' }}>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editingSuggestion.Syllable}
                        onChange={(e) => setEditingSuggestion({ ...editingSuggestion, Syllable: e.target.value })}
                        style={{ width: '80px', padding: '4px' }}
                      />
                    ) : (
                      suggestion.Syllable
                    )}
                  </td>
                  <td style={{ padding: '12px', border: '1px solid #ddd' }}>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editingSuggestion['Suggested Word'] || ''}
                        onChange={(e) => handleWordChange(e.target.value)}
                        style={{ width: '100px', padding: '4px' }}
                        placeholder="输入汉字"
                      />
                    ) : (
                      <div>
                        {suggestion['Suggested Word'] || 'NONE'}
                        {/* Show English vocab suggestions only for pending items (not approved) */}
                        {!suggestion.approved && englishVocabSuggestions[suggestion.Syllable] && (
                          <div style={{ marginTop: '8px', padding: '8px', backgroundColor: '#f0f8ff', borderRadius: '4px', fontSize: '11px' }}>
                            <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>English Suggestions:</div>
                            {englishVocabSuggestions[suggestion.Syllable].slice(0, 3).map((match, idx) => {
                              const isSelected = suggestion['Suggested Word'] === match.chinese;
                              const englishWord = match.english.toLowerCase().replace(/[^a-z0-9]+/g, '_');
                              const pinyinDisplay = convertNumberedPinyinToToneMarks(match.pinyin);
                              return (
                                <label
                                  key={idx}
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px',
                                    marginBottom: '4px',
                                    cursor: 'pointer',
                                    padding: '4px',
                                    borderRadius: '3px',
                                    backgroundColor: isSelected ? '#e3f2fd' : 'transparent',
                                    border: isSelected ? '1px solid #2196F3' : '1px solid transparent'
                                  }}
                                >
                                  <input
                                    type="radio"
                                    name={`english-vocab-${suggestion.Syllable}`}
                                    checked={isSelected}
                                    onChange={() => handleEnglishVocabSelection(suggestion.Syllable, match)}
                                    style={{ margin: 0 }}
                                  />
                                  <span style={{ flex: 1 }}>
                                    <strong>{match.english}</strong> → {match.chinese} ({pinyinDisplay})
                                  </span>
                                  {/* Show image preview if available - use backend to find actual filename */}
                                  <EnglishVocabImagePreview englishWord={match.english} />
                                </label>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '12px', border: '1px solid #ddd' }}>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editingSuggestion['Word Pinyin'] || ''}
                        onChange={(e) => {
                          // Allow manual editing but normalize on blur
                          setEditingSuggestion({ ...editingSuggestion, 'Word Pinyin': e.target.value });
                        }}
                        onBlur={(e) => {
                          // Normalize format when user finishes editing (spaces between syllables)
                          const normalized = normalizePinyin(e.target.value);
                          setEditingSuggestion({ ...editingSuggestion, 'Word Pinyin': normalized });
                        }}
                        style={{ width: '120px', padding: '4px' }}
                        placeholder="拼音"
                      />
                    ) : (
                      suggestion['Word Pinyin'] || '-'
                    )}
                  </td>
                  <td style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'center' }}>
                    {suggestion['HSK Level'] || '-'}
                  </td>
                  <td style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'center' }}>
                    {suggestion.Concreteness !== '-' ? parseFloat(suggestion.Concreteness).toFixed(2) : '-'}
                  </td>
                  <td style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'center' }}>
                    {suggestion.AoA !== '-' ? parseFloat(suggestion.AoA).toFixed(1) : '-'}
                  </td>
                  <td style={{ padding: '12px', border: '1px solid #ddd', textAlign: 'center' }}>
                    {isEditing ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center' }}>
                        {editingSuggestion['Image File'] ? (
                          <img
                            src={(() => {
                              // Get or initialize the path index for this image
                              const imageKey = `edit-${editingSuggestion.Syllable}-${editingSuggestion['Image File']}`;
                              const alternatives = [
                                `${API_BASE}/media/visual_images/${editingSuggestion['Image File']}`,
                                `${API_BASE}/media/pinyin/${editingSuggestion['Image File']}`,
                                `${API_BASE}/media/character_recognition/${editingSuggestion['Image File']}`,
                                `${API_BASE}/media/chinese_word_recognition/${editingSuggestion['Image File']}`,
                                `${API_BASE}/media/images/${editingSuggestion['Image File']}`,
                                `${API_BASE}/media/${editingSuggestion['Image File']}`,
                                `/${editingSuggestion['Image File']}`
                              ];
                              const currentIndex = imagePathIndices.get(imageKey) || 0;
                              return alternatives[currentIndex] || alternatives[0];
                            })()}
                            alt="Preview"
                            style={{
                              maxWidth: '80px',
                              maxHeight: '80px',
                              borderRadius: '4px',
                              border: '1px solid #ddd',
                              objectFit: 'contain',
                              backgroundColor: '#f5f5f5',
                              display: 'block'
                            }}
                            onLoad={(e) => {
                              // Image loaded successfully - ensure it's visible
                              e.target.style.display = 'block';
                              e.target.style.visibility = 'visible';
                              e.target.style.opacity = '1';
                            }}
                            onError={(e) => {
                              // Try alternative paths - search all image directories
                              const filename = editingSuggestion['Image File'];
                              const imageKey = `edit-${editingSuggestion.Syllable}-${filename}`;
                              const alternatives = [
                                `${API_BASE}/media/visual_images/${filename}`,
                                `${API_BASE}/media/pinyin/${filename}`,
                                `${API_BASE}/media/character_recognition/${filename}`,
                                `${API_BASE}/media/chinese_word_recognition/${filename}`,
                                `${API_BASE}/media/images/${filename}`,
                                `${API_BASE}/media/${filename}`,
                                `/${filename}`
                              ];
                              const currentIndex = imagePathIndices.get(imageKey) || 0;
                              if (currentIndex < alternatives.length - 1) {
                                const newIndex = currentIndex + 1;
                                setImagePathIndices(new Map(imagePathIndices).set(imageKey, newIndex));
                                e.target.src = alternatives[newIndex];
                              } else {
                                // All paths tried, hide the image
                                e.target.style.display = 'none';
                              }
                            }}
                          />
                        ) : (
                          <div style={{ 
                            width: '80px', 
                            height: '80px', 
                            border: '1px dashed #ccc', 
                            borderRadius: '4px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#999',
                            fontSize: '12px'
                          }}>
                            无图片
                          </div>
                        )}
                        <input
                          type="text"
                          value={editingSuggestion['Image File'] || ''}
                          onChange={(e) => {
                            const imageFile = e.target.value.trim();
                            setEditingSuggestion({ 
                              ...editingSuggestion, 
                              'Image File': imageFile,
                              'Has Image': imageFile ? 'Yes' : 'No'
                            });
                          }}
                          placeholder="图片文件名"
                          style={{ width: '120px', padding: '4px', fontSize: '11px' }}
                        />
                        <div style={{ fontSize: '10px', color: '#666' }}>
                          {editingSuggestion['Image File'] ? '✅' : '❌'}
                        </div>
                      </div>
                    ) : (
                      <>
                        {suggestion['Has Image'] === 'Yes' && suggestion['Image File'] ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'center' }}>
                            {(() => {
                              // Calculate image src once per render
                              const filename = String(suggestion['Image File'] || '').trim();
                              const imageKey = `${suggestion.Syllable}-${filename}`;
                              const alternatives = [
                                `${API_BASE}/media/visual_images/${filename}`,
                                `${API_BASE}/media/pinyin/${filename}`,
                                `${API_BASE}/media/character_recognition/${filename}`,
                                `${API_BASE}/media/chinese_word_recognition/${filename}`,
                                `${API_BASE}/media/images/${filename}`,
                                `${API_BASE}/media/${filename}`,
                                `/${filename}`
                              ];
                              const currentIndex = imagePathIndices.get(imageKey) || 0;
                              const imageSrc = alternatives[currentIndex] || alternatives[0];
                              
                              return (
                                <img
                                  key={`${imageKey}-${currentIndex}-${filename}`}
                                  src={imageSrc}
                                  alt={suggestion['Suggested Word']}
                                  style={{
                                    maxWidth: '60px',
                                    maxHeight: '60px',
                                    borderRadius: '4px',
                                    border: '1px solid #ddd',
                                    objectFit: 'contain',
                                    backgroundColor: '#f5f5f5',
                                    display: 'block',
                                    visibility: 'visible',
                                    minWidth: '40px',
                                    minHeight: '40px'
                                  }}
                                  onLoad={(e) => {
                                    // Image loaded successfully - ensure it's visible
                                    e.target.style.display = 'block';
                                    e.target.style.visibility = 'visible';
                                    e.target.style.opacity = '1';
                                    // Prevent error handler from firing after successful load
                                    e.target.dataset.loaded = 'true';
                                  }}
                                  onError={(e) => {
                                    // Don't handle error if image already loaded successfully
                                    if (e.target.dataset.loaded === 'true') {
                                      return;
                                    }
                                    
                                    // Prevent infinite loops - only try alternatives if filename is valid
                                    const filename = String(suggestion['Image File'] || '').trim();
                                    if (!filename || filename.length < 3) {
                                      e.target.style.display = 'none';
                                      return;
                                    }
                                    
                                    const key = `${suggestion.Syllable}-${filename}`;
                                    const altPaths = [
                                      `${API_BASE}/media/visual_images/${filename}`,
                                      `${API_BASE}/media/pinyin/${filename}`,
                                      `${API_BASE}/media/character_recognition/${filename}`,
                                      `${API_BASE}/media/chinese_word_recognition/${filename}`,
                                      `${API_BASE}/media/images/${filename}`,
                                      `${API_BASE}/media/${filename}`,
                                      `/${filename}`
                                    ];
                                    const idx = imagePathIndices.get(key) || 0;
                                    if (idx < altPaths.length - 1) {
                                      const newIdx = idx + 1;
                                      const newMap = new Map(imagePathIndices);
                                      newMap.set(key, newIdx);
                                      setImagePathIndices(newMap);
                                      // Update src directly to avoid re-render loop
                                      e.target.src = altPaths[newIdx];
                                    } else {
                                      // All paths tried, hide the image
                                      e.target.style.display = 'none';
                                      e.target.style.visibility = 'hidden';
                                    }
                                  }}
                                />
                              );
                            })()}
                            <span style={{ fontSize: '9px', color: '#666', wordBreak: 'break-word', textAlign: 'center', maxWidth: '80px' }}>
                              {suggestion['Image File']}
                            </span>
                          </div>
                        ) : (
                          <div>
                            <span style={{ fontSize: '14px' }}>❌</span>
                            {suggestion['Image File'] && (
                              <span style={{ fontSize: '9px', color: '#666', display: 'block' }}>
                                {suggestion['Image File']}
                              </span>
                            )}
                          </div>
                        )}
                      </>
                    )}
                  </td>
                  <td style={{ padding: '12px', border: '1px solid #ddd' }}>
                    <div style={{ display: 'flex', gap: '5px', flexDirection: 'column' }}>
                      <button
                        onClick={() => toggleApproval(actualIndex)}
                        style={{
                          padding: '4px 8px',
                          fontSize: '12px',
                          backgroundColor: suggestion.approved ? '#4CAF50' : '#ccc',
                          color: 'white',
                          border: 'none',
                          borderRadius: '4px',
                          cursor: 'pointer'
                        }}
                      >
                        {suggestion.approved ? '已批准' : '批准'}
                      </button>
                      {isEditing ? (
                        <>
                          <button
                            onClick={handleSaveEdit}
                            style={{
                              padding: '4px 8px',
                              fontSize: '12px',
                              backgroundColor: '#2196F3',
                              color: 'white',
                              border: 'none',
                              borderRadius: '4px',
                              cursor: 'pointer'
                            }}
                          >
                            保存
                          </button>
                          <button
                            onClick={handleCancelEdit}
                            style={{
                              padding: '4px 8px',
                              fontSize: '12px',
                              backgroundColor: '#666',
                              color: 'white',
                              border: 'none',
                              borderRadius: '4px',
                              cursor: 'pointer'
                            }}
                          >
                            取消
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => handleEdit(actualIndex)}
                          style={{
                            padding: '4px 8px',
                            fontSize: '12px',
                            backgroundColor: '#FF9800',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer'
                          }}
                        >
                          编辑
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {filteredSuggestions.length === 0 && (
        <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>
          <p>没有找到匹配的建议</p>
        </div>
      )}
    </div>
  );
};

export default PinyinGapFillSuggestions;

