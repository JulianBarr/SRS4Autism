import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { useLanguage } from '../i18n/LanguageContext';
import MasteredWordsManager from './MasteredWordsManager';
import MasteredEnglishWordsManager from './MasteredEnglishWordsManager';
import MasteredGrammarManager from './MasteredGrammarManager';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const LanguageContentManager = ({ profile, onProfileUpdate }) => {
  const { t } = useLanguage();
  
  // Chinese Word Recommendations State
  const [showRecommendations, setShowRecommendations] = useState(false);
  const [recommendations, setRecommendations] = useState([]);
  const [loadingRecommendations, setLoadingRecommendations] = useState(false);
  const [selectedRecommendations, setSelectedRecommendations] = useState(new Set());
  const [savingMasteredWords, setSavingMasteredWords] = useState(false);
  const [concretenessWeight, setConcretenessWeight] = useState(0.5);
  
  // Mastered Managers State
  const [showMasteredWordsManager, setShowMasteredWordsManager] = useState(false);
  const [showMasteredEnglishWordsManager, setShowMasteredEnglishWordsManager] = useState(false);
  const [showMasteredGrammarManager, setShowMasteredGrammarManager] = useState(false);
  
  // English Word Recommendations State
  const [showEnglishRecommendations, setShowEnglishRecommendations] = useState(false);
  const [englishRecommendations, setEnglishRecommendations] = useState([]);
  const [loadingEnglishRecommendations, setLoadingEnglishRecommendations] = useState(false);
  const [selectedEnglishRecommendations, setSelectedEnglishRecommendations] = useState(new Set());
  const [savingMasteredEnglishWords, setSavingMasteredEnglishWords] = useState(false);
  const [englishSliderPosition, setEnglishSliderPosition] = useState(0.5);
  const [recommendationsKey, setRecommendationsKey] = useState(0);
  
  const englishRecommendationsAbortController = useRef(null);
  const englishRecommendationsRequestId = useRef(0);
  const sliderDebounceTimer = useRef(null);

  // Grammar Recommendations State
  const [showGrammarRecommendations, setShowGrammarRecommendations] = useState(false);
  const [grammarRecommendations, setGrammarRecommendations] = useState([]);
  const [loadingGrammarRecommendations, setLoadingGrammarRecommendations] = useState(false);
  const [selectedGrammarRecommendations, setSelectedGrammarRecommendations] = useState(new Set());
  const [savingMasteredGrammar, setSavingMasteredGrammar] = useState(false);
  const [grammarLanguage, setGrammarLanguage] = useState('zh');

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (englishRecommendationsAbortController.current) {
        englishRecommendationsAbortController.current.abort();
      }
      if (sliderDebounceTimer.current) {
        clearTimeout(sliderDebounceTimer.current);
      }
    };
  }, []);

  const parseMasteredEnglishWords = (text) => {
    if (!text) return [];
    return text
      .split(',')
      .map(w => w.trim())
      .filter(Boolean);
  };

  if (!profile) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
        <p>{t('pleaseSelectProfile') || "Please select a child profile to view language content."}</p>
      </div>
    );
  }

  // --- Chinese Recommendations ---

  const handleGetRecommendations = async (weight = null) => {
    setLoadingRecommendations(true);
    setSelectedRecommendations(new Set());
    
    const weightToUse = weight !== null ? weight : concretenessWeight;
    
    try {
      const mastered_words_array = profile.mastered_words 
        ? profile.mastered_words.split(/[,\s，]+/).filter(w => w.trim())
        : [];
      
      const response = await axios.post(`${API_BASE}/kg/recommendations`, {
        mastered_words: mastered_words_array,
        profile_id: profile.id || profile.name,
        concreteness_weight: weightToUse
      });
      
      setRecommendations(response.data.recommendations || []);
      setShowRecommendations(true);
    } catch (error) {
      console.error('Error getting recommendations:', error);
      alert('Failed to get recommendations. Please check if the knowledge graph server is running.');
    } finally {
      setLoadingRecommendations(false);
    }
  };

  const handleToggleRecommendation = (word) => {
    setSelectedRecommendations(prev => {
      const newSet = new Set(prev);
      if (newSet.has(word)) {
        newSet.delete(word);
      } else {
        newSet.add(word);
      }
      return newSet;
    });
  };

  const handleAddSelectedToMastered = async () => {
    if (selectedRecommendations.size === 0) return;

    setSavingMasteredWords(true);
    try {
      const currentMastered = profile.mastered_words 
        ? profile.mastered_words.split(/[,\s，]+/).map(w => w.trim()).filter(w => w)
        : [];
      
      const newMastered = [...new Set([...currentMastered, ...Array.from(selectedRecommendations)])];
      
      const updatedProfile = {
        ...profile,
        mastered_words: newMastered.join(', ')
      };
      
      await axios.put(`${API_BASE}/profiles/${profile.name}`, updatedProfile);
      if (onProfileUpdate) onProfileUpdate();
      
      const addedCount = selectedRecommendations.size;
      setSelectedRecommendations(new Set());
      alert(`✅ Successfully added ${addedCount} word(s) to mastered list!`);
    } catch (error) {
      console.error('Error adding words to mastered list:', error);
      alert('Failed to add words to mastered list.');
    } finally {
      setSavingMasteredWords(false);
    }
  };

  // --- English Recommendations ---

  const handleGetEnglishRecommendations = async (sliderPos = null) => {
    if (englishRecommendationsAbortController.current) {
      englishRecommendationsAbortController.current.abort();
    }
    
    const abortController = new AbortController();
    englishRecommendationsAbortController.current = abortController;
    const currentRequestId = ++englishRecommendationsRequestId.current;
    
    setLoadingEnglishRecommendations(true);
    setSelectedEnglishRecommendations(new Set());
    
    const sliderValue = sliderPos !== null ? sliderPos : englishSliderPosition;
    
    try {
      const mastered_words_array = parseMasteredEnglishWords(profile.mastered_english_words);
      const mentalAge = profile.mental_age ? parseFloat(profile.mental_age) : null;
      
      const response = await axios.post(`${API_BASE}/kg/english-recommendations?t=${Date.now()}`, {
        mastered_words: mastered_words_array,
        profile_id: profile.id || profile.name,
        concreteness_weight: sliderValue,
        mental_age: mentalAge
      }, {
        headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' },
        signal: abortController.signal
      });
      
      if (currentRequestId !== englishRecommendationsRequestId.current) return;
      
      const newRecommendations = [...(response.data.recommendations || [])];
      newRecommendations.sort((a, b) => (b.score || 0) - (a.score || 0));
      
      setRecommendationsKey(prev => prev + 1);
      setEnglishRecommendations(newRecommendations);
      setShowEnglishRecommendations(true);
    } catch (error) {
      if (error.name === 'CanceledError' || error.message === 'canceled') return;
      if (currentRequestId !== englishRecommendationsRequestId.current) return;
      console.error('Error getting English recommendations:', error);
      alert('Failed to get English recommendations.');
    } finally {
      if (currentRequestId === englishRecommendationsRequestId.current) {
        setLoadingEnglishRecommendations(false);
      }
    }
  };

  const handleToggleEnglishRecommendation = (word) => {
    setSelectedEnglishRecommendations(prev => {
      const newSet = new Set(prev);
      if (newSet.has(word)) {
        newSet.delete(word);
      } else {
        newSet.add(word);
      }
      return newSet;
    });
  };

  const handleAddSelectedEnglishToMastered = async () => {
    if (selectedEnglishRecommendations.size === 0) return;

    setSavingMasteredEnglishWords(true);
    try {
      const currentMastered = parseMasteredEnglishWords(profile.mastered_english_words);
      const newMastered = [...new Set([...currentMastered, ...Array.from(selectedEnglishRecommendations)])];
      
      const updatedProfile = {
        ...profile,
        mastered_english_words: newMastered.join(', ')
      };
      
      await axios.put(`${API_BASE}/profiles/${profile.name}`, updatedProfile);
      if (onProfileUpdate) {
        await onProfileUpdate(); // Wait for update
        // Re-fetch recommendations to reflect changes
        // Note: We can't easily re-fetch here without the updated profile object from the parent
        // Ideally onProfileUpdate returns the updated profile or we rely on props updating
      }
      
      const addedCount = selectedEnglishRecommendations.size;
      setSelectedEnglishRecommendations(new Set());
      alert(`✅ Successfully added ${addedCount} word(s) to mastered English words list!`);
      
      // Trigger re-fetch if profile updates prop, otherwise we might need to manually handle it
      // For now, we rely on parent updating the profile prop
    } catch (error) {
      console.error('Error adding English words to mastered list:', error);
      alert('Failed to add words to mastered list.');
    } finally {
      setSavingMasteredEnglishWords(false);
    }
  };

  // --- Grammar Recommendations ---

  const handleGetGrammarRecommendations = async (lang = 'zh') => {
    setLoadingGrammarRecommendations(true);
    setSelectedGrammarRecommendations(new Set());
    setGrammarLanguage(lang);
    
    try {
      const mastered_grammar_array = profile.mastered_grammar 
        ? profile.mastered_grammar.split(',').map(g => g.trim()).filter(g => g)
        : [];
      
      const response = await axios.post(`${API_BASE}/kg/grammar-recommendations`, {
        mastered_grammar: mastered_grammar_array,
        profile_id: profile.id || profile.name,
        language: lang
      });
      
      setGrammarRecommendations(response.data.recommendations || []);
      setShowGrammarRecommendations(true);
    } catch (error) {
      console.error('Error getting grammar recommendations:', error);
      alert('Failed to get grammar recommendations.');
    } finally {
      setLoadingGrammarRecommendations(false);
    }
  };

  const handleToggleGrammarRecommendation = (grammarPoint) => {
    setSelectedGrammarRecommendations(prev => {
      const newSet = new Set(prev);
      if (newSet.has(grammarPoint)) {
        newSet.delete(grammarPoint);
      } else {
        newSet.add(grammarPoint);
      }
      return newSet;
    });
  };

  const handleAddSelectedGrammarToMastered = async () => {
    if (selectedGrammarRecommendations.size === 0) return;

    setSavingMasteredGrammar(true);
    try {
      const currentMastered = profile.mastered_grammar 
        ? profile.mastered_grammar.split(',').map(g => g.trim()).filter(g => g)
        : [];
      
      const newMastered = [...new Set([...currentMastered, ...Array.from(selectedGrammarRecommendations)])];
      
      const updatedProfile = {
        ...profile,
        mastered_grammar: newMastered.join(',')
      };
      
      await axios.put(`${API_BASE}/profiles/${profile.name}`, updatedProfile);
      if (onProfileUpdate) onProfileUpdate();
      
      const addedCount = selectedGrammarRecommendations.size;
      setSelectedGrammarRecommendations(new Set());
      alert(`✅ Successfully added ${addedCount} grammar point(s) to mastered list!`);
    } catch (error) {
      console.error('Error adding grammar to mastered list:', error);
      alert('Failed to add grammar to mastered list.');
    } finally {
      setSavingMasteredGrammar(false);
    }
  };

  return (
    <div style={{ padding: '20px' }}>
      {/* Action Buttons */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '20px' }}>
        <button 
          onClick={() => setShowMasteredWordsManager(true)}
          className="btn"
        >
          📝 {t('manageMasteredWords')} ({t('chineseVocabulary')})
        </button>
        <button 
          onClick={() => setShowMasteredEnglishWordsManager(true)}
          className="btn"
        >
          📝 {t('manageMasteredEnglishWords')}
        </button>
        <button 
          onClick={() => setShowMasteredGrammarManager(true)}
          className="btn"
        >
          📖 {t('manageMasteredGrammar')}
        </button>
      </div>
      
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '20px' }}>
        <button 
          onClick={() => handleGetRecommendations()}
          className="btn"
          disabled={loadingRecommendations}
        >
          {loadingRecommendations ? t('loading') || 'Loading...' : `📚 ${t('getWordRecommendations')} ({t('chineseVocabulary')})`}
        </button>
        <button 
          onClick={() => handleGetEnglishRecommendations()}
          className="btn"
          disabled={loadingEnglishRecommendations}
        >
          {loadingEnglishRecommendations ? t('loading') || 'Loading...' : `📚 ${t('getWordRecommendations')} ({t('englishVocabulary')})`}
        </button>
        <button 
          onClick={() => handleGetGrammarRecommendations()}
          className="btn"
          disabled={loadingGrammarRecommendations}
        >
          {loadingGrammarRecommendations ? t('loading') || 'Loading...' : `📖 ${t('getGrammarRecommendations')}`}
        </button>
      </div>

      {/* Modals - Using the same structure as ProfileManager but adapted */}
      
      {/* Chinese Recommendations Modal */}
      {showRecommendations && (
        <div className="modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'white', padding: '30px', borderRadius: '8px',
            maxWidth: '600px', maxHeight: '80vh', overflow: 'auto', position: 'relative'
          }}>
            <button onClick={() => setShowRecommendations(false)} style={{
              position: 'absolute', top: '10px', right: '10px', border: 'none', background: 'none', fontSize: '24px', cursor: 'pointer'
            }}>×</button>
            <h2>📚 {t('wordRecommendations')}</h2>
            
            {/* Concreteness Weight Control */}
            <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: '#f5f5f5', borderRadius: '8px', border: '1px solid #ddd' }}>
              <label style={{ display: 'block', marginBottom: '10px', fontWeight: 'bold', fontSize: '14px' }}>
                ⚖️ Recommendation Balance:
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                <span style={{ fontSize: '12px', color: '#666', minWidth: '100px' }}>HSK Level Only</span>
                <input
                  type="range" min="0" max="1" step="0.1" value={concretenessWeight}
                  onChange={(e) => {
                    const newWeight = parseFloat(e.target.value);
                    setConcretenessWeight(newWeight);
                    handleGetRecommendations(newWeight);
                  }}
                  style={{ flex: 1, cursor: 'pointer' }}
                />
                <span style={{ fontSize: '12px', color: '#666', minWidth: '100px', textAlign: 'right' }}>Concreteness Only</span>
              </div>
              {/* ... simplified label ... */}
            </div>
            
            {recommendations.length === 0 ? (
              <p>{t('noRecommendations')}. {t('pleaseAddMasteredWords')}</p>
            ) : (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <p style={{ color: '#666', margin: 0 }}>Next 50 words to learn:</p>
                  {selectedRecommendations.size > 0 && (
                    <button
                      onClick={handleAddSelectedToMastered}
                      disabled={savingMasteredWords}
                      className="btn"
                      style={{ backgroundColor: '#4CAF50', color: 'white' }}
                    >
                      {savingMasteredWords ? `💾 ${t('saving')}` : `✓ ${t('addSelected')} (${selectedRecommendations.size})`}
                    </button>
                  )}
                </div>
                <ol style={{ paddingLeft: '20px' }}>
                  {recommendations.map((rec, idx) => {
                    const isSelected = selectedRecommendations.has(rec.word);
                    const isAlreadyMastered = profile.mastered_words?.split(/[,\s，]+/).map(w => w.trim()).includes(rec.word);
                    
                    return (
                      <li key={rec.word || idx} style={{ marginBottom: '15px' }}>
                        <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                          <input
                            type="checkbox" checked={isSelected} disabled={isAlreadyMastered}
                            onChange={() => handleToggleRecommendation(rec.word)}
                            style={{ marginRight: '10px' }}
                          />
                          <div>
                            <div style={{ fontWeight: 'bold' }}>
                              {rec.word} {rec.pinyin && <span style={{ color: '#666', fontSize: '0.9em' }}>({rec.pinyin})</span>}
                              {isAlreadyMastered && <span style={{ fontSize: '12px', color: '#ff9800', marginLeft: '8px' }}>({t('alreadyMastered')})</span>}
                            </div>
                            <div style={{ fontSize: '0.8em', color: '#888' }}>
                              HSK: {rec.hsk} | Score: {typeof rec.score === 'number' ? rec.score.toFixed(1) : rec.score}
                            </div>
                          </div>
                        </label>
                      </li>
                    );
                  })}
                </ol>
              </div>
            )}
          </div>
        </div>
      )}

      {/* English Recommendations Modal */}
      {showEnglishRecommendations && (
        <div className="modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'white', padding: '30px', borderRadius: '8px',
            maxWidth: '600px', maxHeight: '80vh', overflow: 'auto', position: 'relative'
          }}>
            <button onClick={() => setShowEnglishRecommendations(false)} style={{
              position: 'absolute', top: '10px', right: '10px', border: 'none', background: 'none', fontSize: '24px', cursor: 'pointer'
            }}>×</button>
            <h2>📚 {t('englishRecommendations')}</h2>
            
            <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: '#f5f5f5', borderRadius: '8px', border: '1px solid #ddd' }}>
              <label style={{ display: 'block', marginBottom: '10px', fontWeight: 'bold', fontSize: '14px' }}>
                ⚖️ Recommendation Balance (English):
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                <span style={{ fontSize: '12px', color: '#666', minWidth: '120px' }}>Frequency (Utility)</span>
                <input
                  type="range" min="0" max="1" step="0.1" value={englishSliderPosition}
                  onChange={(e) => {
                    const newPos = parseFloat(e.target.value);
                    setEnglishSliderPosition(newPos);
                    if (sliderDebounceTimer.current) clearTimeout(sliderDebounceTimer.current);
                    sliderDebounceTimer.current = setTimeout(() => {
                      handleGetEnglishRecommendations(newPos);
                    }, 300);
                  }}
                  style={{ flex: 1, cursor: 'pointer' }}
                />
                <span style={{ fontSize: '12px', color: '#666', minWidth: '120px', textAlign: 'right' }}>Concreteness (Ease)</span>
              </div>
            </div>

            {englishRecommendations.length === 0 ? (
              <p>{t('noRecommendations')}. {t('pleaseAddMasteredEnglishWords')}</p>
            ) : (
              <div>
                 <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <p style={{ color: '#666', margin: 0 }}>Next 50 words to learn:</p>
                  {selectedEnglishRecommendations.size > 0 && (
                    <button
                      onClick={handleAddSelectedEnglishToMastered}
                      disabled={savingMasteredEnglishWords}
                      className="btn"
                      style={{ backgroundColor: '#4CAF50', color: 'white' }}
                    >
                      {savingMasteredEnglishWords ? `💾 ${t('saving')}` : `✓ ${t('addSelected')} (${selectedEnglishRecommendations.size})`}
                    </button>
                  )}
                </div>
                <ol key={recommendationsKey} style={{ paddingLeft: '20px' }}>
                  {englishRecommendations.map((rec, idx) => {
                    const isSelected = selectedEnglishRecommendations.has(rec.word);
                    const isAlreadyMastered = parseMasteredEnglishWords(profile.mastered_english_words).includes(rec.word);
                    
                    return (
                      <li key={`${rec.word}-${idx}`} style={{ marginBottom: '15px' }}>
                        <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                          <input
                            type="checkbox" checked={isSelected} disabled={isAlreadyMastered}
                            onChange={() => handleToggleEnglishRecommendation(rec.word)}
                            style={{ marginRight: '10px' }}
                          />
                          <div>
                            <div style={{ fontWeight: 'bold' }}>
                              {rec.word}
                              {isAlreadyMastered && <span style={{ fontSize: '12px', color: '#ff9800', marginLeft: '8px' }}>({t('alreadyMastered')})</span>}
                            </div>
                            <div style={{ fontSize: '0.8em', color: '#888' }}>
                              CEFR: {rec.cefr_level || '-'} | Score: {rec.score?.toFixed(2)}
                            </div>
                          </div>
                        </label>
                      </li>
                    );
                  })}
                </ol>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Grammar Recommendations Modal */}
      {showGrammarRecommendations && (
        <div className="modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'white', padding: '30px', borderRadius: '8px',
            maxWidth: '600px', maxHeight: '80vh', overflow: 'auto', position: 'relative'
          }}>
            <button onClick={() => setShowGrammarRecommendations(false)} style={{
              position: 'absolute', top: '10px', right: '10px', border: 'none', background: 'none', fontSize: '24px', cursor: 'pointer'
            }}>×</button>
            <h2>📖 {t('grammarRecommendations')} ({grammarLanguage === 'en' ? t('englishGrammar') : t('chineseGrammar')})</h2>
            
            <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
               <button onClick={() => handleGetGrammarRecommendations('zh')} className="btn" style={{
                 backgroundColor: grammarLanguage === 'zh' ? '#1976d2' : '#e0e0e0', color: grammarLanguage === 'zh' ? 'white' : '#333'
               }}>中文</button>
               <button onClick={() => handleGetGrammarRecommendations('en')} className="btn" style={{
                 backgroundColor: grammarLanguage === 'en' ? '#1976d2' : '#e0e0e0', color: grammarLanguage === 'en' ? 'white' : '#333'
               }}>English</button>
            </div>

            {grammarRecommendations.length === 0 ? (
              <p>No grammar recommendations available.</p>
            ) : (
              <div>
                 <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <p style={{ color: '#666', margin: 0 }}>Next 50 grammar points:</p>
                  {selectedGrammarRecommendations.size > 0 && (
                    <button
                      onClick={handleAddSelectedGrammarToMastered}
                      disabled={savingMasteredGrammar}
                      className="btn"
                      style={{ backgroundColor: '#4CAF50', color: 'white' }}
                    >
                      {savingMasteredGrammar ? `💾 ${t('saving')}` : `✓ ${t('addSelected')} (${selectedGrammarRecommendations.size})`}
                    </button>
                  )}
                </div>
                <ol style={{ paddingLeft: '20px' }}>
                  {grammarRecommendations.map((rec, idx) => {
                    const isSelected = selectedGrammarRecommendations.has(rec.gp_uri || rec.grammar_point);
                    const isAlreadyMastered = profile.mastered_grammar?.split(',').map(g => g.trim()).includes(rec.gp_uri || rec.grammar_point);
                    
                    return (
                      <li key={idx} style={{ marginBottom: '15px' }}>
                         <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                          <input
                            type="checkbox" checked={isSelected} disabled={isAlreadyMastered}
                            onChange={() => handleToggleGrammarRecommendation(rec.gp_uri || rec.grammar_point)}
                            style={{ marginRight: '10px' }}
                          />
                          <div>
                            <div style={{ fontWeight: 'bold' }}>
                              {grammarLanguage === 'en' ? rec.grammar_point : (rec.grammar_point_zh || rec.grammar_point)}
                              {isAlreadyMastered && <span style={{ fontSize: '12px', color: '#ff9800', marginLeft: '8px' }}>({t('alreadyMastered')})</span>}
                            </div>
                            <div style={{ fontSize: '0.8em', color: '#888' }}>
                              {rec.structure}
                            </div>
                          </div>
                        </label>
                      </li>
                    );
                  })}
                </ol>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Mastered Managers Modals */}
      {showMasteredWordsManager && (
        <div className="modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'white', padding: '20px', borderRadius: '8px', width: '90%', maxWidth: '900px', maxHeight: '90vh', overflow: 'auto', position: 'relative'
          }}>
            <button onClick={() => setShowMasteredWordsManager(false)} style={{
              position: 'absolute', top: '10px', right: '10px', border: 'none', background: 'none', fontSize: '24px', cursor: 'pointer'
            }}>×</button>
            <MasteredWordsManager profile={profile} onUpdate={onProfileUpdate} />
          </div>
        </div>
      )}

      {showMasteredEnglishWordsManager && (
         <div className="modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'white', padding: '20px', borderRadius: '8px', width: '90%', maxWidth: '900px', maxHeight: '90vh', overflow: 'auto', position: 'relative'
          }}>
            <button onClick={() => setShowMasteredEnglishWordsManager(false)} style={{
              position: 'absolute', top: '10px', right: '10px', border: 'none', background: 'none', fontSize: '24px', cursor: 'pointer'
            }}>×</button>
            <MasteredEnglishWordsManager profile={profile} onUpdate={onProfileUpdate} />
          </div>
        </div>
      )}

      {showMasteredGrammarManager && (
         <div className="modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'white', padding: '20px', borderRadius: '8px', width: '90%', maxWidth: '900px', maxHeight: '90vh', overflow: 'auto', position: 'relative'
          }}>
            <button onClick={() => setShowMasteredGrammarManager(false)} style={{
              position: 'absolute', top: '10px', right: '10px', border: 'none', background: 'none', fontSize: '24px', cursor: 'pointer'
            }}>×</button>
            <MasteredGrammarManager profile={profile} onUpdate={onProfileUpdate} />
          </div>
        </div>
      )}

    </div>
  );
};

export default LanguageContentManager;

