import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import axios from 'axios';
import { useLanguage } from '../i18n/LanguageContext';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Map POS values from CEFR-J CSV to i18n keys
const POS_TO_KEY = {
  'be-verb': 'posBeVerb',
  'determiner': 'posDeterminer',
  'adverb': 'posAdverb',
  'noun': 'posNoun',
  'verb': 'posVerb',
  'adjective': 'posAdjective',
  'preposition': 'posPreposition',
  'conjunction': 'posConjunction',
  'pronoun': 'posPronoun'
};

const MasteredEnglishWordsManager = ({ profile, onUpdate }) => {
  const { t } = useLanguage();
  const [vocabulary, setVocabulary] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCEFR, setSelectedCEFR] = useState(null); // null = all levels
  const [masteredSet, setMasteredSet] = useState(new Set());
  const [saving, setSaving] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [lastSaveTime, setLastSaveTime] = useState(null);
  const saveTimeoutRef = useRef(null);
  const initialMasteredSetRef = useRef(null); // Store original state for reset
  const [wordImages, setWordImages] = useState({}); // Cache of word -> image URL
  const [loadingImages, setLoadingImages] = useState(false);
  const requestedWordsRef = useRef(new Set()); // Track which words we've already requested

  // Parse mastered words from profile
  useEffect(() => {
    const masteredWordsString = profile?.mastered_english_words || '';
    console.log('MasteredEnglishWordsManager: Profile mastered_english_words changed:', masteredWordsString);
    
    if (masteredWordsString) {
      // Split only on commas to preserve multi-word phrases like "good morning"
      const words = masteredWordsString
        .split(',')
        .map(w => w.trim().toLowerCase())
        .filter(w => w);
      const initialSet = new Set(words);
      console.log('MasteredEnglishWordsManager: Parsed', words.length, 'words:', words.slice(0, 10));
      setMasteredSet(initialSet);
      // Store initial state for undo/reset
      initialMasteredSetRef.current = new Set(initialSet);
    } else {
      console.log('MasteredEnglishWordsManager: No mastered English words');
      setMasteredSet(new Set());
      initialMasteredSetRef.current = new Set();
    }
  }, [profile?.mastered_english_words]);

  // Load CEFR vocabulary
  useEffect(() => {
    const loadVocabulary = async () => {
      try {
        const response = await axios.get(`${API_BASE}/vocabulary/cefr`);
        setVocabulary(response.data.words || []);
      } catch (error) {
        console.error('Error loading vocabulary:', error);
        alert(t('failedToLoadVocabularyEnglish'));
      } finally {
        setLoading(false);
      }
    };

    loadVocabulary();
  }, []);

  // Filter vocabulary based on search and CEFR level
  const filteredVocab = useMemo(() => {
    let filtered = vocabulary;

    // Filter by CEFR level
    if (selectedCEFR !== null) {
      filtered = filtered.filter(w => w.cefr_level === selectedCEFR);
    }

    // Filter by search term
    if (searchTerm.trim()) {
      const searchLower = searchTerm.toLowerCase();
      filtered = filtered.filter(w =>
        w.word.toLowerCase().includes(searchLower) ||
        w.definition?.toLowerCase().includes(searchLower)
      );
    }

    // Limit display unless showAll is true
    if (!showAll && filtered.length > 100) {
      filtered = filtered.slice(0, 100);
    }

    return filtered;
  }, [vocabulary, searchTerm, selectedCEFR, showAll]);

  // Load images for visible words (batch query, lazy loading)
  useEffect(() => {
    if (filteredVocab.length === 0) return;

    // Get words that we haven't requested yet
    const wordsToLoad = filteredVocab
      .slice(0, 100) // Only load for first 100 visible items
      .map(w => w.word)
      .filter(word => !requestedWordsRef.current.has(word));

    if (wordsToLoad.length === 0) return;

    // Mark these words as requested immediately to prevent duplicate requests
    wordsToLoad.forEach(word => requestedWordsRef.current.add(word));

    // Batch load images
    const loadImages = async () => {
      setLoadingImages(true);
      try {
        console.log('Loading images for words:', wordsToLoad.slice(0, 10), '...');
        const response = await axios.post(`${API_BASE}/vocabulary/images`, {
          words: wordsToLoad
        });
        const foundCount = Object.keys(response.data).filter(k => response.data[k]).length;
        console.log(`Image response: ${foundCount} images found out of ${wordsToLoad.length} words requested`);
        if (foundCount > 0) {
          console.log('Sample images:', Object.entries(response.data).filter(([k, v]) => v).slice(0, 5));
        }
        setWordImages(prev => ({ ...prev, ...response.data }));
      } catch (error) {
        console.error('Error loading images:', error);
        // On error, remove from requested set so we can retry
        wordsToLoad.forEach(word => requestedWordsRef.current.delete(word));
        // Graceful degradation - continue without images
      } finally {
        setLoadingImages(false);
      }
    };

    // Debounce image loading
    const timeoutId = setTimeout(loadImages, 300);
    return () => clearTimeout(timeoutId);
  }, [filteredVocab]);

  // Auto-save function with debounce
  const saveMasteredWords = useCallback(async (wordsToSave, immediate = false) => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    const saveAction = async () => {
      setSaving(true);
      try {
        const masteredWordsString = Array.from(wordsToSave).join(', ');
        const profileData = { ...profile, mastered_english_words: masteredWordsString };
        await axios.put(`${API_BASE}/profiles/${profile.name}`, profileData);
        setLastSaveTime(new Date());
        if (immediate && onUpdate) {
          await onUpdate();
        }
      } catch (error) {
        console.error('Error saving mastered words:', error);
        alert(t('failedToSaveMasteredEnglishWords'));
      } finally {
        setSaving(false);
      }
    };

    if (immediate) {
      await saveAction();
    } else {
      saveTimeoutRef.current = setTimeout(saveAction, 500); // 500ms debounce
    }
  }, [profile, onUpdate, t]);

  // Toggle word mastery with auto-save
  const toggleWord = useCallback((word) => {
    const normalizedWord = word.toLowerCase();
    const newSet = new Set(masteredSet);
    if (newSet.has(normalizedWord)) {
      newSet.delete(normalizedWord);
    } else {
      newSet.add(normalizedWord);
    }
    setMasteredSet(newSet);
    saveMasteredWords(newSet, false);
  }, [masteredSet, saveMasteredWords]);

  // Select all visible words with warning
  const selectAllVisible = useCallback(() => {
    // Recalculate filtered vocab based on current filters
    let filtered = vocabulary;
    if (selectedCEFR !== null) {
      filtered = filtered.filter(w => w.cefr_level === selectedCEFR);
    }
    if (searchTerm.trim()) {
      const searchLower = searchTerm.toLowerCase();
      filtered = filtered.filter(w =>
        w.word.toLowerCase().includes(searchLower) ||
        w.definition?.toLowerCase().includes(searchLower)
      );
    }
    
    // Show warning, especially for all CEFR levels
    const isAllLevels = selectedCEFR === null && !searchTerm.trim();
    const wordCount = filtered.length;
    const alreadyMastered = filtered.filter(w => masteredSet.has(w.word.toLowerCase())).length;
    const willAdd = wordCount - alreadyMastered;
    
    let warningMessage = `⚠️ ` + (willAdd > 0
      ? t('selectAllVisibleEnglishConfirm')
          .replace('{count}', wordCount.toLocaleString())
          .replace('{willAdd}', willAdd.toLocaleString())
          .replace('{alreadyMastered}', alreadyMastered.toLocaleString())
      : t('selectAllVisibleEnglishConfirmNoAdd').replace('{count}', wordCount.toLocaleString()));
    if (isAllLevels) {
      warningMessage += `🚨 ` + t('selectAllVisibleEnglishWarnAllLevels');
    } else {
      warningMessage += t('selectAllVisibleEnglishConfirmContinue');
    }
    
    if (!window.confirm(warningMessage)) {
      return; // User cancelled
    }
    
    const newSet = new Set(masteredSet);
    filtered.forEach(w => {
      newSet.add(w.word.toLowerCase());
    });
    setMasteredSet(newSet);
    saveMasteredWords(newSet, false);
  }, [masteredSet, saveMasteredWords, vocabulary, selectedCEFR, searchTerm, t]);

  // Deselect all visible words with warning
  const deselectAllVisible = useCallback(() => {
    // Recalculate filtered vocab based on current filters
    let filtered = vocabulary;
    if (selectedCEFR !== null) {
      filtered = filtered.filter(w => w.cefr_level === selectedCEFR);
    }
    if (searchTerm.trim()) {
      const searchLower = searchTerm.toLowerCase();
      filtered = filtered.filter(w =>
        w.word.toLowerCase().includes(searchLower) ||
        w.definition?.toLowerCase().includes(searchLower)
      );
    }
    
    const selectedCount = filtered.filter(w => masteredSet.has(w.word.toLowerCase())).length;
    
    if (selectedCount === 0) {
      alert(t('deselectAllVisibleEnglishNoSelected'));
      return;
    }
    
    // Show warning
    const isAllLevels = selectedCEFR === null && !searchTerm.trim();
    let warningMessage = `⚠️ ` + t('deselectAllVisibleEnglishConfirm').replace('{count}', selectedCount.toLocaleString());
    if (isAllLevels && selectedCount > 100) {
      warningMessage += `🚨 ` + t('deselectAllVisibleEnglishWarnAllLevels');
    }
    warningMessage += t('selectAllVisibleEnglishConfirmContinue');
    
    if (!window.confirm(warningMessage)) {
      return; // User cancelled
    }
    
    const newSet = new Set(masteredSet);
    filtered.forEach(w => {
      newSet.delete(w.word.toLowerCase());
    });
    setMasteredSet(newSet);
    saveMasteredWords(newSet, false);
  }, [masteredSet, saveMasteredWords, vocabulary, selectedCEFR, searchTerm, t]);

  // Reset to original state (undo all changes)
  const resetToOriginal = useCallback(async () => {
    if (initialMasteredSetRef.current) {
      const restoredSet = new Set(initialMasteredSetRef.current);
      setMasteredSet(restoredSet);
      // Save immediately (bypass debounce)
      await saveMasteredWords(restoredSet, true);
    }
  }, [saveMasteredWords]);

  // Calculate statistics
  const stats = useMemo(() => {
    const total = vocabulary.length;
    // Count mastered items that actually exist in vocabulary
    const mastered = vocabulary.filter(w => masteredSet.has(w.word.toLowerCase())).length;
    const byLevel = {};
    
    vocabulary.forEach(w => {
      const level = w.cefr_level || 'Unknown';
      
      if (!byLevel[level]) {
        byLevel[level] = { total: 0, mastered: 0 };
      }
      byLevel[level].total++;
      if (masteredSet.has(w.word.toLowerCase())) {
        byLevel[level].mastered++;
      }
    });

    return { total, mastered, byLevel };
  }, [vocabulary, masteredSet]);

  if (loading) {
    return <div style={{ padding: '20px', textAlign: 'center' }}>{t('loadingVocabularyEnglish')}</div>;
  }

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3>📚 {t('masteredEnglishWordsManagerTitle')}</h3>
            <p style={{ color: '#666', fontSize: '14px', marginTop: '5px' }}>
              {t('masteredEnglishWordsSubtitle')}
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {saving && (
              <span style={{ fontSize: '12px', color: '#666' }}>💾 {t('saving')}</span>
            )}
            {lastSaveTime && !saving && (
              <span style={{ fontSize: '12px', color: '#4CAF50' }}>
                {t('savedAtTime').replace('{time}', lastSaveTime.toLocaleTimeString())}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Statistics */}
      <div style={{
        backgroundColor: '#f5f5f5',
        padding: '15px',
        borderRadius: '8px',
        marginBottom: '20px'
      }}>
        <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
          <div>
            <strong>{t('totalMasteredEnglishWords')}:</strong> {stats.mastered} / {stats.total} {t('wordsCountEnglish')}
          </div>
          {['A1', 'A2', 'B1', 'B2', 'C1', 'C2'].map(level => {
            const levelStats = stats.byLevel[level];
            if (!levelStats) return null;
            const percentage = levelStats.total > 0
              ? (levelStats.mastered / levelStats.total * 100).toFixed(1)
              : 0;
            return (
              <div key={level}>
                <strong>CEFR {level}:</strong> {levelStats.mastered} / {levelStats.total} ({percentage}%)
              </div>
            );
          })}
          {stats.byLevel['Unknown'] && (
            <div>
              <strong>{t('unknownLevel')}:</strong> {stats.byLevel['Unknown'].mastered} / {stats.byLevel['Unknown'].total}
            </div>
          )}
        </div>
      </div>

      {/* Filters */}
      <div style={{ marginBottom: '20px', display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          type="text"
          placeholder={t('searchWordsOrDefinitions')}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{
            padding: '8px 12px',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '14px',
            flex: '1',
            minWidth: '200px'
          }}
        />
        <select
          value={selectedCEFR || ''}
          onChange={(e) => setSelectedCEFR(e.target.value || null)}
          style={{
            padding: '8px 12px',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '14px'
          }}
        >
          <option value="">{t('allCEFRLevels')}</option>
          {['A1', 'A2', 'B1', 'B2', 'C1', 'C2'].map(level => (
            <option key={level} value={level}>CEFR {level}</option>
          ))}
        </select>
      </div>

      {/* Bulk Actions */}
      <div style={{ marginBottom: '20px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
        <button
          onClick={selectAllVisible}
          className="btn"
          style={{ fontSize: '14px', padding: '8px 16px' }}
        >
          ✓ {t('selectAllVisibleEnglishWords').replace('{count}', filteredVocab.length)}
        </button>
        <button
          onClick={deselectAllVisible}
          className="btn btn-secondary"
          style={{ fontSize: '14px', padding: '8px 16px' }}
        >
          ✗ {t('deselectAllVisibleEnglishWords')}
        </button>
        <button
          onClick={resetToOriginal}
          className="btn btn-secondary"
          style={{ fontSize: '14px', padding: '8px 16px', backgroundColor: '#ff9800', color: 'white' }}
        >
          ↶ {t('resetToOriginalEnglishWords')}
        </button>
      </div>

      {/* Word List */}
      <div style={{
        maxHeight: '500px',
        overflowY: 'auto',
        border: '1px solid #ddd',
        borderRadius: '4px',
        padding: '10px'
      }}>
        {filteredVocab.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#666', padding: '20px' }}>
            {t('noWordsMatchingCriteriaEnglish')}
          </div>
        ) : (
          <>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
              gap: '8px'
            }}>
              {filteredVocab.map((w) => {
                const normalizedWord = w.word.toLowerCase();
                const isMastered = masteredSet.has(normalizedWord);
                return (
                  <label
                    key={w.word}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      padding: '8px',
                      borderRadius: '4px',
                      backgroundColor: isMastered ? '#e8f5e9' : 'transparent',
                      cursor: 'pointer',
                      border: isMastered ? '2px solid #4CAF50' : '1px solid #e0e0e0',
                      minHeight: '60px'
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isMastered}
                      onChange={() => toggleWord(w.word)}
                      style={{ marginRight: '8px', cursor: 'pointer' }}
                    />
                    {/* Small image preview */}
                    {wordImages[w.word] ? (
                      <img
                        src={`${API_BASE}${wordImages[w.word]}`}
                        alt={w.word}
                        style={{
                          width: '32px',
                          height: '32px',
                          objectFit: 'cover',
                          borderRadius: '3px',
                          marginRight: '6px',
                          flexShrink: 0
                        }}
                        onError={(e) => {
                          console.error(`Failed to load image for ${w.word}: ${wordImages[w.word]}`);
                          e.target.style.display = 'none';
                        }}
                        onLoad={() => {
                          console.log(`✅ Image loaded for ${w.word}: ${wordImages[w.word]}`);
                        }}
                      />
                    ) : loadingImages && !wordImages[w.word] ? (
                      <div style={{
                        width: '32px',
                        height: '32px',
                        marginRight: '6px',
                        flexShrink: 0,
                        backgroundColor: '#f0f0f0',
                        borderRadius: '3px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '10px',
                        color: '#999'
                      }}>...</div>
                    ) : null}
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 'bold', fontSize: '16px' }}>{w.word}</div>
                      {w.definition && (
                        <div style={{ fontSize: '12px', color: '#666' }}>{w.definition}</div>
                      )}
                      {w.cefr_level && (
                        <div style={{ fontSize: '11px', color: '#999' }}>CEFR {w.cefr_level}</div>
                      )}
                      {w.pos && (
                        <div style={{ fontSize: '11px', color: '#999' }}>
                          {POS_TO_KEY[w.pos] ? t(POS_TO_KEY[w.pos]) : w.pos}
                        </div>
                      )}
                    </div>
                  </label>
                );
              })}
            </div>
            {!showAll && filteredVocab.length >= 100 && (
              <div style={{ textAlign: 'center', marginTop: '15px' }}>
                <button
                  onClick={() => setShowAll(true)}
                  className="btn"
                  style={{ fontSize: '14px' }}
                >
                  {t('showAllResultsEnglish')}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default MasteredEnglishWordsManager;

