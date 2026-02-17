import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import axios from 'axios';
import { useLanguage } from '../i18n/LanguageContext';
import TopicChat from './TopicChat';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const MasteredGrammarManager = ({ profile, onClose, grammarLanguage = 'zh' }) => {
  const { language: uiLanguage, t } = useLanguage();
  // grammarLanguage is now passed as prop from parent (no local state)
  const [grammarPoints, setGrammarPoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCEFR, setSelectedCEFR] = useState(null); // null = all levels
  const [masteredSet, setMasteredSet] = useState(new Set());
  const [saving, setSaving] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [lastSaveTime, setLastSaveTime] = useState(null);
  const saveTimeoutRef = useRef(null);
  const initialMasteredSetRef = useRef(null); // Store original state for reset
  const [editingId, setEditingId] = useState(null); // Track which grammar point is being edited
  const [editedGrammar, setEditedGrammar] = useState({}); // Store edited values
  const [savingGrammar, setSavingGrammar] = useState(false); // Track grammar save status
  const [chatTopic, setChatTopic] = useState(null); // Track which topic is open for chat
  const [chatTopicName, setChatTopicName] = useState(null); // Track the topic name for display

  // Parse mastered grammar from profile
  // Grammar points are stored as URIs (gp_uri) to avoid comma issues in names
  useEffect(() => {
    if (profile && profile.mastered_grammar) {
      // Split by comma, but be aware that URIs don't contain commas
      const grammar = profile.mastered_grammar
        .split(',')
        .map(g => g.trim())
        .filter(g => g);
      const initialSet = new Set(grammar);
      setMasteredSet(initialSet);
      // Store initial state for undo/reset
      initialMasteredSetRef.current = new Set(initialSet);
    } else {
      setMasteredSet(new Set());
      initialMasteredSetRef.current = new Set();
    }
  }, [profile]);

  // Load grammar points and corrections
  useEffect(() => {
    const loadGrammarPoints = async () => {
      setLoading(true);
      try {
        const [grammarResponse, correctionsResponse] = await Promise.all([
          axios.get(`${API_BASE}/vocabulary/grammar`, {
            params: { language: grammarLanguage }
          }),
          axios.get(`${API_BASE}/vocabulary/grammar/corrections`).catch(() => ({ data: { corrections: {} } }))
        ]);
        
        let grammarPoints = grammarResponse.data.grammar_points || [];
        const corrections = correctionsResponse.data.corrections || {};
        
        // Apply corrections to grammar points
        grammarPoints = grammarPoints.map(gp => {
          const correction = corrections[gp.gp_uri];
          if (correction) {
            return {
              ...gp,
              ...correction,
              // Keep original gp_uri
              gp_uri: gp.gp_uri
            };
          }
          return gp;
        });
        
        setGrammarPoints(grammarPoints);
      } catch (error) {
        console.error('Error loading grammar points:', error);
        alert(t('failedToLoadGrammar'));
      } finally {
        setLoading(false);
      }
    };

    loadGrammarPoints();
  }, [grammarLanguage]);

  // Auto-save function with debounce
  const saveMasteredGrammar = useCallback(async (grammarToSave, immediate = false) => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    const saveAction = async () => {
      setSaving(true);
      try {
        // Join URIs with comma only (no space) since URIs don't contain commas
        const masteredGrammarString = Array.from(grammarToSave).join(',');
        const profileData = { ...profile, mastered_grammar: masteredGrammarString };
        await axios.put(`${API_BASE}/profiles/${profile.name}`, profileData);
        setLastSaveTime(new Date());
        // NO onUpdate call - modal is isolated during editing
      } catch (error) {
        console.error('Error saving mastered grammar:', error);
        alert(t('failedToSaveMasteredGrammar'));
      } finally {
        setSaving(false);
      }
    };

    if (immediate) {
      await saveAction();
    } else {
      saveTimeoutRef.current = setTimeout(saveAction, 500); // 500ms debounce
    }
  }, [profile]);

  // Toggle grammar mastery with auto-save
  // grammarPoint should be gp_uri (unique identifier)
  const toggleGrammar = useCallback((gp_uri) => {
    const newSet = new Set(masteredSet);
    if (newSet.has(gp_uri)) {
      newSet.delete(gp_uri);
    } else {
      newSet.add(gp_uri);
    }
    setMasteredSet(newSet);
    saveMasteredGrammar(newSet, false);
  }, [masteredSet, saveMasteredGrammar]);

  // Start editing a grammar point
  const startEdit = useCallback((g) => {
    setEditingId(g.gp_uri);
    setEditedGrammar({
      grammar_point: g.grammar_point || '',
      grammar_point_zh: g.grammar_point_zh || '',
      structure: g.structure || '',
      explanation: g.explanation || '',
      cefr_level: g.cefr_level || '',
      example_chinese: g.example_chinese || g.example || '', // Support both Chinese and English examples
      example: g.example || g.example_chinese || '' // Support both
    });
  }, []);

  // Cancel editing
  const cancelEdit = useCallback(() => {
    setEditingId(null);
    setEditedGrammar({});
  }, []);

  // Save grammar point edits
  const saveGrammarEdit = useCallback(async (gp_uri) => {
    setSavingGrammar(true);
    try {
      const encoded_uri = encodeURIComponent(gp_uri);
      await axios.put(`${API_BASE}/vocabulary/grammar/${encoded_uri}`, editedGrammar);
      
      // Update local state
      setGrammarPoints(prev => prev.map(g => 
        g.gp_uri === gp_uri 
          ? { ...g, ...editedGrammar }
          : g
      ));
      
      setEditingId(null);
      setEditedGrammar({});
      alert(t('grammarUpdatedSuccess'));
    } catch (error) {
      console.error('Error saving grammar point:', error);
      alert(t('failedToSaveGrammar'));
    } finally {
      setSavingGrammar(false);
    }
  }, [editedGrammar]);

  // Select all visible grammar points
  const selectAllVisible = useCallback(() => {
    // Recalculate filtered grammar based on current filters
    let filtered = grammarPoints;
    if (selectedCEFR !== null) {
      filtered = filtered.filter(g => g.cefr_level === selectedCEFR);
    }
    if (searchTerm.trim()) {
      const searchLower = searchTerm.toLowerCase();
      filtered = filtered.filter(g =>
        g.grammar_point.toLowerCase().includes(searchLower) ||
        g.structure?.toLowerCase().includes(searchLower) ||
        g.explanation?.toLowerCase().includes(searchLower)
      );
    }
    
    // Show warning, especially for all CEFR levels
    const isAllLevels = selectedCEFR === null && !searchTerm.trim();
    const grammarCount = filtered.length;
    const alreadyMastered = filtered.filter(g => masteredSet.has(g.gp_uri)).length; // Use gp_uri
    const willAdd = grammarCount - alreadyMastered;
    
    let warningMessage = `⚠️ ` + (willAdd > 0
      ? t('selectAllVisibleGrammarConfirm')
          .replace('{count}', grammarCount.toLocaleString())
          .replace('{willAdd}', willAdd.toLocaleString())
          .replace('{alreadyMastered}', alreadyMastered.toLocaleString())
      : t('selectAllVisibleGrammarConfirmNoAdd').replace('{count}', grammarCount.toLocaleString()));
    
    if (isAllLevels) {
      warningMessage += `🚨 ` + t('selectAllVisibleGrammarWarnAllLevels');
    } else {
      warningMessage += t('selectAllVisibleGrammarConfirmContinue');
    }
    
    if (!window.confirm(warningMessage)) {
      return; // User cancelled
    }
    
    const newSet = new Set(masteredSet);
    filtered.forEach(g => {
      newSet.add(g.gp_uri); // Use gp_uri instead of grammar_point
    });
    setMasteredSet(newSet);
    saveMasteredGrammar(newSet, false);
  }, [masteredSet, saveMasteredGrammar, grammarPoints, selectedCEFR, searchTerm, t]);

  // Deselect all visible grammar points
  const deselectAllVisible = useCallback(() => {
    // Recalculate filtered grammar based on current filters
    let filtered = grammarPoints;
    if (selectedCEFR !== null) {
      filtered = filtered.filter(g => g.cefr_level === selectedCEFR);
    }
    if (searchTerm.trim()) {
      const searchLower = searchTerm.toLowerCase();
      filtered = filtered.filter(g =>
        g.grammar_point.toLowerCase().includes(searchLower) ||
        g.structure?.toLowerCase().includes(searchLower) ||
        g.explanation?.toLowerCase().includes(searchLower)
      );
    }
    
    const selectedCount = filtered.filter(g => masteredSet.has(g.gp_uri)).length; // Use gp_uri
    
    if (selectedCount === 0) {
      alert(t('deselectAllVisibleGrammarNoSelected'));
      return;
    }
    
    // Show warning
    const isAllLevels = selectedCEFR === null && !searchTerm.trim();
    let warningMessage = `⚠️ ` + t('deselectAllVisibleGrammarConfirm').replace('{count}', selectedCount.toLocaleString());
    
    if (isAllLevels && selectedCount > 50) {
      warningMessage += `🚨 ` + t('deselectAllVisibleGrammarWarnAllLevels');
    }
    warningMessage += t('selectAllVisibleGrammarConfirmContinue');
    
    if (!window.confirm(warningMessage)) {
      return; // User cancelled
    }
    
    const newSet = new Set(masteredSet);
    filtered.forEach(g => {
      newSet.delete(g.gp_uri); // Use gp_uri instead of grammar_point
    });
    setMasteredSet(newSet);
    saveMasteredGrammar(newSet, false);
  }, [masteredSet, saveMasteredGrammar, grammarPoints, selectedCEFR, searchTerm, t]);

  // Reset to original state (undo all changes)
  const resetToOriginal = useCallback(async () => {
    if (initialMasteredSetRef.current) {
      const restoredSet = new Set(initialMasteredSetRef.current);
      setMasteredSet(restoredSet);
      // Save immediately (bypass debounce)
      await saveMasteredGrammar(restoredSet, true);
    }
  }, [saveMasteredGrammar]);

  // Filter grammar points based on search and CEFR level
  const filteredGrammar = useMemo(() => {
    let filtered = grammarPoints;

    // Filter by CEFR level
    if (selectedCEFR !== null) {
      filtered = filtered.filter(g => g.cefr_level === selectedCEFR);
    }

    // Filter by search term
    if (searchTerm.trim()) {
      const searchLower = searchTerm.toLowerCase();
      filtered = filtered.filter(g =>
        g.grammar_point.toLowerCase().includes(searchLower) ||
        g.structure?.toLowerCase().includes(searchLower) ||
        g.explanation?.toLowerCase().includes(searchLower)
      );
    }

    // Limit display unless showAll is true
    if (!showAll && filtered.length > 100) {
      filtered = filtered.slice(0, 100);
    }

    return filtered;
  }, [grammarPoints, searchTerm, selectedCEFR, showAll]);

  // Calculate statistics
  const stats = useMemo(() => {
    const total = grammarPoints.length;
    // Count mastered items that actually exist in grammarPoints
    const mastered = grammarPoints.filter(g => masteredSet.has(g.gp_uri)).length;
    const byLevel = {};
    
    grammarPoints.forEach(g => {
      // Normalize empty string, null, undefined to 'unknown'
      const rawLevel = g.cefr_level;
      const level = (rawLevel && rawLevel.trim()) ? rawLevel.trim() : 'unknown';
      
      if (!byLevel[level]) {
        byLevel[level] = { total: 0, mastered: 0 };
      }
      byLevel[level].total++;
      if (masteredSet.has(g.gp_uri)) { // Use gp_uri instead of grammar_point
        byLevel[level].mastered++;
      }
    });

    // Verify totals add up
    const levelTotals = Object.values(byLevel).reduce((sum, levelStats) => sum + levelStats.total, 0);
    if (levelTotals !== total) {
      console.warn(`Stats mismatch: total=${total}, levelTotals=${levelTotals}`);
    }

    return { total, mastered, byLevel };
  }, [grammarPoints, masteredSet]);

  if (loading) {
    return <div style={{ padding: '20px', textAlign: 'center' }}>{t('loadingGrammarPoints')}</div>;
  }

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3>📚 {grammarLanguage === 'en' ? t('masteredGrammarTitleEnglish') : t('masteredGrammarTitleChinese')}</h3>
            <p style={{ color: '#666', fontSize: '14px', marginTop: '5px' }}>
              {t('masteredGrammarSubtitle')}
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {saving && (
              <span style={{ fontSize: '12px', color: '#666' }}>{t('savingGrammar')}</span>
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
            <strong>{t('totalMasteredGrammar')}:</strong> {stats.mastered} / {stats.total} {t('grammarPointsCount')}
          </div>
          {Object.keys(stats.byLevel)
            .sort((a, b) => {
              // Sort: A1, A2, B1, B2, C1, C2 first, then others
              const order = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'not specified', 'not mentioned', 'unknown'];
              const aIdx = order.indexOf(a);
              const bIdx = order.indexOf(b);
              if (aIdx !== -1 && bIdx !== -1) return aIdx - bIdx;
              if (aIdx !== -1) return -1;
              if (bIdx !== -1) return 1;
              return a.localeCompare(b);
            })
            .map(level => {
              const levelStats = stats.byLevel[level];
              if (!levelStats) return null;
              const percentage = levelStats.total > 0
                ? (levelStats.mastered / levelStats.total * 100).toFixed(1)
                : 0;
              const levelLabel = level === 'unknown' ? t('unknownUnspecifiedGrammar') : level === 'not specified' ? t('notSpecifiedGrammar') : level === 'not mentioned' ? t('notMentionedGrammar') : level;
              return (
                <div key={level}>
                  <strong>CEFR {levelLabel}:</strong> {levelStats.mastered} / {levelStats.total} ({percentage}%)
                </div>
              );
            })}
        </div>
      </div>

      {/* Language selector removed - language is selected in parent component */}

      {/* Filters */}
      <div style={{ marginBottom: '20px', display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          type="text"
          placeholder={t('searchGrammarPlaceholder')}
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
          <option value="A1">A1</option>
          <option value="A2">A2</option>
          <option value="B1">B1</option>
          <option value="B2">B2</option>
          <option value="C1">C1</option>
          <option value="C2">C2</option>
        </select>
      </div>

      {/* Bulk Actions */}
      <div style={{ marginBottom: '20px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
        <button
          onClick={selectAllVisible}
          className="btn"
          style={{ fontSize: '14px', padding: '8px 16px' }}
        >
          ✓ {t('selectAllVisibleGrammar').replace('{count}', filteredGrammar.length)}
        </button>
        <button
          onClick={deselectAllVisible}
          className="btn btn-secondary"
          style={{ fontSize: '14px', padding: '8px 16px' }}
        >
          ✗ {t('deselectAllVisibleGrammar')}
        </button>
        <button
          onClick={resetToOriginal}
          className="btn btn-secondary"
          style={{ fontSize: '14px', padding: '8px 16px', backgroundColor: '#ff9800', color: 'white' }}
        >
          ↶ {t('resetToOriginalGrammar')}
        </button>
      </div>

      {/* Grammar Points List */}
      <div style={{
        maxHeight: '500px',
        overflowY: 'auto',
        border: '1px solid #ddd',
        borderRadius: '4px',
        padding: '10px'
      }}>
        {filteredGrammar.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#666', padding: '20px' }}>
            {grammarPoints.length === 0 ? (
              <div>
                <p>{t('noGrammarPointsFound')}</p>
                <p style={{ fontSize: '12px', marginTop: '10px' }}>
                  {t('knowledgeGraphCheck')}
                </p>
              </div>
            ) : (
              t('noGrammarPointsMatching')
            )}
          </div>
        ) : (
          <>
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '10px'
            }}>
              {filteredGrammar.map((g) => {
                const isMastered = masteredSet.has(g.gp_uri); // Use gp_uri instead of grammar_point
                const isEditing = editingId === g.gp_uri;
                const editData = isEditing ? editedGrammar : g;
                
                return (
                  <div
                    key={g.gp_uri || g.grammar_point}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      padding: '12px',
                      borderRadius: '4px',
                      backgroundColor: isMastered ? '#e8f5e9' : isEditing ? '#fff3cd' : 'transparent',
                      border: isMastered ? '2px solid #4CAF50' : isEditing ? '2px solid #ffc107' : '1px solid #e0e0e0',
                      marginBottom: '10px'
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isMastered}
                      onChange={() => toggleGrammar(g.gp_uri)} // Use gp_uri instead of grammar_point
                      style={{ marginRight: '12px', marginTop: '4px', cursor: 'pointer', transform: 'scale(1.2)' }}
                    />
                    <div style={{ flex: 1 }}>
                      {isEditing ? (
                        // Edit mode
                        <div>
                          <div style={{ marginBottom: '10px' }}>
                            <label style={{ display: 'block', fontSize: '12px', color: '#666', marginBottom: '4px' }}>
                              {t('englishName')}
                            </label>
                            <input
                              type="text"
                              value={editData.grammar_point}
                              onChange={(e) => setEditedGrammar({...editData, grammar_point: e.target.value})}
                              style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '4px' }}
                            />
                          </div>
                          <div style={{ marginBottom: '10px' }}>
                            <label style={{ display: 'block', fontSize: '12px', color: '#666', marginBottom: '4px' }}>
                              {t('chineseTranslation')}
                            </label>
                            <input
                              type="text"
                              value={editData.grammar_point_zh}
                              onChange={(e) => setEditedGrammar({...editData, grammar_point_zh: e.target.value})}
                              style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '4px' }}
                            />
                          </div>
                          <div style={{ marginBottom: '10px' }}>
                            <label style={{ display: 'block', fontSize: '12px', color: '#666', marginBottom: '4px' }}>
                              {t('structureLabel')}
                            </label>
                            <input
                              type="text"
                              value={editData.structure}
                              onChange={(e) => setEditedGrammar({...editData, structure: e.target.value})}
                              style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '4px', fontFamily: 'monospace' }}
                            />
                          </div>
                          <div style={{ marginBottom: '10px' }}>
                            <label style={{ display: 'block', fontSize: '12px', color: '#666', marginBottom: '4px' }}>
                              {t('exampleLabel')} ({grammarLanguage === 'en' ? t('english') : t('chinese')}):
                            </label>
                            <input
                              type="text"
                              value={grammarLanguage === 'en' ? (editData.example || '') : (editData.example_chinese || '')}
                              onChange={(e) => {
                                if (grammarLanguage === 'en') {
                                  setEditedGrammar({...editData, example: e.target.value});
                                } else {
                                  setEditedGrammar({...editData, example_chinese: e.target.value});
                                }
                              }}
                              style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '4px' }}
                            />
                          </div>
                          <div style={{ marginBottom: '10px' }}>
                            <label style={{ display: 'block', fontSize: '12px', color: '#666', marginBottom: '4px' }}>
                              {t('explanationLabel')}
                            </label>
                            <textarea
                              value={editData.explanation}
                              onChange={(e) => setEditedGrammar({...editData, explanation: e.target.value})}
                              rows={4}
                              style={{ width: '100%', padding: '6px', border: '1px solid #ddd', borderRadius: '4px', resize: 'vertical' }}
                            />
                          </div>
                          <div style={{ marginBottom: '10px' }}>
                            <label style={{ display: 'block', fontSize: '12px', color: '#666', marginBottom: '4px' }}>
                              {t('cefrLevel')}
                            </label>
                            <select
                              value={editData.cefr_level || ''}
                              onChange={(e) => setEditedGrammar({...editData, cefr_level: e.target.value})}
                              style={{ padding: '6px', border: '1px solid #ddd', borderRadius: '4px' }}
                            >
                              <option value="">{t('notSpecifiedGrammar')}</option>
                              <option value="A1">A1</option>
                              <option value="A2">A2</option>
                              <option value="B1">B1</option>
                              <option value="B2">B2</option>
                              <option value="C1">C1</option>
                              <option value="C2">C2</option>
                            </select>
                          </div>
                          <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
                            <button
                              onClick={() => saveGrammarEdit(g.gp_uri)}
                              disabled={savingGrammar}
                              className="btn"
                              style={{ fontSize: '14px', padding: '6px 12px', backgroundColor: '#4CAF50', color: 'white' }}
                            >
                              {savingGrammar ? t('savingGrammar') : t('saveButton')}
                            </button>
                            <button
                              onClick={cancelEdit}
                              className="btn btn-secondary"
                              style={{ fontSize: '14px', padding: '6px 12px' }}
                            >
                              {t('cancelButton')}
                            </button>
                          </div>
                        </div>
                      ) : (
                        // View mode
                        <>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '4px' }}>
                            <div style={{ fontWeight: 'bold', fontSize: '16px', flex: 1 }}>
                              {grammarLanguage === 'en' ? (
                                <>
                                  {editData.grammar_point}
                                  {editData.grammar_point_zh && (
                                    <span style={{ fontSize: '12px', color: '#999', fontWeight: 'normal', marginLeft: '8px' }}>
                                      ({editData.grammar_point_zh})
                                    </span>
                                  )}
                                </>
                              ) : (
                                <>
                                  {editData.grammar_point_zh || editData.grammar_point}
                                  {editData.grammar_point_zh && editData.grammar_point !== editData.grammar_point_zh && (
                                    <span style={{ fontSize: '12px', color: '#999', fontWeight: 'normal', marginLeft: '8px' }}>
                                      ({editData.grammar_point})
                                    </span>
                                  )}
                                </>
                              )}
                            </div>
                            <div style={{ display: 'flex', gap: '8px' }}>
                              <button
                                onClick={() => {
                                  setChatTopic(g.gp_uri);
                                  setChatTopicName(g.grammar_point || g.grammar_point_zh || g.gp_uri);
                                }}
                                className="btn btn-secondary"
                                style={{ fontSize: '12px', padding: '4px 8px' }}
                                title={t('chatAboutGrammar')}
                              >
                                💬 {t('chatButton')}
                              </button>
                              <button
                                onClick={() => startEdit(g)}
                                className="btn btn-secondary"
                                style={{ fontSize: '12px', padding: '4px 8px' }}
                                title={t('editGrammarPoint')}
                              >
                                ✏️ {t('editButton')}
                              </button>
                            </div>
                          </div>
                          
                          {editData.structure && (
                            <div style={{ fontSize: '14px', color: '#555', marginBottom: '4px', fontFamily: 'monospace' }}>
                              {editData.structure}
                            </div>
                          )}
                          
                          {/* Explanation with example at the beginning */}
                          {editData.explanation && (
                            <div style={{ fontSize: '13px', color: '#666', marginBottom: '4px' }}>
                              {/* Example sentence at the beginning of the explanation text */}
                              {(editData.example_chinese || editData.example) && (
                                <div style={{
                                  fontSize: '15px',
                                  fontWeight: '500',
                                  color: '#1976d2',
                                  marginBottom: '6px',
                                  fontStyle: 'italic'
                                }}>
                                  {editData.example_chinese || editData.example || ''}
                                </div>
                              )}
                              {editData.explanation.length > 150 ? `${editData.explanation.substring(0, 150)}...` : editData.explanation}
                            </div>
                          )}
                          
                          {/* If no explanation but there's an example, show it */}
                          {!editData.explanation && (editData.example_chinese || editData.example) && (
                            <div style={{ fontSize: '13px', color: '#666', marginBottom: '4px' }}>
                              <div style={{
                                fontSize: '15px',
                                fontWeight: '500',
                                color: '#1976d2',
                                marginBottom: '6px',
                                fontStyle: 'italic'
                              }}>
                                {editData.example_chinese || editData.example || ''}
                              </div>
                            </div>
                          )}
                          
                          <div style={{ fontSize: '11px', color: '#999', marginTop: '4px' }}>
                            {t('cefrLevel')} {editData.cefr_level || t('notSpecifiedGrammar')}
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            {!showAll && filteredGrammar.length >= 100 && (
              <div style={{ textAlign: 'center', marginTop: '15px' }}>
                <button
                  onClick={() => setShowAll(true)}
                  className="btn"
                  style={{ fontSize: '14px' }}
                >
                  {t('showAllResultsGrammar')}
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Topic Chat Drawer */}
      {chatTopic && (
        <>
          {/* Backdrop */}
          <div
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: 'rgba(0, 0, 0, 0.3)',
              zIndex: 1000
            }}
            onClick={() => {
              setChatTopic(null);
              setChatTopicName(null);
            }}
          />
          {/* Chat Drawer */}
          <TopicChat
            topicId={chatTopic}
            topicName={chatTopicName}
            profile={profile}
            onClose={() => {
              setChatTopic(null);
              setChatTopicName(null);
            }}
          />
        </>
      )}
    </div>
  );
};

export default MasteredGrammarManager;
