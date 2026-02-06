import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { useLanguage } from '../i18n/LanguageContext';
import MasteredWordsManager from './MasteredWordsManager';
import MasteredEnglishWordsManager from './MasteredEnglishWordsManager';
import MasteredGrammarManager from './MasteredGrammarManager';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const ProfileManager = ({ profiles, onProfilesChange }) => {
  const { t } = useLanguage();
  const [showForm, setShowForm] = useState(false);
  const [editingProfile, setEditingProfile] = useState(null);
  const [interestsInput, setInterestsInput] = useState('');
  const [charactersInput, setCharactersInput] = useState('');
  const [masteredWordsInput, setMasteredWordsInput] = useState('');
  const [showRecommendations, setShowRecommendations] = useState(false);
  const [recommendations, setRecommendations] = useState([]);
  const [loadingRecommendations, setLoadingRecommendations] = useState(false);
  const [selectedProfileForRecommendations, setSelectedProfileForRecommendations] = useState(null);
  const [selectedRecommendations, setSelectedRecommendations] = useState(new Set());
  const [savingMasteredWords, setSavingMasteredWords] = useState(false);
  const [showMasteredWordsManager, setShowMasteredWordsManager] = useState(false);
  const [selectedProfileForMasteredWords, setSelectedProfileForMasteredWords] = useState(null);
  const [showMasteredGrammarManager, setShowMasteredGrammarManager] = useState(false);
  const [selectedProfileForMasteredGrammar, setSelectedProfileForMasteredGrammar] = useState(null);
  const [showGrammarRecommendations, setShowGrammarRecommendations] = useState(false);
  const [grammarRecommendations, setGrammarRecommendations] = useState([]);
  const [loadingGrammarRecommendations, setLoadingGrammarRecommendations] = useState(false);
  const [selectedProfileForGrammarRecommendations, setSelectedProfileForGrammarRecommendations] = useState(null);
  const [selectedGrammarRecommendations, setSelectedGrammarRecommendations] = useState(new Set());
  const [savingMasteredGrammar, setSavingMasteredGrammar] = useState(false);
  
  const [showMasteredEnglishWordsManager, setShowMasteredEnglishWordsManager] = useState(false);
  const [selectedProfileForMasteredEnglishWords, setSelectedProfileForMasteredEnglishWords] = useState(null);
  const [masteredEnglishWordsInput, setMasteredEnglishWordsInput] = useState('');
  const [showEnglishRecommendations, setShowEnglishRecommendations] = useState(false);
  const [englishRecommendations, setEnglishRecommendations] = useState([]);
  const [loadingEnglishRecommendations, setLoadingEnglishRecommendations] = useState(false);
  const [selectedProfileForEnglishRecommendations, setSelectedProfileForEnglishRecommendations] = useState(null);
  const [selectedEnglishRecommendations, setSelectedEnglishRecommendations] = useState(new Set());
  const [savingMasteredEnglishWords, setSavingMasteredEnglishWords] = useState(false);
  const [recommendationsKey, setRecommendationsKey] = useState(0); // Force re-render when changed
  const englishRecommendationsAbortController = useRef(null); // For canceling pending requests
  const englishRecommendationsRequestId = useRef(0); // Track request order

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      // Cancel any pending requests
      if (englishRecommendationsAbortController.current) {
        englishRecommendationsAbortController.current.abort();
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
  const [formData, setFormData] = useState({
    name: '',
    dob: '',
    gender: '',
    address: '',
    school: '',
    neighborhood: '',
    interests: [],
    character_roster: [],
    verbal_fluency: '',
    passive_language_level: '',
    mental_age: '',
    raw_input: '',
    mastered_words: '',
    mastered_english_words: '',
    mastered_grammar: '',
    extracted_data: {}
  });

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  // Just update the input text, don't process until submit
  const handleInterestsInputChange = (e) => {
    setInterestsInput(e.target.value);
  };

  const handleCharactersInputChange = (e) => {
    setCharactersInput(e.target.value);
  };

  const handleMasteredWordsInputChange = (e) => {
    setMasteredWordsInput(e.target.value);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      // Process comma-separated inputs into arrays
      const interests = interestsInput.split(',').map(item => item.trim()).filter(item => item);
      const character_roster = charactersInput.split(',').map(item => item.trim()).filter(item => item);
      
      const profileData = {
        ...formData,
        interests,
        character_roster,
        mastered_words: masteredWordsInput, // Store as text
        mastered_english_words: masteredEnglishWordsInput, // Store as text
        mental_age: formData.mental_age ? parseFloat(formData.mental_age) : null // Convert to number or null
      };
      
      if (editingProfile) {
        // Update existing profile
        await axios.put(`${API_BASE}/profiles/${editingProfile}`, profileData);
      } else {
        // Create new profile
        await axios.post(`${API_BASE}/profiles`, profileData);
      }
      
      // Refresh profiles
      const response = await axios.get(`${API_BASE}/profiles`);
      onProfilesChange(response.data);
      
      // Reset form
      setFormData({
        name: '',
        dob: '',
        gender: '',
        address: '',
        school: '',
        neighborhood: '',
        interests: [],
        character_roster: [],
        verbal_fluency: '',
        passive_language_level: '',
        mental_age: '',
        raw_input: '',
        mastered_words: '',
        mastered_english_words: '',
        mastered_grammar: '',
        extracted_data: {}
      });
      setInterestsInput('');
      setCharactersInput('');
      setMasteredWordsInput('');
      setMasteredEnglishWordsInput('');
      setShowForm(false);
      setEditingProfile(null);
    } catch (error) {
      console.error('Error saving profile:', error);
    }
  };

  const handleEdit = (profile) => {
    setFormData({
      name: profile.name || '',
      dob: profile.dob || '',
      gender: profile.gender || '',
      address: profile.address || '',
      school: profile.school || '',
      neighborhood: profile.neighborhood || '',
      interests: profile.interests || [],
      character_roster: profile.character_roster || [],
      verbal_fluency: profile.verbal_fluency || '',
      passive_language_level: profile.passive_language_level || '',
      mental_age: profile.mental_age || '',
      raw_input: profile.raw_input || '',
      mastered_words: profile.mastered_words || '',
      mastered_english_words: profile.mastered_english_words || '',
      mastered_grammar: profile.mastered_grammar || '',
      extracted_data: profile.extracted_data || {}
    });
    setInterestsInput((profile.interests || []).join(', '));
    setCharactersInput((profile.character_roster || []).join(', '));
    setMasteredWordsInput(profile.mastered_words || '');
    setMasteredEnglishWordsInput(profile.mastered_english_words || '');
    setEditingProfile(profile.name);
    setShowForm(true);
  };

  const handleDelete = async (profileName) => {
    if (window.confirm('Are you sure you want to delete this profile?')) {
      try {
        await axios.delete(`${API_BASE}/profiles/${profileName}`);
        const response = await axios.get(`${API_BASE}/profiles`);
        onProfilesChange(response.data);
      } catch (error) {
        console.error('Error deleting profile:', error);
      }
    }
  };

  const handleCancel = () => {
    setFormData({
      name: '',
      dob: '',
      gender: '',
      address: '',
      school: '',
      neighborhood: '',
      interests: [],
      character_roster: [],
      verbal_fluency: '',
      passive_language_level: '',
      mental_age: '',
      raw_input: '',
      mastered_words: '',
      mastered_english_words: '',
      mastered_grammar: '',
      extracted_data: {}
    });
    setInterestsInput('');
    setCharactersInput('');
    setMasteredWordsInput('');
    setShowForm(false);
    setEditingProfile(null);
  };

  const handleGetRecommendations = async (profile) => {
    setLoadingRecommendations(true);
    setSelectedProfileForRecommendations(profile);
    setSelectedRecommendations(new Set()); // Reset selections
    
    try {
      // Convert mastered_words string to array for the API
      const mastered_words_array = profile.mastered_words 
        ? profile.mastered_words.split(/[,\s，]+/).filter(w => w.trim())
        : [];
      
      console.log(`Getting Chinese recommendations with ${mastered_words_array.length} mastered words (PPR)`);
      
      // Use Standard Course defaults for Chinese PPR
      const mentalAge = profile.mental_age ? parseFloat(profile.mental_age) : null;
      const requestConfig = {
        profile_id: profile.id || profile.name,
        mastered_words: mastered_words_array.length > 0 ? mastered_words_array : undefined,
        mental_age: mentalAge || 8.0,
        beta_ppr: 1.0,
        beta_concreteness: 0.8,
        beta_frequency: 0.3,
        beta_aoa_penalty: 2.0,
        beta_intercept: 0.0,
        alpha: 0.5,
        aoa_buffer: 0.0,
        top_n: 50,
        exclude_multiword: false,
        max_hsk_level: 4
      };

      const response = await axios.post(`${API_BASE}/kg/chinese-ppr-recommendations?t=${Date.now()}`, requestConfig, {
        headers: {
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        }
      });
      
      console.log(`Got ${response.data.recommendations.length} recommendations`);
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

  const handleGetEnglishRecommendations = async (profile) => {
    // Cancel any pending request
    if (englishRecommendationsAbortController.current) {
      englishRecommendationsAbortController.current.abort();
    }
    
    // Create new abort controller for this request
    const abortController = new AbortController();
    englishRecommendationsAbortController.current = abortController;
    
    // Increment request ID to track order
    const currentRequestId = ++englishRecommendationsRequestId.current;
    
    setLoadingEnglishRecommendations(true);
    setSelectedProfileForEnglishRecommendations(profile);
    setSelectedEnglishRecommendations(new Set()); // Reset selections
    
    try {
      // Convert mastered_english_words string to array for the API
      const mastered_words_array = parseMasteredEnglishWords(profile.mastered_english_words);
      
      console.log(`[Request ${currentRequestId}] Getting English recommendations with ${mastered_words_array.length} mastered words (PPR)`);
      
      // Get mental age from profile (if available)
      const mentalAge = profile.mental_age ? parseFloat(profile.mental_age) : null;
      
      // Use Standard Course defaults for PPR
      const requestConfig = {
        profile_id: profile.id || profile.name,
        mastered_words: mastered_words_array.length > 0 ? mastered_words_array : undefined,
        mental_age: mentalAge || 8.0,
        beta_ppr: 1.0,
        beta_concreteness: 0.8,
        beta_frequency: 0.3,
        beta_aoa_penalty: 2.0,
        beta_intercept: 0.0,
        alpha: 0.5,
        aoa_buffer: 0.0,
        top_n: 50,
        exclude_multiword: false
      };
      
      // Use PPR algorithm
      const response = await axios.post(`${API_BASE}/kg/ppr-recommendations?t=${Date.now()}`, requestConfig, {
        headers: {
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        },
        signal: abortController.signal
      });
      
      // Check if this is still the latest request (ignore stale responses)
      if (currentRequestId !== englishRecommendationsRequestId.current) {
        console.log(`[Request ${currentRequestId}] Ignoring stale response (newer request ${englishRecommendationsRequestId.current} exists)`);
        return;
      }
      
      console.log(`[Request ${currentRequestId}] Got ${response.data.recommendations.length} English recommendations`);
      // Force a new array reference to ensure React re-renders
      const newRecommendations = [...(response.data.recommendations || [])];
      // Sort by score descending to ensure correct order
      newRecommendations.sort((a, b) => (b.score || 0) - (a.score || 0));
      
      // Log first few recommendations with scores for debugging
      console.log(`[Request ${currentRequestId}] Top 5 recommendations with scores:`);
      newRecommendations.slice(0, 5).forEach((rec, idx) => {
        console.log(
          `  ${idx + 1}. ${rec.word}: score=${rec.score?.toFixed(2)}, `
          + `CEFR=${rec.cefr_level}, conc=${rec.concreteness?.toFixed(2)}, `
          + `freqRank=${rec.frequency_rank ?? 'N/A'}, freqScore=${rec.frequency_score?.toFixed(2) ?? 'N/A'}`
        );
      });
      
      // Force React to re-render by updating key and setting recommendations
      setRecommendationsKey(prev => prev + 1);
      setEnglishRecommendations(newRecommendations);
      setShowEnglishRecommendations(true);
    } catch (error) {
      // Ignore aborted requests
      if (error.name === 'CanceledError' || error.message === 'canceled') {
        console.log(`[Request ${currentRequestId}] Request was canceled`);
        return;
      }
      // Check if this is still the latest request
      if (currentRequestId !== englishRecommendationsRequestId.current) {
        console.log(`[Request ${currentRequestId}] Ignoring error from stale request`);
        return;
      }
      console.error(`[Request ${currentRequestId}] Error getting English recommendations:`, error);
      const errorMessage = error.response?.data?.detail || error.message || 'Unknown error';
      alert(`Failed to get English recommendations: ${errorMessage}`);
    } finally {
      // Only update loading state if this is still the latest request
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
    if (selectedEnglishRecommendations.size === 0) {
      alert('Please select at least one word to add to the mastered list.');
      return;
    }

    if (!selectedProfileForEnglishRecommendations) {
      alert('Profile not found. Please close and reopen the recommendations.');
      return;
    }

    setSavingMasteredEnglishWords(true);
    try {
      // Get current mastered English words
      const currentMastered = parseMasteredEnglishWords(
        selectedProfileForEnglishRecommendations.mastered_english_words
      );
      
      // Add selected words (avoid duplicates)
      const newMastered = [...new Set([...currentMastered, ...Array.from(selectedEnglishRecommendations)])];
      
      // Update profile
      const updatedProfile = {
        ...selectedProfileForEnglishRecommendations,
        mastered_english_words: newMastered.join(', ')
      };
      
      await axios.put(`${API_BASE}/profiles/${selectedProfileForEnglishRecommendations.name}`, updatedProfile);
      
      // Refresh profiles
      const response = await axios.get(`${API_BASE}/profiles`);
      onProfilesChange(response.data);
      
      // Update the selected profile reference
      const updated = response.data.find(p => p.name === selectedProfileForEnglishRecommendations.name);
      if (updated) {
        setSelectedProfileForEnglishRecommendations(updated);
        // Refresh recommendations so the UI immediately reflects the newly mastered words
        await handleGetEnglishRecommendations(updated);
      }
      
      // Save count before clearing
      const addedCount = selectedEnglishRecommendations.size;
      
      // Clear selections
      setSelectedEnglishRecommendations(new Set());
      
      alert(`✅ Successfully added ${addedCount} word(s) to mastered English words list!`);
    } catch (error) {
      console.error('Error adding English words to mastered list:', error);
      alert('Failed to add words to mastered list. Please try again.');
    } finally {
      setSavingMasteredEnglishWords(false);
    }
  };

  const [grammarLanguage, setGrammarLanguage] = useState('zh'); // 'zh' for Chinese, 'en' for English
  
  const handleGetGrammarRecommendations = async (profile, lang = 'zh') => {
    setLoadingGrammarRecommendations(true);
    setSelectedProfileForGrammarRecommendations(profile);
    setSelectedGrammarRecommendations(new Set()); // Reset selections
    setGrammarLanguage(lang); // Set the language
    
    try {
      // Convert mastered_grammar string to array for the API
      // Grammar points are stored as URIs (gp_uri), split by comma only
      const mastered_grammar_array = profile.mastered_grammar 
        ? profile.mastered_grammar.split(',').map(g => g.trim()).filter(g => g)
        : [];
      
      console.log(`Getting ${lang.toUpperCase()} grammar recommendations with ${mastered_grammar_array.length} mastered grammar points`);
      
      const response = await axios.post(`${API_BASE}/kg/grammar-recommendations`, {
        mastered_grammar: mastered_grammar_array,
        profile_id: profile.id || profile.name,
        language: lang
      });
      
      console.log(`Got ${response.data.recommendations.length} ${lang.toUpperCase()} grammar recommendations`);
      setGrammarRecommendations(response.data.recommendations || []);
      setShowGrammarRecommendations(true);
    } catch (error) {
      console.error('Error getting grammar recommendations:', error);
      alert('Failed to get grammar recommendations. Please check if the knowledge graph server is running.');
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

  const handleAddSelectedToMastered = async () => {
    if (selectedRecommendations.size === 0) {
      alert('Please select at least one word to add to the mastered list.');
      return;
    }

    if (!selectedProfileForRecommendations) {
      alert('Profile not found. Please close and reopen the recommendations.');
      return;
    }

    setSavingMasteredWords(true);
    try {
      // Get current mastered words
      const currentMastered = selectedProfileForRecommendations.mastered_words 
        ? selectedProfileForRecommendations.mastered_words.split(/[,\s，]+/).map(w => w.trim()).filter(w => w)
        : [];
      
      // Add selected words (avoid duplicates)
      const newMastered = [...new Set([...currentMastered, ...Array.from(selectedRecommendations)])];
      
      // Update profile
      const updatedProfile = {
        ...selectedProfileForRecommendations,
        mastered_words: newMastered.join(', ')
      };
      
      await axios.put(`${API_BASE}/profiles/${selectedProfileForRecommendations.name}`, updatedProfile);
      
      // Refresh profiles
      const response = await axios.get(`${API_BASE}/profiles`);
      onProfilesChange(response.data);
      
      // Update the selected profile reference
      const updated = response.data.find(p => p.name === selectedProfileForRecommendations.name);
      if (updated) {
        setSelectedProfileForRecommendations(updated);
        
        // Also update selectedProfileForMasteredWords if it's the same profile (for modal refresh)
        // Create a new object to ensure React detects the change
        if (selectedProfileForMasteredWords && 
            (selectedProfileForMasteredWords.name === updated.name || 
             selectedProfileForMasteredWords.id === updated.id)) {
          console.log('ProfileManager: Updating selectedProfileForMasteredWords with new mastered_words:', updated.mastered_words);
          // Create a new object reference to ensure React detects the change
          // Force a new object by spreading and ensuring mastered_words is included
          setSelectedProfileForMasteredWords({ 
            ...updated,
            mastered_words: updated.mastered_words || '' // Ensure this field exists
          });
        }
      }
      
      // Save count before clearing
      const addedCount = selectedRecommendations.size;
      
      // Clear selections
      setSelectedRecommendations(new Set());
      
      alert(`✅ Successfully added ${addedCount} word(s) to mastered list!`);
    } catch (error) {
      console.error('Error adding words to mastered list:', error);
      alert('Failed to add words to mastered list. Please try again.');
    } finally {
      setSavingMasteredWords(false);
    }
  };

  const handleAddSelectedGrammarToMastered = async () => {
    if (selectedGrammarRecommendations.size === 0) {
      alert('Please select at least one grammar point to add to the mastered list.');
      return;
    }

    if (!selectedProfileForGrammarRecommendations) {
      alert('Profile not found. Please close and reopen the recommendations.');
      return;
    }

    setSavingMasteredGrammar(true);
    try {
      // Get current mastered grammar (URIs, comma-separated)
      const currentMastered = selectedProfileForGrammarRecommendations.mastered_grammar 
        ? selectedProfileForGrammarRecommendations.mastered_grammar.split(',').map(g => g.trim()).filter(g => g)
        : [];
      
      // Add selected grammar points (avoid duplicates)
      // selectedGrammarRecommendations contains URIs (gp_uri)
      const newMastered = [...new Set([...currentMastered, ...Array.from(selectedGrammarRecommendations)])];
      
      // Update profile
      const updatedProfile = {
        ...selectedProfileForGrammarRecommendations,
        mastered_grammar: newMastered.join(',') // Use comma only, no space (URIs don't need spaces)
      };
      
      await axios.put(`${API_BASE}/profiles/${selectedProfileForGrammarRecommendations.name}`, updatedProfile);
      
      // Refresh profiles
      const response = await axios.get(`${API_BASE}/profiles`);
      onProfilesChange(response.data);
      
      // Update the selected profile reference
      const updated = response.data.find(p => p.name === selectedProfileForGrammarRecommendations.name);
      if (updated) {
        setSelectedProfileForGrammarRecommendations(updated);
        
        // Also update selectedProfileForMasteredGrammar if it's the same profile (for modal refresh)
        // Create a new object to ensure React detects the change
        if (selectedProfileForMasteredGrammar && 
            (selectedProfileForMasteredGrammar.name === updated.name || 
             selectedProfileForMasteredGrammar.id === updated.id)) {
          // Create a new object reference to ensure React detects the change
          setSelectedProfileForMasteredGrammar({ ...updated });
        }
      }
      
      // Save count before clearing
      const addedCount = selectedGrammarRecommendations.size;
      
      // Clear selections
      setSelectedGrammarRecommendations(new Set());
      
      alert(`✅ Successfully added ${addedCount} grammar point(s) to mastered list!`);
    } catch (error) {
      console.error('Error adding grammar to mastered list:', error);
      alert('Failed to add grammar to mastered list. Please try again.');
    } finally {
      setSavingMasteredGrammar(false);
    }
  };

  const handleCloseMasteredGrammar = async () => {
    // Close modal first
    setShowMasteredGrammarManager(false);
    setSelectedProfileForMasteredGrammar(null);
    // Then refresh profiles to ensure main screen is up to date
    try {
      const response = await axios.get(`${API_BASE}/profiles`);
      onProfilesChange(response.data);
    } catch (error) {
      console.error('Error refreshing profiles:', error);
    }
  };

  return (
    <div className="card">
      <h2>{t('profilesTitle')}</h2>
      <p>{t('profilesDescription')}</p>

      <div className="profiles-header">
        <button 
          onClick={() => setShowForm(true)}
          className="btn"
        >
          {t('addNewProfile')}
        </button>
      </div>

      {showForm && (
        <div className="card">
          <h3>{editingProfile ? t('editProfile') : t('addNewProfile')}</h3>
          <form onSubmit={handleSubmit}>
            {/* Form fields same as before... */}
            <div className="form-row">
              <div className="form-group">
                <label>{t('name')} *</label>
                <input
                  type="text"
                  name="name"
                  value={formData.name}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <div className="form-group">
                <label>{t('dateOfBirth')}</label>
                <input
                  type="date"
                  name="dob"
                  value={formData.dob}
                  onChange={handleInputChange}
                />
              </div>
              <div className="form-group">
                <label>{t('gender')}</label>
                <select
                  name="gender"
                  value={formData.gender}
                  onChange={handleInputChange}
                >
                  <option value="">{t('selectGender')}</option>
                  <option value="male">{t('male')}</option>
                  <option value="female">{t('female')}</option>
                  <option value="other">{t('other')}</option>
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>{t('address')}</label>
                <input
                  type="text"
                  name="address"
                  value={formData.address}
                  onChange={handleInputChange}
                />
              </div>
              <div className="form-group">
                <label>{t('school')}</label>
                <input
                  type="text"
                  name="school"
                  value={formData.school}
                  onChange={handleInputChange}
                />
              </div>
              <div className="form-group">
                <label>{t('neighborhood')}</label>
                <input
                  type="text"
                  name="neighborhood"
                  value={formData.neighborhood}
                  onChange={handleInputChange}
                />
              </div>
            </div>

            <div className="form-group">
              <label>{t('interests')}</label>
              <input
                type="text"
                name="interests"
                value={interestsInput}
                onChange={handleInterestsInputChange}
                placeholder={t('interestsPlaceholder')}
              />
            </div>

            <div className="form-group">
              <label>{t('characterRosterLabel')}</label>
              <input
                type="text"
                name="character_roster"
                value={charactersInput}
                onChange={handleCharactersInputChange}
                placeholder={t('characterRosterPlaceholder')}
              />
              <small style={{color: '#666', fontSize: '12px'}}>
                {t('characterRosterHint')}
              </small>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>{t('verbalFluency')}</label>
                <select
                  name="verbal_fluency"
                  value={formData.verbal_fluency}
                  onChange={handleInputChange}
                >
                  <option value="">{t('selectLevel')}</option>
                  <option value="non-verbal">{t('nonVerbal')}</option>
                  <option value="limited">{t('limited')}</option>
                  <option value="developing">{t('developing')}</option>
                  <option value="fluent">{t('fluent')}</option>
                </select>
              </div>
              <div className="form-group">
                <label>{t('passiveLanguageLevel')}</label>
                <select
                  name="passive_language_level"
                  value={formData.passive_language_level}
                  onChange={handleInputChange}
                >
                  <option value="">{t('selectLevel')}</option>
                  <option value="beginner">{t('beginner')}</option>
                  <option value="intermediate">{t('intermediate')}</option>
                  <option value="advanced">{t('advanced')}</option>
                </select>
              </div>
              <div className="form-group">
                <label>Mental Age (for English word recommendations)</label>
                <input
                  type="number"
                  name="mental_age"
                  value={formData.mental_age}
                  onChange={handleInputChange}
                  min="1"
                  max="18"
                  step="0.5"
                  placeholder="e.g., 7.0"
                />
                <small style={{color: '#666', fontSize: '12px'}}>
                  Mental/developmental age in years. Used to filter out words that are too advanced (AoA &gt; mental_age + 2). Leave empty to disable AoA filtering.
                </small>
              </div>
            </div>

            <div className="form-group">
              <label>Mastered Words (Chinese)</label>
              <textarea
                name="mastered_words"
                value={masteredWordsInput}
                onChange={handleMasteredWordsInputChange}
                placeholder="苹果, 朋友, 老师, 学习, 学校, 水, 书, 车, 狗, 猫..."
                rows="4"
              />
              <small style={{color: '#666', fontSize: '12px'}}>
                Enter comma-separated Chinese words the child already knows (for vocabulary recommendations)
              </small>
              <div style={{ marginTop: '10px' }}>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedProfileForMasteredWords({
                      ...formData,
                      mastered_words: masteredWordsInput,
                      interests: interestsInput.split(',').map(i => i.trim()).filter(i => i),
                      character_roster: charactersInput.split(',').map(c => c.trim()).filter(c => c)
                    });
                    setShowMasteredWordsManager(true);
                  }}
                  className="btn btn-secondary"
                  style={{ fontSize: '14px' }}
                >
                  📚 Manage with Visual Selector
                </button>
              </div>
            </div>

            <div className="form-group">
              <label>Mastered Words (English)</label>
              <textarea
                name="mastered_english_words"
                value={masteredEnglishWordsInput}
                onChange={(e) => setMasteredEnglishWordsInput(e.target.value)}
                placeholder="cat, dog, house, book, water, food, friend, happy, big, small..."
                rows="4"
              />
              <small style={{color: '#666', fontSize: '12px'}}>
                Enter comma-separated English words the child already knows (for vocabulary recommendations)
              </small>
              <div style={{ marginTop: '10px' }}>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedProfileForMasteredEnglishWords({
                      ...formData,
                      mastered_english_words: masteredEnglishWordsInput,
                      interests: interestsInput.split(',').map(i => i.trim()).filter(i => i),
                      character_roster: charactersInput.split(',').map(c => c.trim()).filter(c => c)
                    });
                    setShowMasteredEnglishWordsManager(true);
                  }}
                  className="btn btn-secondary"
                  style={{ fontSize: '14px' }}
                >
                  📚 Manage with Visual Selector
                </button>
              </div>
            </div>

            <div className="form-group">
              <label>{t('rawInput')}</label>
              <textarea
                name="raw_input"
                value={formData.raw_input}
                onChange={handleInputChange}
                placeholder={t('rawInputPlaceholder')}
              />
            </div>

            <div className="form-actions">
              <button type="submit" className="btn">
                {editingProfile ? t('updateProfile') : t('createProfile')}
              </button>
              <button type="button" onClick={handleCancel} className="btn btn-secondary">
                {t('cancel')}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="profiles-list">
        {profiles.length === 0 ? (
          <p>{t('noProfilesYet')}</p>
        ) : (
          profiles.map(profile => (
            <div key={profile.name} className="profile-card">
              <div className="profile-header">
                <h3>{profile.name}</h3>
                <div className="profile-actions">
                  <button 
                    onClick={() => {
                      setSelectedProfileForMasteredWords(profile);
                      setShowMasteredWordsManager(true);
                    }}
                    className="btn"
                  >
                    📝 {t('manageMasteredWords')} ({t('chineseVocabulary')})
                  </button>
                  <button 
                    onClick={() => {
                      setSelectedProfileForMasteredEnglishWords(profile);
                      setShowMasteredEnglishWordsManager(true);
                    }}
                    className="btn"
                  >
                    📝 {t('manageMasteredEnglishWords')}
                  </button>
                  <button 
                    onClick={() => {
                      setSelectedProfileForMasteredGrammar(profile);
                      setShowMasteredGrammarManager(true);
                    }}
                    className="btn"
                  >
                    📖 {t('manageMasteredGrammar')}
                  </button>
                  <button 
                    onClick={() => handleGetRecommendations(profile)}
                    className="btn"
                    disabled={loadingRecommendations}
                  >
                    {loadingRecommendations ? t('saving') : `📚 ${t('getWordRecommendations')} (${t('chineseVocabulary')})`}
                  </button>
                  <button 
                    onClick={() => handleGetEnglishRecommendations(profile)}
                    className="btn"
                    disabled={loadingEnglishRecommendations}
                  >
                    {loadingEnglishRecommendations ? t('saving') : `📚 ${t('getWordRecommendations')} (${t('englishVocabulary')})`}
                  </button>
                  <button 
                    onClick={() => handleGetGrammarRecommendations(profile)}
                    className="btn"
                    disabled={loadingGrammarRecommendations}
                  >
                    {loadingGrammarRecommendations ? t('saving') : `📖 ${t('getGrammarRecommendations')}`}
                  </button>
                  <button 
                    onClick={() => handleEdit(profile)}
                    className="btn btn-secondary"
                  >
                    {t('edit')}
                  </button>
                  <button 
                    onClick={() => handleDelete(profile.name)}
                    className="btn btn-secondary"
                  >
                    {t('delete')}
                  </button>
                </div>
              </div>
              <div className="profile-details">
                <div className="detail-row">
                  <strong>{t('age')}:</strong> {profile.dob ? new Date().getFullYear() - new Date(profile.dob).getFullYear() : t('notSpecified')}
                </div>
                <div className="detail-row">
                  <strong>{t('gender')}:</strong> {profile.gender || t('notSpecified')}
                </div>
                <div className="detail-row">
                  <strong>Mental Age:</strong> {profile.mental_age ? `${profile.mental_age} years` : t('notSpecified')}
                </div>
                <div className="detail-row">
                  <strong>{t('school')}:</strong> {profile.school || t('notSpecified')}
                </div>
                <div className="detail-row">
                  <strong>{t('interests')}:</strong> {profile.interests?.join(', ') || t('noneSpecified')}
                </div>
                <div className="detail-row">
                  <strong>{t('characterRosterLabel')}:</strong> {profile.character_roster?.join(', ') || t('noneSpecified')}
                </div>
                <div className="detail-row">
                  <strong>{t('verbalFluency')}:</strong> {profile.verbal_fluency || t('notSpecified')}
                </div>
                <div className="detail-row">
                  <strong>{t('passiveLanguageLevel')}:</strong> {profile.passive_language_level || t('notSpecified')}
                </div>
                <div className="detail-row" style={{
                  marginTop: '10px',
                  padding: '10px',
                  backgroundColor: '#f0f4ff',
                  border: '1px solid #cfe2ff',
                  borderRadius: '8px',
                  whiteSpace: 'pre-line'
                }}>
                  <strong>{t('additionalNotes')}:</strong> {profile.raw_input ? profile.raw_input : <span style={{ color: '#999', fontStyle: 'italic' }}>{t('noAdditionalNotes') || 'No additional notes'}</span>}
                  </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Recommendations Modal */}
      {showRecommendations && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'white',
            padding: '30px',
            borderRadius: '8px',
            maxWidth: '600px',
            maxHeight: '80vh',
            overflow: 'auto',
            position: 'relative'
          }}>
            <button
              onClick={() => setShowRecommendations(false)}
              style={{
                position: 'absolute',
                top: '10px',
                right: '10px',
                background: 'none',
                border: 'none',
                fontSize: '24px',
                cursor: 'pointer'
              }}
            >
              ×
            </button>
            <h2>📚 {t('wordRecommendations')}</h2>
            {selectedProfileForRecommendations && (
              <p style={{ color: '#666', marginBottom: '20px' }}>
                For: <strong>{selectedProfileForRecommendations.name}</strong>
              </p>
            )}
            
            {recommendations.length === 0 ? (
              <p>{t('noRecommendations')}. {t('pleaseAddMasteredWords')}</p>
            ) : (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <p style={{ color: '#666', margin: 0 }}>
                    Based on the words the child already knows, here are the next 50 words to learn (PPR Smart Recommendation):
                  </p>
                  {selectedRecommendations.size > 0 && (
                    <button
                      onClick={handleAddSelectedToMastered}
                      disabled={savingMasteredWords}
                      className="btn"
                      style={{
                        backgroundColor: '#4CAF50',
                        color: 'white',
                        padding: '8px 16px',
                        fontSize: '14px'
                      }}
                    >
                      {savingMasteredWords ? `💾 ${t('saving')}` : `✓ ${t('addSelected')} (${selectedRecommendations.size})`}
                    </button>
                  )}
                </div>
                <ol style={{ paddingLeft: '20px' }}>
                  {recommendations.map((rec, idx) => {
                    const isSelected = selectedRecommendations.has(rec.word);
                    const isAlreadyMastered = selectedProfileForRecommendations?.mastered_words
                      ? selectedProfileForRecommendations.mastered_words.split(/[,\s，]+/).map(w => w.trim()).includes(rec.word)
                      : false;
                    
                    // Use a stable key based on word instead of index
                    const itemKey = rec.word || `word-${idx}`;
                    
                    return (
                      <li key={itemKey} style={{ marginBottom: '15px', paddingLeft: '5px' }}>
                        <label style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          cursor: 'pointer',
                          padding: '8px',
                          borderRadius: '4px',
                          backgroundColor: isSelected ? '#e8f5e9' : isAlreadyMastered ? '#fff3e0' : 'transparent',
                          border: isSelected ? '2px solid #4CAF50' : isAlreadyMastered ? '1px solid #ff9800' : '1px solid transparent'
                        }}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => handleToggleRecommendation(rec.word)}
                            disabled={isAlreadyMastered}
                            style={{
                              marginRight: '10px',
                              marginTop: '4px',
                              cursor: isAlreadyMastered ? 'not-allowed' : 'pointer',
                              transform: 'scale(1.2)'
                            }}
                          />
                          <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: 'bold', fontSize: '18px' }}>
                              {rec.word}
                              {isAlreadyMastered && (
                                <span style={{ fontSize: '12px', color: '#ff9800', marginLeft: '8px' }}>
                                  ({t('alreadyMastered')})
                                </span>
                              )}
                              {rec.pinyin && <span style={{ fontSize: '14px', color: '#666', marginLeft: '10px' }}>
                                ({rec.pinyin})
                              </span>}
                            </div>
                            <div style={{ fontSize: '12px', color: '#888', marginTop: '3px' }}>
                              P(推荐): {(rec.score * 100).toFixed(1)}% |
                              {rec.log_ppr !== undefined && ` log(PPR): ${rec.log_ppr.toFixed(2)} |`}
                              {rec.z_concreteness !== undefined && ` Z(具体): ${rec.z_concreteness.toFixed(2)} |`}
                              {rec.log_frequency !== undefined && ` log(${t('frequency')}): ${rec.log_frequency.toFixed(2)} |`}
                              {rec.aoa_penalty !== undefined && rec.aoa_penalty > 0 && ` AoA惩罚: ${rec.aoa_penalty.toFixed(1)} |`}
                              {rec.hsk_level && ` HSK: ${rec.hsk_level}`}
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

      {/* Mastered Words Manager Modal */}
      {showMasteredWordsManager && selectedProfileForMasteredWords && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'white',
            padding: '20px',
            borderRadius: '8px',
            maxWidth: '900px',
            width: '90%',
            maxHeight: '90vh',
            overflow: 'auto',
            position: 'relative'
          }}>
            <button
              onClick={() => {
                setShowMasteredWordsManager(false);
                setSelectedProfileForMasteredWords(null);
                // Refresh profiles after closing
                axios.get(`${API_BASE}/profiles`).then(response => {
                  onProfilesChange(response.data);
                });
              }}
              style={{
                position: 'absolute',
                top: '10px',
                right: '10px',
                background: 'none',
                border: 'none',
                fontSize: '24px',
                cursor: 'pointer',
                zIndex: 1001
              }}
            >
              ×
            </button>
            <MasteredWordsManager
              key={`${selectedProfileForMasteredWords?.name}-${selectedProfileForMasteredWords?.mastered_words?.length || 0}`}
              profile={selectedProfileForMasteredWords}
              onUpdate={async () => {
                // Refresh profiles
                const response = await axios.get(`${API_BASE}/profiles`);
                onProfilesChange(response.data);
                // Update selected profile
                const updated = response.data.find(p => 
                  p.name === selectedProfileForMasteredWords.name || 
                  p.id === selectedProfileForMasteredWords.id
                );
                if (updated) {
                  setSelectedProfileForMasteredWords(updated);
                }
              }}
            />
          </div>
        </div>
      )}

      {/* English Words Manager Modal */}
      {showMasteredEnglishWordsManager && selectedProfileForMasteredEnglishWords && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'white',
            padding: '20px',
            borderRadius: '8px',
            maxWidth: '900px',
            width: '90%',
            maxHeight: '90vh',
            overflow: 'auto',
            position: 'relative'
          }}>
            <button
              onClick={() => {
                setShowMasteredEnglishWordsManager(false);
                setSelectedProfileForMasteredEnglishWords(null);
                // Refresh profiles after closing
                axios.get(`${API_BASE}/profiles`).then(response => {
                  onProfilesChange(response.data);
                });
              }}
              style={{
                position: 'absolute',
                top: '10px',
                right: '10px',
                background: 'none',
                border: 'none',
                fontSize: '24px',
                cursor: 'pointer',
                zIndex: 1001
              }}
            >
              ×
            </button>
            <MasteredEnglishWordsManager
              key={`${selectedProfileForMasteredEnglishWords?.name}-${selectedProfileForMasteredEnglishWords?.mastered_english_words?.length || 0}`}
              profile={selectedProfileForMasteredEnglishWords}
              onUpdate={async () => {
                // Refresh profiles
                const response = await axios.get(`${API_BASE}/profiles`);
                onProfilesChange(response.data);
                // Update selected profile
                const updated = response.data.find(p => 
                  p.name === selectedProfileForMasteredEnglishWords.name || 
                  p.id === selectedProfileForMasteredEnglishWords.id
                );
                if (updated) {
                  setSelectedProfileForMasteredEnglishWords(updated);
                }
              }}
            />
          </div>
        </div>
      )}

      {/* Grammar Recommendations Modal */}
      {showGrammarRecommendations && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'white',
            padding: '30px',
            borderRadius: '8px',
            maxWidth: '600px',
            maxHeight: '80vh',
            overflow: 'auto',
            position: 'relative'
          }}>
            <button
              onClick={() => setShowGrammarRecommendations(false)}
              style={{
                position: 'absolute',
                top: '10px',
                right: '10px',
                background: 'none',
                border: 'none',
                fontSize: '24px',
                cursor: 'pointer'
              }}
            >
              ×
            </button>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 style={{ margin: 0 }}>
                📖 {t('grammarRecommendations')} ({grammarLanguage === 'en' ? t('englishGrammar') : t('chineseGrammar')})
              </h2>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  onClick={() => handleGetGrammarRecommendations(selectedProfileForGrammarRecommendations, 'zh')}
                  className="btn"
                  style={{
                    backgroundColor: grammarLanguage === 'zh' ? '#1976d2' : '#e0e0e0',
                    color: grammarLanguage === 'zh' ? 'white' : '#333',
                    padding: '6px 12px',
                    fontSize: '12px',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                >
                  中文
                </button>
                <button
                  onClick={() => handleGetGrammarRecommendations(selectedProfileForGrammarRecommendations, 'en')}
                  className="btn"
                  style={{
                    backgroundColor: grammarLanguage === 'en' ? '#1976d2' : '#e0e0e0',
                    color: grammarLanguage === 'en' ? 'white' : '#333',
                    padding: '6px 12px',
                    fontSize: '12px',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                >
                  English
                </button>
              </div>
            </div>
            {selectedProfileForGrammarRecommendations && (
              <p style={{ color: '#666', marginBottom: '20px' }}>
                For: <strong>{selectedProfileForGrammarRecommendations.name}</strong>
              </p>
            )}
            
            {grammarRecommendations.length === 0 ? (
              <p>No grammar recommendations available. Please add mastered grammar points to the profile first.</p>
            ) : (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <p style={{ color: '#666', margin: 0 }}>
                    Based on the grammar points the child already knows, here are the next 50 grammar points to learn:
                  </p>
                  {selectedGrammarRecommendations.size > 0 && (
                    <button
                      onClick={handleAddSelectedGrammarToMastered}
                      disabled={savingMasteredGrammar}
                      className="btn"
                      style={{
                        backgroundColor: '#4CAF50',
                        color: 'white',
                        padding: '8px 16px',
                        fontSize: '14px'
                      }}
                    >
                      {savingMasteredGrammar ? `💾 ${t('saving')}` : `✓ ${t('addSelected')} (${selectedGrammarRecommendations.size})`}
                    </button>
                  )}
                </div>
                <ol style={{ paddingLeft: '20px' }}>
                  {grammarRecommendations.map((rec, idx) => {
                    // Use gp_uri for tracking selections (URIs don't contain commas)
                    const recId = rec.gp_uri || rec.grammar_point;
                    const isSelected = selectedGrammarRecommendations.has(recId);
                    const mastered_grammar_list = selectedProfileForGrammarRecommendations?.mastered_grammar
                      ? selectedProfileForGrammarRecommendations.mastered_grammar.split(',').map(g => g.trim())
                      : [];
                    const isAlreadyMastered = mastered_grammar_list.includes(rec.gp_uri || rec.grammar_point);
                    
                    // Use gp_uri as the key (more stable than name)
                    const itemKey = rec.gp_uri || rec.grammar_point || `grammar-${idx}`;
                    
                    return (
                      <li key={itemKey} style={{ marginBottom: '15px', paddingLeft: '5px' }}>
                        <label style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          cursor: 'pointer',
                          padding: '8px',
                          borderRadius: '4px',
                          backgroundColor: isSelected ? '#e8f5e9' : isAlreadyMastered ? '#fff3e0' : 'transparent',
                          border: isSelected ? '2px solid #4CAF50' : isAlreadyMastered ? '1px solid #ff9800' : '1px solid transparent'
                        }}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => handleToggleGrammarRecommendation(rec.gp_uri || rec.grammar_point)}
                            disabled={isAlreadyMastered}
                            style={{
                              marginRight: '10px',
                              marginTop: '4px',
                              cursor: isAlreadyMastered ? 'not-allowed' : 'pointer',
                              transform: 'scale(1.2)'
                            }}
                          />
                          <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: 'bold', fontSize: '16px' }}>
                              {grammarLanguage === 'en' ? (
                                <>
                              {rec.grammar_point}
                              {rec.grammar_point_zh && (
                                <span style={{ fontSize: '14px', color: '#666', marginLeft: '10px' }}>
                                  ({rec.grammar_point_zh})
                                </span>
                                  )}
                                </>
                              ) : (
                                <>
                                  {rec.grammar_point_zh || rec.grammar_point}
                                  {rec.grammar_point_zh && rec.grammar_point !== rec.grammar_point_zh && (
                                    <span style={{ fontSize: '14px', color: '#666', marginLeft: '10px' }}>
                                      ({rec.grammar_point})
                                    </span>
                                  )}
                                </>
                              )}
                              {isAlreadyMastered && (
                                <span style={{ fontSize: '12px', color: '#ff9800', marginLeft: '8px' }}>
                                  ({t('alreadyMastered')})
                                </span>
                              )}
                            </div>
                            {rec.structure && (
                              <div style={{ fontSize: '13px', color: '#555', marginTop: '3px', fontFamily: 'monospace' }}>
                                {rec.structure}
                              </div>
                            )}
                            {rec.example_chinese && (
                              <div style={{ fontSize: '13px', color: '#1976d2', marginTop: '3px', fontStyle: 'italic' }}>
                                {rec.example_chinese}
                              </div>
                            )}
                            <div style={{ fontSize: '12px', color: '#888', marginTop: '3px' }}>
                              CEFR Level: {rec.cefr_level || 'Not specified'} | Score: {rec.score}
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
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'white',
            padding: '30px',
            borderRadius: '8px',
            maxWidth: '600px',
            maxHeight: '80vh',
            overflow: 'auto',
            position: 'relative'
          }}>
            <button
              onClick={() => setShowEnglishRecommendations(false)}
              style={{
                position: 'absolute',
                top: '10px',
                right: '10px',
                background: 'none',
                border: 'none',
                fontSize: '24px',
                cursor: 'pointer'
              }}
            >
              ×
            </button>
            <h2>📚 {t('englishRecommendations')}</h2>
            {selectedProfileForEnglishRecommendations && (
              <p style={{ color: '#666', marginBottom: '20px' }}>
                For: <strong>{selectedProfileForEnglishRecommendations.name}</strong>
              </p>
            )}
            
            {englishRecommendations.length === 0 ? (
              <p>{t('noRecommendations')}. {t('pleaseAddMasteredEnglishWords')}</p>
            ) : (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <p style={{ color: '#666', margin: 0 }}>
                    Based on the English words the child already knows, here are the next 50 words to learn (PPR Smart Recommendation):
                  </p>
                  {selectedEnglishRecommendations.size > 0 && (
                    <button
                      onClick={handleAddSelectedEnglishToMastered}
                      disabled={savingMasteredEnglishWords}
                      className="btn"
                      style={{
                        backgroundColor: '#4CAF50',
                        color: 'white',
                        padding: '8px 16px',
                        fontSize: '14px'
                      }}
                    >
                      {savingMasteredEnglishWords ? `💾 ${t('saving')}` : `✓ ${t('addSelected')} (${selectedEnglishRecommendations.size})`}
                    </button>
                  )}
                </div>
                <ol key={`recommendations-${recommendationsKey}`} style={{ paddingLeft: '20px' }}>
                  {englishRecommendations.map((rec, idx) => {
                    const isSelected = selectedEnglishRecommendations.has(rec.word);
                    const isAlreadyMastered = selectedProfileForEnglishRecommendations?.mastered_english_words
                      ? parseMasteredEnglishWords(selectedProfileForEnglishRecommendations.mastered_english_words).includes(rec.word)
                      : false;
                    
                    // Use word + score + key to force re-render when scores change
                    const itemKey = `rec-${recommendationsKey}-${rec.word}-${rec.score?.toFixed(3) || idx}`;
                    
                    return (
                      <li key={itemKey} style={{ marginBottom: '15px', paddingLeft: '5px' }}>
                        <label style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          cursor: 'pointer',
                          padding: '8px',
                          borderRadius: '4px',
                          backgroundColor: isSelected ? '#e8f5e9' : isAlreadyMastered ? '#fff3e0' : 'transparent',
                          border: isSelected ? '2px solid #4CAF50' : isAlreadyMastered ? '1px solid #ff9800' : '1px solid transparent'
                        }}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => handleToggleEnglishRecommendation(rec.word)}
                            disabled={isAlreadyMastered}
                            style={{
                              marginRight: '10px',
                              marginTop: '4px',
                              cursor: isAlreadyMastered ? 'not-allowed' : 'pointer',
                              transform: 'scale(1.2)'
                            }}
                          />
                          <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: 'bold', fontSize: '18px' }}>
                              {rec.word}
                              {isAlreadyMastered && (
                                <span style={{ fontSize: '12px', color: '#ff9800', marginLeft: '8px' }}>
                                  ({t('alreadyMastered')})
                                </span>
                              )}
                            </div>
                            <div style={{ fontSize: '12px', color: '#888', marginTop: '3px' }}>
                              <span style={{ fontWeight: 'bold', color: '#4CAF50' }}>
                                #{idx + 1}
                              </span>
                              {' '}P(Recommend): {(rec.score * 100).toFixed(1)}%
                              {typeof rec.concreteness === 'number' && (
                                <span style={{ marginLeft: '8px', color: '#1976d2' }}>
                                  | Concreteness: {rec.concreteness.toFixed(1)}
                                </span>
                              )}
                              {typeof rec.age_of_acquisition === 'number' && (
                                <span style={{ marginLeft: '8px', color: '#9c27b0' }}>
                                  | AoA: {rec.age_of_acquisition.toFixed(1)}
                                </span>
                              )}
                              {rec.frequency_rank && (
                                <span style={{ marginLeft: '8px', color: '#6d4c41' }}>
                                  | Freq rank: {rec.frequency_rank}
                                </span>
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

      {/* Mastered Grammar Manager Modal */}
      {showMasteredGrammarManager && selectedProfileForMasteredGrammar && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'white',
            padding: '20px',
            borderRadius: '8px',
            maxWidth: '900px',
            width: '90%',
            maxHeight: '90vh',
            overflow: 'auto',
            position: 'relative'
          }}>
            <button
              onClick={handleCloseMasteredGrammar}
              style={{
                position: 'absolute',
                top: '10px',
                right: '10px',
                background: 'none',
                border: 'none',
                fontSize: '24px',
                cursor: 'pointer',
                zIndex: 1001
              }}
            >
              ×
            </button>
            <MasteredGrammarManager
              profile={selectedProfileForMasteredGrammar}
              onClose={handleCloseMasteredGrammar}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default ProfileManager;
