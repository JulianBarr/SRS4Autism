import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { useLanguage } from '../i18n/LanguageContext';
import MasteredWordsManager from './MasteredWordsManager';
import MasteredEnglishWordsManager from './MasteredEnglishWordsManager';
import MasteredGrammarManager from './MasteredGrammarManager';
import CharacterRecognition from './CharacterRecognition';
import theme from '../styles/theme';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const LanguageContentManager = ({ profile, onProfileUpdate }) => {
  const { t } = useLanguage();
  
  // Hierarchy: Language -> Content Type -> Actions
  const [selectedLanguage, setSelectedLanguage] = useState('zh'); // 'zh' or 'en'
  const [selectedContentType, setSelectedContentType] = useState('word'); // 'character', 'word', 'grammar', 'pragmatics'
  
  // Chinese Word Recommendations State
  const [showRecommendations, setShowRecommendations] = useState(false);
  const [recommendations, setRecommendations] = useState([]);
  const [loadingRecommendations, setLoadingRecommendations] = useState(false);
  const [selectedRecommendations, setSelectedRecommendations] = useState(new Set());
  const [savingMasteredWords, setSavingMasteredWords] = useState(false);
  const [concretenessWeight, setConcretenessWeight] = useState(0.5);
  const [useChinesePPRAlgorithm, setUseChinesePPRAlgorithm] = useState(false); // Toggle between PPR and old algorithm for Chinese
  
  // Chinese PPR Algorithm Configuration State
  const [chinesePprConfig, setChinesePprConfig] = useState({
    beta_ppr: 1.0,
    beta_concreteness: 0.8,
    beta_frequency: 0.3,
    beta_aoa_penalty: 2.0,
    beta_intercept: 0.0,
    alpha: 0.5,
    mental_age: null, // Will use profile.mental_age if available
    aoa_buffer: 0.0,
    top_n: 50,
    exclude_multiword: false
  });
  const [showChinesePprConfig, setShowChinesePprConfig] = useState(false);
  
  // Mastered Managers State
  const [showMasteredWordsManager, setShowMasteredWordsManager] = useState(false);
  const [showMasteredEnglishWordsManager, setShowMasteredEnglishWordsManager] = useState(false);
  const [showMasteredGrammarManager, setShowMasteredGrammarManager] = useState(false);
  const [showCharacterRecognition, setShowCharacterRecognition] = useState(false);
  
  // English Word Recommendations State
  const [showEnglishRecommendations, setShowEnglishRecommendations] = useState(false);
  const [englishRecommendations, setEnglishRecommendations] = useState([]);
  const [loadingEnglishRecommendations, setLoadingEnglishRecommendations] = useState(false);
  const [selectedEnglishRecommendations, setSelectedEnglishRecommendations] = useState(new Set());
  const [savingMasteredEnglishWords, setSavingMasteredEnglishWords] = useState(false);
  const [englishSliderPosition, setEnglishSliderPosition] = useState(0.5);
  const [recommendationsKey, setRecommendationsKey] = useState(0);
  const [usePPRAlgorithm, setUsePPRAlgorithm] = useState(false); // Toggle between PPR and old algorithm
  
  // PPR Algorithm Configuration State
  const [pprConfig, setPprConfig] = useState({
    beta_ppr: 1.0,
    beta_concreteness: 0.8,
    beta_frequency: 0.3,
    beta_aoa_penalty: 2.0,
    beta_intercept: 0.0,
    alpha: 0.5,
    mental_age: null, // Will use profile.mental_age if available
    aoa_buffer: 0.0,
    top_n: 50,
    exclude_multiword: false
  });
  const [showPprConfig, setShowPprConfig] = useState(false);
  
  const englishRecommendationsAbortController = useRef(null);
  const englishRecommendationsRequestId = useRef(0);
  const sliderDebounceTimer = useRef(null);

  // Grammar Recommendations State
  const [showGrammarRecommendations, setShowGrammarRecommendations] = useState(false);
  const [grammarRecommendations, setGrammarRecommendations] = useState([]);
  const [loadingGrammarRecommendations, setLoadingGrammarRecommendations] = useState(false);
  const [selectedGrammarRecommendations, setSelectedGrammarRecommendations] = useState(new Set());
  const [savingMasteredGrammar, setSavingMasteredGrammar] = useState(false);

  // Integrated Recommendations State (PPR + ZPD + Campaign Manager)
  const [showIntegratedRecommendations, setShowIntegratedRecommendations] = useState(false);
  const [integratedRecommendations, setIntegratedRecommendations] = useState([]);
  const [loadingIntegratedRecommendations, setLoadingIntegratedRecommendations] = useState(false);
  const [selectedIntegratedRecommendations, setSelectedIntegratedRecommendations] = useState(new Set());
  const [allocationInfo, setAllocationInfo] = useState(null);

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

  // Initialize mental_age from profile when available (for both English and Chinese)
  useEffect(() => {
    if (profile?.mental_age) {
      const mentalAge = parseFloat(profile.mental_age);
      if (!isNaN(mentalAge)) {
        setPprConfig(prev => ({ ...prev, mental_age: mentalAge }));
        setChinesePprConfig(prev => ({ ...prev, mental_age: mentalAge }));
      }
    }
  }, [profile?.mental_age]);
  
  // Initialize mental_age from profile when available (old - keep for backward compatibility)
  useEffect(() => {
    if (profile && profile.mental_age && pprConfig.mental_age === null) {
      setPprConfig(prev => ({ ...prev, mental_age: parseFloat(profile.mental_age) }));
    }
  }, [profile]);

  const parseMasteredEnglishWords = (text) => {
    if (!text) return [];
    return text
      .split(',')
      .map(w => w.trim())
      .filter(Boolean);
  };

  if (!profile) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', color: theme.ui.text.secondary }}>
        <p>{t('pleaseSelectProfile') || "Please select a child profile to view language content."}</p>
      </div>
    );
  }

  // Content types available per language
  const getContentTypes = (lang) => {
    if (lang === 'zh') {
      return [
        { id: 'character', label: t('character'), icon: t('character') },
        { id: 'word', label: t('word'), icon: t('word') },
        { id: 'grammar', label: t('grammar'), icon: t('grammar') },
        { id: 'pragmatics', label: t('pragmatics'), icon: t('pragmatics') }
      ];
    } else { // English
      return [
        { id: 'word', label: t('word'), icon: t('word') },
        { id: 'grammar', label: t('grammar'), icon: t('grammar') },
        { id: 'pragmatics', label: t('pragmatics'), icon: t('pragmatics') }
      ];
    }
  };

  // Handle actions based on language and content type
  const handleManageMastered = () => {
    if (selectedLanguage === 'zh') {
      if (selectedContentType === 'word') {
        setShowMasteredWordsManager(true);
      } else if (selectedContentType === 'grammar') {
        setShowMasteredGrammarManager(true);
      } else if (selectedContentType === 'character') {
        // Character management (Chinese only) - can reuse word manager or create new one
        setShowMasteredWordsManager(true);
      } else {
        // Pragmatics - placeholder
        alert('Pragmatics management coming soon');
      }
    } else { // English
      if (selectedContentType === 'word') {
        setShowMasteredEnglishWordsManager(true);
      } else if (selectedContentType === 'grammar') {
        setShowMasteredGrammarManager(true);
      } else {
        // Pragmatics - placeholder
        alert('Pragmatics management coming soon');
      }
    }
  };

  const handleGetRecommendations = () => {
    if (selectedLanguage === 'zh') {
      if (selectedContentType === 'word') {
        handleGetChineseWordRecommendations();
      } else if (selectedContentType === 'grammar') {
        handleGetGrammarRecommendations('zh');
      } else {
        alert(`${selectedContentType} recommendations coming soon`);
      }
    } else { // English
      if (selectedContentType === 'word') {
        handleGetEnglishWordRecommendations();
      } else if (selectedContentType === 'grammar') {
        handleGetGrammarRecommendations('en');
      } else {
        alert(`${selectedContentType} recommendations coming soon`);
      }
    }
  };

  // --- Chinese Word Recommendations ---

  const handleGetChineseWordRecommendations = async (weight = null, algorithmType = null) => {
    setLoadingRecommendations(true);
    setSelectedRecommendations(new Set());
    
    const weightToUse = weight !== null ? weight : concretenessWeight;
    // Use provided algorithm type or current state
    const usePPR = algorithmType !== null ? algorithmType : useChinesePPRAlgorithm;
    
    try {
      const mastered_words_array = profile.mastered_words 
        ? profile.mastered_words.split(/[,\s，]+/).filter(w => w.trim())
        : [];
      
      let response;
      if (usePPR) {
        // Use Chinese PPR algorithm with configurable parameters
        const mentalAge = profile.mental_age ? parseFloat(profile.mental_age) : null;
        const requestConfig = {
          profile_id: profile.id || profile.name,
          mastered_words: mastered_words_array.length > 0 ? mastered_words_array : undefined,
          mental_age: chinesePprConfig.mental_age !== null ? chinesePprConfig.mental_age : (mentalAge || 8.0),
          beta_ppr: chinesePprConfig.beta_ppr,
          beta_concreteness: chinesePprConfig.beta_concreteness,
          beta_frequency: chinesePprConfig.beta_frequency,
          beta_aoa_penalty: chinesePprConfig.beta_aoa_penalty,
          beta_intercept: chinesePprConfig.beta_intercept,
          alpha: chinesePprConfig.alpha,
          aoa_buffer: chinesePprConfig.aoa_buffer,
          top_n: chinesePprConfig.top_n,
          exclude_multiword: chinesePprConfig.exclude_multiword
        };
        
        response = await axios.post(`${API_BASE}/kg/chinese-ppr-recommendations?t=${Date.now()}`, requestConfig, {
          headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' }
        });
      } else {
        // Use old algorithm
        response = await axios.post(`${API_BASE}/kg/recommendations`, {
        mastered_words: mastered_words_array,
        profile_id: profile.id || profile.name,
        concreteness_weight: weightToUse
      });
      }
      
      setRecommendations(response.data.recommendations || []);
      setShowRecommendations(true);
    } catch (error) {
      console.error('Error getting Chinese recommendations:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to get recommendations.';
      alert(`${t('failedToGetRecommendations')}: ${errorMsg}`);
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

  // --- English Word Recommendations ---

  const handleGetEnglishWordRecommendations = async (sliderPos = null, algorithmType = null) => {
    if (englishRecommendationsAbortController.current) {
      englishRecommendationsAbortController.current.abort();
    }
    
    const abortController = new AbortController();
    englishRecommendationsAbortController.current = abortController;
    const currentRequestId = ++englishRecommendationsRequestId.current;
    
    setLoadingEnglishRecommendations(true);
    setSelectedEnglishRecommendations(new Set());
    
    const sliderValue = sliderPos !== null ? sliderPos : englishSliderPosition;
    // Use provided algorithm type or current state
    const usePPR = algorithmType !== null ? algorithmType : usePPRAlgorithm;
    
    try {
      const mastered_words_array = parseMasteredEnglishWords(profile.mastered_english_words);
      const mentalAge = profile.mental_age ? parseFloat(profile.mental_age) : null;
      
      let response;
      if (usePPR) {
        // Use PPR algorithm with configurable parameters
        const requestConfig = {
          profile_id: profile.id || profile.name,
          mastered_words: mastered_words_array.length > 0 ? mastered_words_array : undefined,
          mental_age: pprConfig.mental_age !== null ? pprConfig.mental_age : (mentalAge || 8.0),
          beta_ppr: pprConfig.beta_ppr,
          beta_concreteness: pprConfig.beta_concreteness,
          beta_frequency: pprConfig.beta_frequency,
          beta_aoa_penalty: pprConfig.beta_aoa_penalty,
          beta_intercept: pprConfig.beta_intercept,
          alpha: pprConfig.alpha,
          aoa_buffer: pprConfig.aoa_buffer,
          top_n: pprConfig.top_n,
          exclude_multiword: pprConfig.exclude_multiword
        };
        
        response = await axios.post(`${API_BASE}/kg/ppr-recommendations?t=${Date.now()}`, requestConfig, {
          headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' },
          signal: abortController.signal
        });
      } else {
        // Use old algorithm
        response = await axios.post(`${API_BASE}/kg/english-recommendations?t=${Date.now()}`, {
        mastered_words: mastered_words_array,
        profile_id: profile.id || profile.name,
        concreteness_weight: sliderValue,
        mental_age: mentalAge
      }, {
        headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' },
        signal: abortController.signal
      });
      }
      
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
      const errorMessage = error.response?.data?.detail || error.message || 'Unknown error';
      alert(`Failed to get English recommendations: ${errorMessage}`);
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
        await onProfileUpdate();
      }
      
      const addedCount = selectedEnglishRecommendations.size;
      setSelectedEnglishRecommendations(new Set());
      alert(`✅ Successfully added ${addedCount} word(s) to mastered English words list!`);
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

  // --- Integrated Recommendations (PPR + ZPD + Campaign Manager) ---

  const handleGetIntegratedRecommendations = async () => {
    setLoadingIntegratedRecommendations(true);
    setSelectedIntegratedRecommendations(new Set());
    
    try {
      const response = await axios.post(`${API_BASE}/recommendations/integrated`, {
        profile_id: profile.id || profile.name,
        language: selectedLanguage
      });
      
      setIntegratedRecommendations(response.data.recommendations || []);
      setAllocationInfo(response.data.allocation || null);
      setShowIntegratedRecommendations(true);
    } catch (error) {
      console.error('Error getting integrated recommendations:', error);
      alert(`Failed to get integrated recommendations: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoadingIntegratedRecommendations(false);
    }
  };

  const handleToggleIntegratedRecommendation = (nodeId) => {
    setSelectedIntegratedRecommendations(prev => {
      const newSet = new Set(prev);
      if (newSet.has(nodeId)) {
        newSet.delete(nodeId);
      } else {
        newSet.add(nodeId);
      }
      return newSet;
    });
  };

  const handleAddSelectedIntegratedToMastered = async () => {
    if (selectedIntegratedRecommendations.size === 0) return;

    const selectedRecs = integratedRecommendations.filter(rec => 
      selectedIntegratedRecommendations.has(rec.node_id)
    );
    
    const vocabRecs = selectedRecs.filter(rec => rec.content_type === 'vocab');
    const grammarRecs = selectedRecs.filter(rec => rec.content_type === 'grammar');

    try {
      // Add vocabulary words
      if (vocabRecs.length > 0) {
        const currentMastered = selectedLanguage === 'zh'
          ? (profile.mastered_words ? profile.mastered_words.split(/[,\s，]+/).filter(w => w.trim()) : [])
          : (profile.mastered_english_words ? profile.mastered_english_words.split(/[,\s，]+/).filter(w => w.trim()) : []);
        
        const newWords = vocabRecs.map(rec => rec.label);
        const newMastered = [...new Set([...currentMastered, ...newWords])];
        
        const updatedProfile = {
          ...profile,
          [selectedLanguage === 'zh' ? 'mastered_words' : 'mastered_english_words']: newMastered.join(', ')
        };
        
        await axios.put(`${API_BASE}/profiles/${profile.name}`, updatedProfile);
      }

      // Add grammar points
      if (grammarRecs.length > 0) {
        const currentMastered = profile.mastered_grammar 
          ? profile.mastered_grammar.split(',').map(g => g.trim()).filter(g => g)
          : [];
        
        const newGrammar = grammarRecs.map(rec => rec.node_id);
        const newMastered = [...new Set([...currentMastered, ...newGrammar])];
        
        const updatedProfile = {
          ...profile,
          mastered_grammar: newMastered.join(',')
        };
        
        await axios.put(`${API_BASE}/profiles/${profile.name}`, updatedProfile);
      }

      if (onProfileUpdate) onProfileUpdate();
      
      const addedCount = selectedIntegratedRecommendations.size;
      setSelectedIntegratedRecommendations(new Set());
      alert(`✅ Successfully added ${addedCount} item(s) to mastered list! (${vocabRecs.length} vocab, ${grammarRecs.length} grammar)`);
    } catch (error) {
      console.error('Error adding integrated recommendations to mastered list:', error);
      alert('Failed to add items to mastered list.');
    }
  };

  const contentTypes = getContentTypes(selectedLanguage);
  const isCharacterAvailable = selectedLanguage === 'zh' && selectedContentType === 'character';
  const isLoading = (selectedContentType === 'word' && selectedLanguage === 'zh' && loadingRecommendations) ||
                    (selectedContentType === 'word' && selectedLanguage === 'en' && loadingEnglishRecommendations) ||
                    (selectedContentType === 'grammar' && loadingGrammarRecommendations);

  return (
    <div style={{ padding: theme.spacing.lg }}>
      {/* Level 1: Language Selection */}
      <div style={{ marginBottom: theme.spacing.lg }}>
        <h3 style={{ marginBottom: theme.spacing.md, color: theme.ui.text.primary }}>
          {t('selectLanguage')}
        </h3>
        <div style={{ display: 'flex', gap: theme.spacing.sm }}>
        <button 
            onClick={() => {
              setSelectedLanguage('zh');
              // Reset content type if switching to English and character was selected
              if (selectedContentType === 'character') {
                setSelectedContentType('word');
              }
            }}
            style={{
              padding: `${theme.spacing.sm} ${theme.spacing.md}`,
              border: `2px solid ${selectedLanguage === 'zh' ? theme.categories.language.primary : theme.ui.border}`,
              backgroundColor: selectedLanguage === 'zh' ? theme.categories.language.background : theme.ui.background,
              color: selectedLanguage === 'zh' ? theme.categories.language.primary : theme.ui.text.primary,
              borderRadius: theme.borderRadius.md,
              cursor: 'pointer',
              fontSize: '16px',
              fontWeight: selectedLanguage === 'zh' ? '600' : '400',
              transition: 'all 0.2s'
            }}
          >
            {t('chinese')}
        </button>
        <button 
            onClick={() => {
              setSelectedLanguage('en');
              // Reset content type if character was selected (English doesn't have characters)
              if (selectedContentType === 'character') {
                setSelectedContentType('word');
              }
            }}
            style={{
              padding: `${theme.spacing.sm} ${theme.spacing.md}`,
              border: `2px solid ${selectedLanguage === 'en' ? theme.categories.language.primary : theme.ui.border}`,
              backgroundColor: selectedLanguage === 'en' ? theme.categories.language.background : theme.ui.background,
              color: selectedLanguage === 'en' ? theme.categories.language.primary : theme.ui.text.primary,
              borderRadius: theme.borderRadius.md,
              cursor: 'pointer',
              fontSize: '16px',
              fontWeight: selectedLanguage === 'en' ? '600' : '400',
              transition: 'all 0.2s'
            }}
          >
            {t('english')}
        </button>
        </div>
      </div>

      {/* Level 2: Content Type Selection */}
      <div style={{ marginBottom: theme.spacing.lg }}>
        <h3 style={{ marginBottom: theme.spacing.md, color: theme.ui.text.primary }}>
          {t('selectContentType')}
        </h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: theme.spacing.sm }}>
          {contentTypes.map(type => (
        <button 
              key={type.id}
              onClick={() => setSelectedContentType(type.id)}
              style={{
                padding: `${theme.spacing.sm} ${theme.spacing.md}`,
                border: `2px solid ${selectedContentType === type.id ? theme.categories.language.primary : theme.ui.border}`,
                backgroundColor: selectedContentType === type.id ? theme.categories.language.background : theme.ui.background,
                color: selectedContentType === type.id ? theme.categories.language.primary : theme.ui.text.primary,
                borderRadius: theme.borderRadius.md,
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: selectedContentType === type.id ? '600' : '400',
                transition: 'all 0.2s'
              }}
            >
              {type.label}
        </button>
          ))}
        </div>
      </div>
      
      {/* Level 3: Actions */}
      <div style={{ 
        padding: theme.spacing.lg, 
        backgroundColor: theme.ui.backgrounds.surface, 
        borderRadius: theme.borderRadius.lg,
        border: `1px solid ${theme.ui.border}`
      }}>
        <h3 style={{ marginBottom: theme.spacing.md, color: theme.ui.text.primary }}>
          {selectedLanguage === 'zh' ? t('chinese') : t('english')} - {contentTypes.find(t => t.id === selectedContentType)?.label}
        </h3>
        
        {/* Actions - Show buttons for all content types */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: theme.spacing.md }}>
          {selectedContentType === 'character' && selectedLanguage === 'zh' ? (
        <button 
              onClick={() => setShowCharacterRecognition(true)}
          className="btn"
              style={{
                backgroundColor: theme.actions.secondary,
                color: theme.ui.text.inverse,
                padding: `${theme.spacing.sm} ${theme.spacing.md}`,
                borderRadius: theme.borderRadius.md,
                border: 'none',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '500'
              }}
            >
              📝 {t('manageCharacterRecognition')}
        </button>
          ) : (
            <>
        <button 
                onClick={handleManageMastered}
          className="btn"
                style={{
                  backgroundColor: theme.actions.secondary,
                  color: theme.ui.text.inverse,
                  padding: `${theme.spacing.sm} ${theme.spacing.md}`,
                  borderRadius: theme.borderRadius.md,
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: '500'
                }}
              >
                📝 {t('manageMastered') || 'Manage Mastered'}
        </button>
        <button 
                onClick={handleGetRecommendations}
          className="btn"
                disabled={isLoading}
                style={{
                  backgroundColor: isLoading ? theme.ui.backgrounds.disabled : theme.actions.primary,
                  color: theme.ui.text.inverse,
                  padding: `${theme.spacing.sm} ${theme.spacing.md}`,
                  borderRadius: theme.borderRadius.md,
                  border: 'none',
                  cursor: isLoading ? 'not-allowed' : 'pointer',
                  fontSize: '14px',
                  fontWeight: '500',
                  opacity: isLoading ? 0.6 : 1
                }}
              >
                {isLoading ? t('loading') : `📚 ${t('getRecommendations')}`}
        </button>
        {(selectedContentType === 'word' || selectedContentType === 'grammar') && (
        <button 
                onClick={handleGetIntegratedRecommendations}
          className="btn"
                disabled={loadingIntegratedRecommendations}
                style={{
                  backgroundColor: loadingIntegratedRecommendations ? theme.ui.backgrounds.disabled : '#9C27B0',
                  color: theme.ui.text.inverse,
                  padding: `${theme.spacing.sm} ${theme.spacing.md}`,
                  borderRadius: theme.borderRadius.md,
                  border: 'none',
                  cursor: loadingIntegratedRecommendations ? 'not-allowed' : 'pointer',
                  fontSize: '14px',
                  fontWeight: '500',
                  opacity: loadingIntegratedRecommendations ? 0.6 : 1
                }}
              >
                {loadingIntegratedRecommendations ? t('loading') : '🎯 Integrated Recommendations'}
        </button>
        )}
            </>
          )}
        </div>
      </div>

      {/* Modals - Keep existing modal code but adapt for hierarchy */}
      {/* Chinese Word Recommendations Modal */}
      {showRecommendations && selectedContentType === 'word' && selectedLanguage === 'zh' && (
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
            <h2>📚 {t('chineseWordRecommendations')}</h2>
            
            {/* PPR Algorithm Toggle */}
            <div style={{ marginBottom: '15px', padding: '12px', backgroundColor: '#e8f4f8', borderRadius: '8px', border: '1px solid #b3d9e6' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={useChinesePPRAlgorithm}
                  onChange={(e) => {
                    setUseChinesePPRAlgorithm(e.target.checked);
                    handleGetChineseWordRecommendations(null, e.target.checked);
                  }}
                  style={{ cursor: 'pointer' }}
                />
                <span style={{ fontWeight: 'bold', fontSize: '14px' }}>
                  🧠 使用智能推荐
                </span>
              </label>
              <div style={{ fontSize: '12px', color: '#666', marginTop: '5px', marginLeft: '24px' }}>
                {useChinesePPRAlgorithm 
                  ? t('smartRecommendationDesc')
                  : t('learningFrontierDesc')}
              </div>
            </div>
            
            {/* PPR Configuration Panel (when PPR is enabled) */}
            {useChinesePPRAlgorithm && (
              <div style={{ marginBottom: '15px', padding: '12px', backgroundColor: '#f9f9f9', borderRadius: '8px', border: '1px solid #ddd' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 'bold', fontSize: '13px' }}>{t('smartRecommendationConfig')}</span>
                  <button
                    onClick={() => setShowChinesePprConfig(!showChinesePprConfig)}
                    style={{
                      padding: '2px 8px',
                      fontSize: '11px',
                      backgroundColor: '#e0e0e0',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    {showChinesePprConfig ? t('collapse') : t('expand')}
                  </button>
                </div>
                {showChinesePprConfig && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '12px' }}>
                    <div>
                      <label>{t('semanticWeight')}: <input type="number" step="0.1" value={chinesePprConfig.beta_ppr} onChange={(e) => setChinesePprConfig({...chinesePprConfig, beta_ppr: parseFloat(e.target.value)})} style={{ width: '60px', marginLeft: '5px' }} /></label>
                    </div>
                    <div>
                      <label>{t('concreteness')}: <input type="number" step="0.1" value={chinesePprConfig.beta_concreteness} onChange={(e) => setChinesePprConfig({...chinesePprConfig, beta_concreteness: parseFloat(e.target.value)})} style={{ width: '60px', marginLeft: '5px' }} /></label>
                    </div>
                    <div>
                      <label>{t('frequency')}: <input type="number" step="0.1" value={chinesePprConfig.beta_frequency} onChange={(e) => setChinesePprConfig({...chinesePprConfig, beta_frequency: parseFloat(e.target.value)})} style={{ width: '60px', marginLeft: '5px' }} /></label>
                    </div>
                    <div>
                      <label>{t('acquisitionAge')}: <input type="number" step="0.1" value={chinesePprConfig.beta_aoa_penalty} onChange={(e) => setChinesePprConfig({...chinesePprConfig, beta_aoa_penalty: parseFloat(e.target.value)})} style={{ width: '60px', marginLeft: '5px' }} /></label>
                    </div>
                    <div>
                      <label>{t('baseScore')}: <input type="number" step="0.1" value={chinesePprConfig.beta_intercept} onChange={(e) => setChinesePprConfig({...chinesePprConfig, beta_intercept: parseFloat(e.target.value)})} style={{ width: '60px', marginLeft: '5px' }} /></label>
                    </div>
                    <div>
                      <label>{t('diversity')}: <input type="number" step="0.1" min="0" max="1" value={chinesePprConfig.alpha} onChange={(e) => setChinesePprConfig({...chinesePprConfig, alpha: parseFloat(e.target.value)})} style={{ width: '60px', marginLeft: '5px' }} /></label>
                    </div>
                    <div>
                      <label>{t('mentalAge')}: <input type="number" step="0.5" value={chinesePprConfig.mental_age || ''} onChange={(e) => setChinesePprConfig({...chinesePprConfig, mental_age: e.target.value ? parseFloat(e.target.value) : null})} style={{ width: '60px', marginLeft: '5px' }} /></label>
                    </div>
                    <div>
                      <label>{t('ageBuffer')}: <input type="number" step="0.5" value={chinesePprConfig.aoa_buffer} onChange={(e) => setChinesePprConfig({...chinesePprConfig, aoa_buffer: parseFloat(e.target.value)})} style={{ width: '60px', marginLeft: '5px' }} /></label>
                    </div>
                    <div>
                      <label>{t('numberOfRecommendations')}: <input type="number" step="5" min="10" max="200" value={chinesePprConfig.top_n} onChange={(e) => setChinesePprConfig({...chinesePprConfig, top_n: parseInt(e.target.value)})} style={{ width: '60px', marginLeft: '5px' }} /></label>
                    </div>
                    <div>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <input type="checkbox" checked={chinesePprConfig.exclude_multiword} onChange={(e) => setChinesePprConfig({...chinesePprConfig, exclude_multiword: e.target.checked})} />
                        排除多词短语
                      </label>
                    </div>
                  </div>
                )}
              </div>
            )}
            
            {/* Concreteness Weight Control (only show when PPR is disabled) */}
            {!useChinesePPRAlgorithm && (
            <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: '#f5f5f5', borderRadius: '8px', border: '1px solid #ddd' }}>
              <label style={{ display: 'block', marginBottom: '10px', fontWeight: 'bold', fontSize: '14px' }}>
                  ⚖️ 推荐平衡：
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                  <span style={{ fontSize: '12px', color: '#666', minWidth: '100px' }}>{t('onlyHSKLevel')}</span>
                <input
                  type="range" min="0" max="1" step="0.1" value={concretenessWeight}
                  onChange={(e) => {
                    const newWeight = parseFloat(e.target.value);
                    setConcretenessWeight(newWeight);
                      handleGetChineseWordRecommendations(newWeight, false);
                  }}
                  style={{ flex: 1, cursor: 'pointer' }}
                />
                  <span style={{ fontSize: '12px', color: '#666', minWidth: '100px', textAlign: 'right' }}>{t('onlyConcreteness')}</span>
              </div>
            </div>
            )}
            
            {recommendations.length === 0 ? (
              <p>{t('noRecommendations')}. {t('pleaseAddMasteredWords')}</p>
            ) : (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <p style={{ color: '#666', margin: 0 }}>{t('nextWordsToLearnCount').replace('{count}', useChinesePPRAlgorithm ? chinesePprConfig.top_n : 50)}：</p>
                    <button
                      onClick={() => handleGetChineseWordRecommendations()}
                      disabled={loadingRecommendations}
                      className="btn"
                      style={{
                        padding: '4px 12px',
                        fontSize: '12px',
                        backgroundColor: loadingRecommendations ? '#ccc' : '#2196F3',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: loadingRecommendations ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '5px'
                      }}
                      title="使用当前配置刷新推荐"
                    >
                      {loadingRecommendations ? '⏳' : '🔄'} {loadingRecommendations ? '加载中...' : '刷新'}
                    </button>
                  </div>
                  {selectedRecommendations.size > 0 && (
                    <button
                      onClick={handleAddSelectedToMastered}
                      disabled={savingMasteredWords}
                      className="btn"
                      style={{ backgroundColor: theme.actions.success, color: 'white' }}
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
                              {isAlreadyMastered && <span style={{ fontSize: '12px', color: theme.status.alreadyMastered, marginLeft: '8px' }}>({t('alreadyMastered')})</span>}
                            </div>
                            <div style={{ fontSize: '0.8em', color: '#888' }}>
                              {useChinesePPRAlgorithm ? (
                                <>
                                  P(推荐): {(rec.score * 100).toFixed(1)}% |
                                  {rec.log_ppr !== undefined && ` log(PPR): ${rec.log_ppr.toFixed(2)} |`}
                                  {rec.z_concreteness !== undefined && ` Z(具体): ${rec.z_concreteness.toFixed(2)} |`}
                                  {rec.log_frequency !== undefined && ` log(${t('frequency')}): ${rec.log_frequency.toFixed(2)} |`}
                                  {rec.aoa_penalty !== undefined && rec.aoa_penalty > 0 && ` AoA惩罚: ${rec.aoa_penalty.toFixed(1)} |`}
                                  {rec.hsk_level && ` HSK: ${rec.hsk_level}`}
                                </>
                              ) : (
                                <>
                              HSK: {rec.hsk} | Score: {typeof rec.score === 'number' ? rec.score.toFixed(1) : rec.score}
                                </>
                              )}
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

      {/* English Word Recommendations Modal */}
      {showEnglishRecommendations && selectedContentType === 'word' && selectedLanguage === 'en' && (
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
            <h2>📚 {t('englishWordRecommendations')}</h2>
            
            <div style={{ marginBottom: '15px', padding: '12px', backgroundColor: '#e8f4f8', borderRadius: '8px', border: '1px solid #b3d9e6' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={usePPRAlgorithm}
                  onChange={(e) => {
                    const newValue = e.target.checked;
                    setUsePPRAlgorithm(newValue);
                    // Refetch recommendations with new algorithm
                    // Pass the new value directly to avoid state timing issues
                    setTimeout(() => {
                      handleGetEnglishWordRecommendations(englishSliderPosition, newValue);
                    }, 100);
                  }}
                  style={{ cursor: 'pointer' }}
                />
                <span style={{ fontWeight: 'bold', fontSize: '14px' }}>
                  🧠 使用智能推荐
                </span>
              </label>
              <div style={{ fontSize: '12px', color: '#666', marginTop: '5px', marginLeft: '24px' }}>
                {usePPRAlgorithm 
                  ? t('smartRecommendationDesc')
                  : t('learningFrontierDescEnglish')}
              </div>
              {usePPRAlgorithm && (
                <div style={{ marginTop: '10px', marginLeft: '24px' }}>
                  <button
                    type="button"
                    onClick={() => setShowPprConfig(!showPprConfig)}
                    style={{
                      fontSize: '12px',
                      padding: '4px 8px',
                      backgroundColor: showPprConfig ? '#4CAF50' : '#2196F3',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer'
                    }}
                  >
                    {showPprConfig ? `▼ ${t('hideConfig')}` : `▶ ${t('showConfig')}`}
                  </button>
                </div>
              )}
            </div>
            
            {usePPRAlgorithm && showPprConfig && (
              <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: '#f0f8ff', borderRadius: '8px', border: '1px solid #b3d9e6' }}>
                <h4 style={{ marginTop: 0, marginBottom: '15px', fontSize: '14px', fontWeight: 'bold' }}>
                  ⚙️ {t('smartRecommendationConfig')}
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', fontWeight: 'bold' }}>
                      语义权重: {pprConfig.beta_ppr.toFixed(2)}
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="3"
                      step="0.1"
                      value={pprConfig.beta_ppr}
                      onChange={(e) => {
                        const newValue = parseFloat(e.target.value);
                        setPprConfig(prev => ({ ...prev, beta_ppr: newValue }));
                        setTimeout(() => handleGetEnglishWordRecommendations(), 300);
                      }}
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', fontWeight: 'bold' }}>
                      具体性: {pprConfig.beta_concreteness.toFixed(2)}
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="3"
                      step="0.1"
                      value={pprConfig.beta_concreteness}
                      onChange={(e) => {
                        const newValue = parseFloat(e.target.value);
                        setPprConfig(prev => ({ ...prev, beta_concreteness: newValue }));
                        setTimeout(() => handleGetEnglishWordRecommendations(), 300);
                      }}
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', fontWeight: 'bold' }}>
                      频率: {pprConfig.beta_frequency.toFixed(2)}
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="3"
                      step="0.1"
                      value={pprConfig.beta_frequency}
                      onChange={(e) => {
                        const newValue = parseFloat(e.target.value);
                        setPprConfig(prev => ({ ...prev, beta_frequency: newValue }));
                        setTimeout(() => handleGetEnglishWordRecommendations(), 300);
                      }}
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', fontWeight: 'bold' }}>
                      习得年龄: {pprConfig.beta_aoa_penalty.toFixed(2)}
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="5"
                      step="0.1"
                      value={pprConfig.beta_aoa_penalty}
                      onChange={(e) => {
                        const newValue = parseFloat(e.target.value);
                        setPprConfig(prev => ({ ...prev, beta_aoa_penalty: newValue }));
                        setTimeout(() => handleGetEnglishWordRecommendations(), 300);
                      }}
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', fontWeight: 'bold' }}>
                      基础分: {pprConfig.beta_intercept.toFixed(2)}
                    </label>
                    <input
                      type="range"
                      min="-2"
                      max="2"
                      step="0.1"
                      value={pprConfig.beta_intercept}
                      onChange={(e) => {
                        const newValue = parseFloat(e.target.value);
                        setPprConfig(prev => ({ ...prev, beta_intercept: newValue }));
                        setTimeout(() => handleGetEnglishWordRecommendations(), 300);
                      }}
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', fontWeight: 'bold' }}>
                      多样性: {pprConfig.alpha.toFixed(2)}
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={pprConfig.alpha}
                      onChange={(e) => {
                        const newValue = parseFloat(e.target.value);
                        setPprConfig(prev => ({ ...prev, alpha: newValue }));
                        setTimeout(() => handleGetEnglishWordRecommendations(), 300);
                      }}
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', fontWeight: 'bold' }}>
                      {t('mentalAge')}: {pprConfig.mental_age !== null ? pprConfig.mental_age.toFixed(1) : (profile.mental_age || t('useProfileDefault'))}
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="18"
                      step="0.5"
                      value={pprConfig.mental_age !== null ? pprConfig.mental_age : ''}
                      onChange={(e) => {
                        const newValue = e.target.value === '' ? null : parseFloat(e.target.value);
                        setPprConfig(prev => ({ ...prev, mental_age: newValue }));
                        setTimeout(() => handleGetEnglishWordRecommendations(), 300);
                      }}
                      placeholder={profile.mental_age ? `${t('profileColon')} ${profile.mental_age}` : t('useProfileDefault')}
                      style={{ width: '100%', padding: '4px' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', fontWeight: 'bold' }}>
                      {t('ageBuffer')}: {pprConfig.aoa_buffer.toFixed(1)}
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="3"
                      step="0.1"
                      value={pprConfig.aoa_buffer}
                      onChange={(e) => {
                        const newValue = parseFloat(e.target.value);
                        setPprConfig(prev => ({ ...prev, aoa_buffer: newValue }));
                        setTimeout(() => handleGetEnglishWordRecommendations(), 300);
                      }}
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '5px', fontSize: '12px', fontWeight: 'bold' }}>
                      {t('topNResults')}: {pprConfig.top_n}
                    </label>
                    <input
                      type="number"
                      min="10"
                      max="200"
                      step="10"
                      value={pprConfig.top_n}
                      onChange={(e) => {
                        const newValue = parseInt(e.target.value);
                        setPprConfig(prev => ({ ...prev, top_n: newValue }));
                        setTimeout(() => handleGetEnglishWordRecommendations(), 300);
                      }}
                      style={{ width: '100%', padding: '4px' }}
                    />
                  </div>
                  <div style={{ gridColumn: '1 / -1' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={pprConfig.exclude_multiword}
                        onChange={(e) => {
                          setPprConfig(prev => ({ ...prev, exclude_multiword: e.target.checked }));
                          setTimeout(() => handleGetEnglishWordRecommendations(), 300);
                        }}
                      />
                      <span style={{ fontSize: '12px', fontWeight: 'bold' }}>
                        排除多词短语（例如："ice hockey"、"chewing gum"）
                      </span>
                    </label>
                  </div>
                </div>
              </div>
            )}
            
            {!usePPRAlgorithm && (
            <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: '#f5f5f5', borderRadius: '8px', border: '1px solid #ddd' }}>
              <label style={{ display: 'block', marginBottom: '10px', fontWeight: 'bold', fontSize: '14px' }}>
                ⚖️ {t('recommendationBalanceEnglish')}：
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                <span style={{ fontSize: '12px', color: '#666', minWidth: '120px' }}>{t('frequencyUtility')}</span>
                <input
                  type="range" min="0" max="1" step="0.1" value={englishSliderPosition}
                  onChange={(e) => {
                    const newPos = parseFloat(e.target.value);
                    setEnglishSliderPosition(newPos);
                    if (sliderDebounceTimer.current) clearTimeout(sliderDebounceTimer.current);
                    sliderDebounceTimer.current = setTimeout(() => {
                        handleGetEnglishWordRecommendations(newPos);
                    }, 300);
                  }}
                  style={{ flex: 1, cursor: 'pointer' }}
                />
                <span style={{ fontSize: '12px', color: '#666', minWidth: '120px', textAlign: 'right' }}>{t('concretenessEase')}</span>
              </div>
            </div>
            )}

            {englishRecommendations.length === 0 ? (
              <p>{t('noRecommendations')}. {t('pleaseAddMasteredEnglishWords')}</p>
            ) : (
              <div>
                 <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <p style={{ color: '#666', margin: 0 }}>
                      {t('nextWordsToLearnCount').replace('{count}', usePPRAlgorithm ? pprConfig.top_n : 50)}：
                    </p>
                    <button
                      onClick={() => handleGetEnglishWordRecommendations()}
                      disabled={loadingEnglishRecommendations}
                      className="btn"
                      style={{
                        padding: '4px 12px',
                        fontSize: '12px',
                        backgroundColor: loadingEnglishRecommendations ? '#ccc' : '#2196F3',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: loadingEnglishRecommendations ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '5px'
                      }}
                      title="使用当前配置刷新推荐"
                    >
                      {loadingEnglishRecommendations ? '⏳' : '🔄'} {loadingEnglishRecommendations ? '加载中...' : '刷新'}
                    </button>
                  </div>
                  {selectedEnglishRecommendations.size > 0 && (
                    <button
                      onClick={handleAddSelectedEnglishToMastered}
                      disabled={savingMasteredEnglishWords}
                      className="btn"
                      style={{ backgroundColor: theme.actions.success, color: 'white' }}
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
                              {isAlreadyMastered && <span style={{ fontSize: '12px', color: theme.status.alreadyMastered, marginLeft: '8px' }}>({t('alreadyMastered')})</span>}
                            </div>
                            <div style={{ fontSize: '0.8em', color: '#888' }}>
                              {usePPRAlgorithm ? (
                                <>
                                  P(Recommend): {(rec.score * 100).toFixed(1)}% | 
                                  Concreteness: {rec.concreteness?.toFixed(1) || '-'} | 
                                  AoA: {rec.age_of_acquisition?.toFixed(1) || '-'}
                                </>
                              ) : (
                                <>
                              CEFR: {rec.cefr_level || '-'} | Score: {rec.score?.toFixed(2)}
                                </>
                              )}
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

      {/* Integrated Recommendations Modal */}
      {showIntegratedRecommendations && (
        <div className="modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'white', padding: '30px', borderRadius: '8px',
            maxWidth: '800px', maxHeight: '80vh', overflow: 'auto', position: 'relative'
          }}>
            <button onClick={() => setShowIntegratedRecommendations(false)} style={{
              position: 'absolute', top: '10px', right: '10px', border: 'none', background: 'none', fontSize: '24px', cursor: 'pointer'
            }}>×</button>
            <h2>🎯 Integrated Recommendations ({selectedLanguage === 'en' ? t('english') : t('chinese')})</h2>
            
            {allocationInfo && (
              <div style={{ 
                backgroundColor: '#f0f0f0', 
                padding: '15px', 
                borderRadius: '8px', 
                marginBottom: '20px',
                fontSize: '14px'
              }}>
                <strong>📊 Allocation:</strong> {allocationInfo.daily_capacity} total slots
                <br />
                <span style={{ color: '#2196F3' }}>📚 Vocabulary: {allocationInfo.vocab_slots} slots ({Math.round(allocationInfo.vocab_ratio * 100)}%)</span>
                <br />
                <span style={{ color: '#9C27B0' }}>📖 Grammar: {allocationInfo.grammar_slots} slots ({Math.round(allocationInfo.grammar_ratio * 100)}%)</span>
              </div>
            )}

            {integratedRecommendations.length === 0 ? (
              <p>No integrated recommendations available.</p>
            ) : (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <p style={{ color: '#666', margin: 0 }}>
                      {integratedRecommendations.length} recommendations (PPR + ZPD filtered)
                    </p>
                    <button
                      onClick={handleGetIntegratedRecommendations}
                      disabled={loadingIntegratedRecommendations}
                      className="btn"
                      style={{
                        padding: '4px 12px',
                        fontSize: '12px',
                        backgroundColor: loadingIntegratedRecommendations ? '#ccc' : '#9C27B0',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: loadingIntegratedRecommendations ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '5px'
                      }}
                    >
                      {loadingIntegratedRecommendations ? '⏳' : '🔄'} {loadingIntegratedRecommendations ? 'Loading...' : 'Refresh'}
                    </button>
                  </div>
                  {selectedIntegratedRecommendations.size > 0 && (
                    <button
                      onClick={handleAddSelectedIntegratedToMastered}
                      className="btn"
                      style={{ backgroundColor: theme.actions.success, color: 'white' }}
                    >
                      ✓ Add Selected ({selectedIntegratedRecommendations.size})
                    </button>
                  )}
                </div>
                
                {/* Group by content type */}
                {['vocab', 'grammar'].map(contentType => {
                  const recs = integratedRecommendations.filter(rec => rec.content_type === contentType);
                  if (recs.length === 0) return null;
                  
                  return (
                    <div key={contentType} style={{ marginBottom: '30px' }}>
                      <h3 style={{ 
                        color: contentType === 'vocab' ? '#2196F3' : '#9C27B0',
                        borderBottom: `2px solid ${contentType === 'vocab' ? '#2196F3' : '#9C27B0'}`,
                        paddingBottom: '5px',
                        marginBottom: '15px'
                      }}>
                        {contentType === 'vocab' ? '📚 Vocabulary' : '📖 Grammar'} ({recs.length})
                      </h3>
                      <ol style={{ paddingLeft: '20px' }}>
                        {recs.map((rec, idx) => {
                          const isSelected = selectedIntegratedRecommendations.has(rec.node_id);
                          
                          return (
                            <li key={`${rec.node_id}-${idx}`} style={{ marginBottom: '15px' }}>
                              <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={() => handleToggleIntegratedRecommendation(rec.node_id)}
                                  style={{ marginRight: '10px' }}
                                />
                                <div style={{ flex: 1 }}>
                                  <div style={{ fontWeight: 'bold' }}>
                                    {rec.label}
                                  </div>
                                  <div style={{ fontSize: '0.8em', color: '#888', marginTop: '5px' }}>
                                    Score: {rec.score?.toFixed(3) || 'N/A'} | 
                                    Mastery: {(rec.mastery * 100).toFixed(1)}% |
                                    {rec.hsk_level && ` HSK ${rec.hsk_level}`}
                                    {rec.cefr_level && ` CEFR ${rec.cefr_level}`}
                                    {rec.prerequisites && rec.prerequisites.length > 0 && ` | Prereqs: ${rec.prerequisites.length}`}
                                  </div>
                                </div>
                              </label>
                            </li>
                          );
                        })}
                      </ol>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Grammar Recommendations Modal */}
      {showGrammarRecommendations && selectedContentType === 'grammar' && (
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
            <h2>📖 {t('grammarRecommendations')} ({selectedLanguage === 'en' ? t('english') : t('chinese')})</h2>

            {grammarRecommendations.length === 0 ? (
              <p>暂无语法推荐。</p>
            ) : (
              <div>
                 <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <p style={{ color: '#666', margin: 0 }}>{t('nextGrammarPoints')}：</p>
                    <button
                      onClick={() => handleGetGrammarRecommendations(selectedLanguage)}
                      disabled={loadingGrammarRecommendations}
                      className="btn"
                      style={{
                        padding: '4px 12px',
                        fontSize: '12px',
                        backgroundColor: loadingGrammarRecommendations ? '#ccc' : '#2196F3',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: loadingGrammarRecommendations ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '5px'
                      }}
                      title="使用当前配置刷新推荐"
                    >
                      {loadingGrammarRecommendations ? '⏳' : '🔄'} {loadingGrammarRecommendations ? '加载中...' : '刷新'}
                    </button>
                  </div>
                  {selectedGrammarRecommendations.size > 0 && (
                    <button
                      onClick={handleAddSelectedGrammarToMastered}
                      disabled={savingMasteredGrammar}
                      className="btn"
                      style={{ backgroundColor: theme.actions.success, color: 'white' }}
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
                              {selectedLanguage === 'en' ? rec.grammar_point : (rec.grammar_point_zh || rec.grammar_point)}
                              {isAlreadyMastered && <span style={{ fontSize: '12px', color: theme.status.alreadyMastered, marginLeft: '8px' }}>({t('alreadyMastered')})</span>}
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
      {showMasteredWordsManager && selectedContentType === 'word' && selectedLanguage === 'zh' && (
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

      {showMasteredEnglishWordsManager && selectedContentType === 'word' && selectedLanguage === 'en' && (
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

      {showMasteredGrammarManager && selectedContentType === 'grammar' && (
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
            <MasteredGrammarManager profile={profile} onUpdate={onProfileUpdate} grammarLanguage={selectedLanguage} />
          </div>
        </div>
      )}

      {/* Character Recognition Modal */}
      {showCharacterRecognition && selectedContentType === 'character' && selectedLanguage === 'zh' && (
        <div className="modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'white', padding: '20px', borderRadius: '8px', width: '90%', maxWidth: '1200px', maxHeight: '90vh', overflow: 'auto', position: 'relative'
          }}>
            <button onClick={() => setShowCharacterRecognition(false)} style={{
              position: 'absolute', top: '10px', right: '10px', border: 'none', background: 'none', fontSize: '24px', cursor: 'pointer', zIndex: 1001
            }}>×</button>
            <CharacterRecognition profile={profile} onProfileUpdate={onProfileUpdate} />
          </div>
        </div>
      )}

    </div>
  );
};

export default LanguageContentManager;
