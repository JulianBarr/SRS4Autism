import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { useLanguage } from '../i18n/LanguageContext';
import MasteredWordsManager from './MasteredWordsManager';
import MasteredEnglishWordsManager from './MasteredEnglishWordsManager';
import MasteredGrammarManager from './MasteredGrammarManager';
import CharacterRecognition from './CharacterRecognition';
import ChineseWordRecognition from './ChineseWordRecognition';
import EnglishWordRecognition from './EnglishWordRecognition';
import RecommendationSmartConfig from './RecommendationSmartConfig';
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
    exclude_multiword: true,
    max_hsk_level: 4 // Default max HSK level
  });
  
  // Calculate current HSK level from recommendations (fallback to 1)
  const [currentHSKLevel, setCurrentHSKLevel] = useState(1);
  
  // Mastered Managers State
  const [showMasteredWordsManager, setShowMasteredWordsManager] = useState(false);
  const [showMasteredEnglishWordsManager, setShowMasteredEnglishWordsManager] = useState(false);
  const [showMasteredGrammarManager, setShowMasteredGrammarManager] = useState(false);
  const [showCharacterRecognition, setShowCharacterRecognition] = useState(false);
  const [showChineseWordRecognition, setShowChineseWordRecognition] = useState(false);
  const [showEnglishWordRecognition, setShowEnglishWordRecognition] = useState(false);

  // Listen for custom event to open word recognition from Mario's World
  useEffect(() => {
    const handleOpenWordRecognition = (event) => {
      const language = event.detail?.language || 'zh';
      setSelectedLanguage(language);
      setSelectedContentType('word');
      if (language === 'zh') {
        setShowChineseWordRecognition(true);
      } else if (language === 'en') {
        setShowEnglishWordRecognition(true);
      }
    };
    
    window.addEventListener('openWordRecognition', handleOpenWordRecognition);
    return () => {
      window.removeEventListener('openWordRecognition', handleOpenWordRecognition);
    };
  }, []);
  
  // English Word Recommendations State
  const [showEnglishRecommendations, setShowEnglishRecommendations] = useState(false);
  const [englishRecommendations, setEnglishRecommendations] = useState([]);
  const [loadingEnglishRecommendations, setLoadingEnglishRecommendations] = useState(false);
  const [selectedEnglishRecommendations, setSelectedEnglishRecommendations] = useState(new Set());
  const [savingMasteredEnglishWords, setSavingMasteredEnglishWords] = useState(false);
  const [recommendationsKey, setRecommendationsKey] = useState(0);
  
  // PPR Algorithm Configuration State for English
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
    exclude_multiword: true
  });
  
  const englishRecommendationsAbortController = useRef(null);
  const englishRecommendationsRequestId = useRef(0);

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

  const handleGetChineseWordRecommendations = async (configOverride = null) => {
    setLoadingRecommendations(true);
    setSelectedRecommendations(new Set());
    
    const config = configOverride || chinesePprConfig;
    
    try {
      const mastered_words_array = profile.mastered_words 
        ? profile.mastered_words.split(/[,\s，]+/).filter(w => w.trim())
        : [];
      
      // Use Chinese PPR algorithm with configurable parameters
      const mentalAge = profile.mental_age ? parseFloat(profile.mental_age) : null;
      const requestConfig = {
        profile_id: profile.id || profile.name,
        mastered_words: mastered_words_array.length > 0 ? mastered_words_array : undefined,
        mental_age: config.mental_age !== null ? config.mental_age : (mentalAge || 8.0),
        beta_ppr: config.beta_ppr,
        beta_concreteness: config.beta_concreteness,
        beta_frequency: config.beta_frequency,
        beta_aoa_penalty: config.beta_aoa_penalty,
        beta_intercept: config.beta_intercept,
        alpha: config.alpha,
        aoa_buffer: config.aoa_buffer,
        top_n: config.top_n,
        exclude_multiword: config.exclude_multiword,
        max_hsk_level: config.max_hsk_level
      };
      
      const response = await axios.post(`${API_BASE}/kg/chinese-ppr-recommendations?t=${Date.now()}`, requestConfig, {
        headers: { 'Cache-Control': 'no-cache', 'Pragma': 'no-cache' }
      });
      
      const recs = response.data.recommendations || [];
      setRecommendations(recs);
      setShowRecommendations(true);
      
      // Try to infer current HSK level from recommendations (use the most common HSK level)
      if (recs.length > 0) {
        const hskLevels = recs.map(r => r.hsk || r.hsk_level).filter(Boolean);
        if (hskLevels.length > 0) {
          const mostCommonLevel = hskLevels.sort((a, b) => 
            hskLevels.filter(v => v === a).length - hskLevels.filter(v => v === b).length
          ).pop();
          setCurrentHSKLevel(mostCommonLevel);
        }
      }
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

  const handleGetEnglishWordRecommendations = async (configOverride = null) => {
    if (englishRecommendationsAbortController.current) {
      englishRecommendationsAbortController.current.abort();
    }
    
    const abortController = new AbortController();
    englishRecommendationsAbortController.current = abortController;
    const currentRequestId = ++englishRecommendationsRequestId.current;
    
    setLoadingEnglishRecommendations(true);
    setSelectedEnglishRecommendations(new Set());
    
    const config = configOverride || pprConfig;
    
    try {
      const mastered_words_array = parseMasteredEnglishWords(profile.mastered_english_words);
      const mentalAge = profile.mental_age ? parseFloat(profile.mental_age) : null;
      
      // Use PPR algorithm with configurable parameters
      const requestConfig = {
        profile_id: profile.id || profile.name,
        mastered_words: mastered_words_array.length > 0 ? mastered_words_array : undefined,
        mental_age: config.mental_age !== null ? config.mental_age : (mentalAge || 8.0),
        beta_ppr: config.beta_ppr,
        beta_concreteness: config.beta_concreteness,
        beta_frequency: config.beta_frequency,
        beta_aoa_penalty: config.beta_aoa_penalty,
        beta_intercept: config.beta_intercept,
        alpha: config.alpha,
        aoa_buffer: config.aoa_buffer,
        top_n: config.top_n,
        exclude_multiword: config.exclude_multiword,
        max_level: config.max_hsk_level
      };
      
      const response = await axios.post(`${API_BASE}/kg/ppr-recommendations?t=${Date.now()}`, requestConfig, {
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
        {selectedContentType === 'word' && selectedLanguage === 'zh' && (
        <button 
              onClick={() => setShowChineseWordRecognition(true)}
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
              📝 {t('manageWordRecognition')}
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
            backgroundColor: 'white', borderRadius: '8px',
            maxWidth: '700px', maxHeight: '85vh', display: 'flex', flexDirection: 'column', position: 'relative',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
          }}>
            <button onClick={() => setShowRecommendations(false)} style={{
              position: 'absolute', top: '15px', right: '15px', border: 'none', background: 'white', 
              fontSize: '28px', cursor: 'pointer', zIndex: 10, width: '40px', height: '40px',
              borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)', color: '#666'
            }}>×</button>
            
            <div style={{ padding: '30px 30px 10px 30px', borderBottom: '1px solid #eee' }}>
              <h2 style={{ margin: 0 }}>📚 {t('chineseWordRecommendations')}</h2>
            </div>

            <div style={{ padding: '20px 30px', overflowY: 'auto', flex: 1 }}>
              {/* PPR Configuration Panel */}
              <RecommendationSmartConfig
                language="zh"
                currentLevel={currentHSKLevel}
                initialConfig={{
                  beta_ppr: chinesePprConfig.beta_ppr,
                  beta_concreteness: chinesePprConfig.beta_concreteness,
                  beta_frequency: chinesePprConfig.beta_frequency,
                  beta_aoa_penalty: chinesePprConfig.beta_aoa_penalty,
                  alpha: chinesePprConfig.alpha,
                  max_hsk_level: chinesePprConfig.max_hsk_level || 4,
                  top_n: chinesePprConfig.top_n,
                  mental_age: chinesePprConfig.mental_age !== null ? chinesePprConfig.mental_age : (profile.mental_age || 8.0)
                }}
                onConfigChange={(newConfig) => {
                  setChinesePprConfig(prev => {
                    const updated = { ...prev, ...newConfig };
                    // If exclude_multiword or other key params changed, trigger refresh
                    if (prev.exclude_multiword !== updated.exclude_multiword || 
                        prev.beta_ppr !== updated.beta_ppr ||
                        prev.max_hsk_level !== updated.max_hsk_level) {
                      setTimeout(() => handleGetChineseWordRecommendations(updated), 50);
                    }
                    return updated;
                  });
                }}
              />
              
              {recommendations.length === 0 ? (
                <p>{t('noRecommendations')}. {t('pleaseAddMasteredWords')}</p>
              ) : (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px', position: 'sticky', top: 0, backgroundColor: 'white', zIndex: 5, padding: '10px 0' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <p style={{ color: '#666', margin: 0, fontWeight: '500' }}>{t('nextWordsToLearnCount').replace('{count}', recommendations.length)}：</p>
                      <button
                        onClick={() => handleGetChineseWordRecommendations()}
                        disabled={loadingRecommendations}
                        className="btn"
                        style={{
                          padding: '6px 16px',
                          fontSize: '13px',
                          backgroundColor: loadingRecommendations ? '#ccc' : theme.actions.primary,
                          color: 'white',
                          border: 'none',
                          borderRadius: '6px',
                          cursor: loadingRecommendations ? 'not-allowed' : 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '5px',
                          fontWeight: '600',
                          transition: 'all 0.2s'
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
                        style={{ 
                          backgroundColor: theme.actions.success, 
                          color: 'white',
                          padding: '6px 16px',
                          borderRadius: '6px',
                          fontWeight: '600'
                        }}
                      >
                        {savingMasteredWords ? `💾 ${t('saving')}` : `✓ ${t('addSelected')} (${selectedRecommendations.size})`}
                      </button>
                    )}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {recommendations.map((rec, idx) => {
                      const isSelected = selectedRecommendations.has(rec.word);
                      const isAlreadyMastered = profile.mastered_words?.split(/[,\s，]+/).map(w => w.trim()).includes(rec.word);
                      
                      return (
                        <div key={rec.word || idx} style={{ 
                          padding: '12px 16px',
                          borderRadius: '10px',
                          border: `1px solid ${isSelected ? theme.actions.primary : '#eee'}`,
                          backgroundColor: isSelected ? `${theme.actions.primary}08` : 'white',
                          transition: 'all 0.2s'
                        }}>
                          <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                            <input
                              type="checkbox" checked={isSelected} disabled={isAlreadyMastered}
                              onChange={() => handleToggleRecommendation(rec.word)}
                              style={{ width: '18px', height: '18px', marginRight: '15px', cursor: 'pointer' }}
                            />
                            <div style={{ flex: 1 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                                <span style={{ 
                                  fontSize: '14px', 
                                  fontWeight: '800', 
                                  color: theme.actions.primary,
                                  backgroundColor: `${theme.actions.primary}15`,
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  minWidth: '40px',
                                  textAlign: 'center'
                                }}>
                                  #{idx + 1}
                                </span>
                                <span style={{ fontSize: '20px', fontWeight: '800', color: '#1a1a1a' }}>
                                  {rec.word}
                                </span>
                                {rec.pinyin && (
                                  <span style={{ color: '#666', fontSize: '15px', fontWeight: '500' }}>
                                    ({rec.pinyin})
                                  </span>
                                )}
                                {isAlreadyMastered && (
                                  <span style={{ 
                                    fontSize: '11px', 
                                    fontWeight: '600',
                                    color: theme.status.alreadyMastered, 
                                    backgroundColor: `${theme.status.alreadyMastered}15`,
                                    padding: '2px 6px',
                                    borderRadius: '4px',
                                    textTransform: 'uppercase'
                                  }}>
                                    {t('alreadyMastered')}
                                  </span>
                                )}
                              </div>
                              <div style={{ fontSize: '12px', color: '#999', fontWeight: '400', display: 'flex', flexWrap: 'wrap', alignItems: 'center' }}>
                                <span>P(Recommend): <strong style={{ color: '#555' }}>{(rec.score * 100).toFixed(1)}%</strong></span>
                                <span style={{ margin: '0 8px', color: '#ddd' }}>|</span>
                                {rec.log_ppr !== undefined && (
                                  <>
                                    <span>log(PPR): <strong style={{ color: '#555' }}>{rec.log_ppr.toFixed(2)}</strong></span>
                                    <span style={{ margin: '0 8px', color: '#ddd' }}>|</span>
                                  </>
                                )}
                                {rec.z_concreteness !== undefined && (
                                  <>
                                    <span>Concreteness: <strong style={{ color: '#555' }}>{rec.z_concreteness.toFixed(2)}</strong></span>
                                    <span style={{ margin: '0 8px', color: '#ddd' }}>|</span>
                                  </>
                                )}
                                {rec.log_frequency !== undefined && (
                                  <>
                                    <span>Frequency: <strong style={{ color: '#555' }}>{rec.log_frequency.toFixed(2)}</strong></span>
                                    <span style={{ margin: '0 8px', color: '#ddd' }}>|</span>
                                  </>
                                )}
                                {rec.hsk_level && <span>HSK: <strong style={{ color: '#555' }}>{rec.hsk_level}</strong></span>}
                              </div>
                            </div>
                          </label>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
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
            backgroundColor: 'white', borderRadius: '8px',
            maxWidth: '700px', maxHeight: '85vh', display: 'flex', flexDirection: 'column', position: 'relative',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
          }}>
            <button onClick={() => setShowEnglishRecommendations(false)} style={{
              position: 'absolute', top: '15px', right: '15px', border: 'none', background: 'white', 
              fontSize: '28px', cursor: 'pointer', zIndex: 10, width: '40px', height: '40px',
              borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)', color: '#666'
            }}>×</button>

            <div style={{ padding: '30px 30px 10px 30px', borderBottom: '1px solid #eee' }}>
              <h2 style={{ margin: 0 }}>📚 {t('englishWordRecommendations')}</h2>
            </div>

            <div style={{ padding: '20px 30px', overflowY: 'auto', flex: 1 }}>
              {/* English PPR Configuration Grid */}
              <RecommendationSmartConfig
                language="en"
                currentLevel={1}
                initialConfig={{
                  beta_ppr: pprConfig.beta_ppr,
                  beta_concreteness: pprConfig.beta_concreteness,
                  beta_frequency: pprConfig.beta_frequency,
                  beta_aoa_penalty: pprConfig.beta_aoa_penalty,
                  alpha: pprConfig.alpha,
                  top_n: pprConfig.top_n,
                  mental_age: pprConfig.mental_age !== null ? pprConfig.mental_age : (profile.mental_age || 8.0)
                }}
                onConfigChange={(newConfig) => {
                  setPprConfig(prev => {
                    const updated = { ...prev, ...newConfig };
                    if (prev.exclude_multiword !== updated.exclude_multiword || 
                        prev.beta_ppr !== updated.beta_ppr ||
                        prev.max_hsk_level !== updated.max_hsk_level) {
                      setTimeout(() => handleGetEnglishWordRecommendations(updated), 50);
                    }
                    return updated;
                  });
                }}
              />
              
              {englishRecommendations.length === 0 ? (
                <p>{t('noRecommendations')}. {t('pleaseAddMasteredEnglishWords')}</p>
              ) : (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px', position: 'sticky', top: 0, backgroundColor: 'white', zIndex: 5, padding: '10px 0' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <p style={{ color: '#666', margin: 0, fontWeight: '500' }}>
                        {t('nextWordsToLearnCount').replace('{count}', englishRecommendations.length)}：
                      </p>
                      <button
                        onClick={() => handleGetEnglishWordRecommendations()}
                        disabled={loadingEnglishRecommendations}
                        className="btn"
                        style={{
                          padding: '6px 16px',
                          fontSize: '13px',
                          backgroundColor: loadingEnglishRecommendations ? '#ccc' : theme.actions.primary,
                          color: 'white',
                          border: 'none',
                          borderRadius: '6px',
                          cursor: loadingEnglishRecommendations ? 'not-allowed' : 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '5px',
                          fontWeight: '600',
                          transition: 'all 0.2s'
                        }}
                        title="Refresh Recommendations"
                      >
                        {loadingEnglishRecommendations ? '⏳' : '🔄'} {loadingEnglishRecommendations ? 'Loading...' : 'Refresh'}
                      </button>
                    </div>
                    {selectedEnglishRecommendations.size > 0 && (
                      <button
                        onClick={handleAddSelectedEnglishToMastered}
                        disabled={savingMasteredEnglishWords}
                        className="btn"
                        style={{ 
                          backgroundColor: theme.actions.success, 
                          color: 'white',
                          padding: '6px 16px',
                          borderRadius: '6px',
                          fontWeight: '600'
                        }}
                      >
                        {savingMasteredEnglishWords ? `💾 ${t('saving')}` : `✓ ${t('addSelected')} (${selectedEnglishRecommendations.size})`}
                      </button>
                    )}
                  </div>
                  <div key={recommendationsKey} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {englishRecommendations.map((rec, idx) => {
                      const isSelected = selectedEnglishRecommendations.has(rec.word);
                      const isAlreadyMastered = parseMasteredEnglishWords(profile.mastered_english_words).includes(rec.word);
                      
                      return (
                        <div key={`${rec.word}-${idx}`} style={{ 
                          padding: '12px 16px',
                          borderRadius: '10px',
                          border: `1px solid ${isSelected ? theme.actions.primary : '#eee'}`,
                          backgroundColor: isSelected ? `${theme.actions.primary}08` : 'white',
                          transition: 'all 0.2s'
                        }}>
                          <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                            <input
                              type="checkbox" checked={isSelected} disabled={isAlreadyMastered}
                              onChange={() => handleToggleEnglishRecommendation(rec.word)}
                              style={{ width: '18px', height: '18px', marginRight: '15px', cursor: 'pointer' }}
                            />
                            <div style={{ flex: 1 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                                <span style={{ 
                                  fontSize: '14px', 
                                  fontWeight: '800', 
                                  color: theme.actions.primary,
                                  backgroundColor: `${theme.actions.primary}15`,
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  minWidth: '40px',
                                  textAlign: 'center'
                                }}>
                                  #{idx + 1}
                                </span>
                                <span style={{ fontSize: '20px', fontWeight: '800', color: '#1a1a1a' }}>
                                  {rec.word}
                                </span>
                                {isAlreadyMastered && (
                                  <span style={{ 
                                    fontSize: '11px', 
                                    fontWeight: '600',
                                    color: theme.status.alreadyMastered, 
                                    backgroundColor: `${theme.status.alreadyMastered}15`,
                                    padding: '2px 6px',
                                    borderRadius: '4px',
                                    textTransform: 'uppercase'
                                  }}>
                                    {t('alreadyMastered')}
                                  </span>
                                )}
                              </div>
                              <div style={{ fontSize: '12px', color: '#999', fontWeight: '400', display: 'flex', flexWrap: 'wrap', alignItems: 'center' }}>
                                <span>P(Recommend): <strong style={{ color: '#555' }}>{(rec.score * 100).toFixed(1)}%</strong></span>
                                <span style={{ margin: '0 8px', color: '#ddd' }}>|</span>
                                {rec.log_ppr !== undefined && (
                                  <>
                                    <span>log(PPR): <strong style={{ color: '#555' }}>{rec.log_ppr.toFixed(2)}</strong></span>
                                    <span style={{ margin: '0 8px', color: '#ddd' }}>|</span>
                                  </>
                                )}
                                {rec.z_concreteness !== undefined ? (
                                  <>
                                    <span>Concreteness: <strong style={{ color: '#555' }}>{rec.z_concreteness.toFixed(2)}</strong></span>
                                    <span style={{ margin: '0 8px', color: '#ddd' }}>|</span>
                                  </>
                                ) : (
                                  typeof rec.concreteness === 'number' && (
                                    <>
                                      <span>Concreteness: <strong style={{ color: '#555' }}>{rec.concreteness.toFixed(1)}</strong></span>
                                      <span style={{ margin: '0 8px', color: '#ddd' }}>|</span>
                                    </>
                                  )
                                )}
                                {rec.log_frequency !== undefined ? (
                                  <>
                                    <span>Frequency: <strong style={{ color: '#555' }}>{rec.log_frequency.toFixed(2)}</strong></span>
                                    <span style={{ margin: '0 8px', color: '#ddd' }}>|</span>
                                  </>
                                ) : (
                                  rec.frequency_rank && (
                                    <>
                                      <span>Freq rank: <strong style={{ color: '#555' }}>{rec.frequency_rank}</strong></span>
                                      <span style={{ margin: '0 8px', color: '#ddd' }}>|</span>
                                    </>
                                  )
                                )}
                                {rec.cefr_level && <span>CEFR: <strong style={{ color: '#555' }}>{rec.cefr_level}</strong></span>}
                              </div>
                            </div>
                          </label>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
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

      {/* Chinese Word Recognition Modal */}
      {showChineseWordRecognition && selectedContentType === 'word' && selectedLanguage === 'zh' && (
        <div className="modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'white', padding: '20px', borderRadius: '8px', width: '90%', maxWidth: '1200px', maxHeight: '90vh', overflow: 'auto', position: 'relative'
          }}>
            <button onClick={() => setShowChineseWordRecognition(false)} style={{
              position: 'absolute', top: '10px', right: '10px', border: 'none', background: 'none', fontSize: '24px', cursor: 'pointer', zIndex: 1001
            }}>×</button>
            <ChineseWordRecognition profile={profile} onProfileUpdate={onProfileUpdate} />
          </div>
        </div>
      )}

      {/* English Word Recognition Modal */}
      {showEnglishWordRecognition && selectedContentType === 'word' && selectedLanguage === 'en' && (
        <div className="modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'white', padding: '20px', borderRadius: '8px', width: '90%', maxWidth: '1200px', maxHeight: '90vh', overflow: 'auto', position: 'relative'
          }}>
            <button onClick={() => setShowEnglishWordRecognition(false)} style={{
              position: 'absolute', top: '10px', right: '10px', border: 'none', background: 'none', fontSize: '24px', cursor: 'pointer', zIndex: 1001
            }}>×</button>
            <EnglishWordRecognition profile={profile} onProfileUpdate={onProfileUpdate} />
          </div>
        </div>
      )}

    </div>
  );
};

export default LanguageContentManager;
