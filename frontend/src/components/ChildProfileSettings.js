import React, { useState } from 'react';
import axios from 'axios';
import { useLanguage } from '../i18n/LanguageContext';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const ChildProfileSettings = ({ profiles, onProfilesChange }) => {
  const { t } = useLanguage();
  const [showForm, setShowForm] = useState(false);
  const [editingProfile, setEditingProfile] = useState(null);
  const [interestsInput, setInterestsInput] = useState('');
  const [charactersInput, setCharactersInput] = useState('');

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
    extracted_data: {}
  });

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleInterestsInputChange = (e) => {
    setInterestsInput(e.target.value);
  };

  const handleCharactersInputChange = (e) => {
    setCharactersInput(e.target.value);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const interests = interestsInput.split(',').map(item => item.trim()).filter(item => item);
      const character_roster = charactersInput.split(',').map(item => item.trim()).filter(item => item);
      
      const profileData = {
        ...formData,
        interests,
        character_roster,
        mental_age: formData.mental_age ? parseFloat(formData.mental_age) : null
      };
      
      if (editingProfile) {
        // Preserve existing mastered data if we are just editing metadata
        // We need to find the existing profile to merge
        const existing = profiles.find(p => p.name === editingProfile);
        if (existing) {
            profileData.mastered_words = existing.mastered_words;
            profileData.mastered_english_words = existing.mastered_english_words;
            profileData.mastered_grammar = existing.mastered_grammar;
        }

        await axios.put(`${API_BASE}/profiles/${editingProfile}`, profileData);
      } else {
        await axios.post(`${API_BASE}/profiles`, profileData);
      }
      
      const response = await axios.get(`${API_BASE}/profiles`);
      onProfilesChange(response.data);
      
      resetForm();
    } catch (error) {
      console.error('Error saving profile:', error);
    }
  };

  const resetForm = () => {
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
      extracted_data: {}
    });
    setInterestsInput('');
    setCharactersInput('');
    setShowForm(false);
    setEditingProfile(null);
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
      extracted_data: profile.extracted_data || {}
    });
    setInterestsInput((profile.interests || []).join(', '));
    setCharactersInput((profile.character_roster || []).join(', '));
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

  return (
    <div className="card">
      <h2>{t('profilesTitle')}</h2>
      <p>{t('profilesDescription')}</p>

      <div className="profiles-header">
        <button onClick={() => setShowForm(true)} className="btn">
          {t('addNewProfile')}
        </button>
      </div>

      {showForm && (
        <div className="card">
          <h3>{editingProfile ? t('editProfile') : t('addNewProfile')}</h3>
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <div className="form-group">
                <label>{t('name')} *</label>
                <input type="text" name="name" value={formData.name} onChange={handleInputChange} required />
              </div>
              <div className="form-group">
                <label>{t('dateOfBirth')}</label>
                <input type="date" name="dob" value={formData.dob} onChange={handleInputChange} />
              </div>
              <div className="form-group">
                <label>{t('gender')}</label>
                <select name="gender" value={formData.gender} onChange={handleInputChange}>
                  <option value="">{t('selectGender')}</option>
                  <option value="male">{t('male')}</option>
                  <option value="female">{t('female')}</option>
                  <option value="other">{t('other')}</option>
                </select>
              </div>
            </div>
            
            <div className="form-group">
                <label>Mental Age</label>
                <input type="number" name="mental_age" value={formData.mental_age} onChange={handleInputChange} min="1" max="18" step="0.5" />
                <small style={{color: '#666', fontSize: '12px'}}>Used for Age of Acquisition filtering.</small>
            </div>

            <div className="form-group">
              <label>{t('interests')}</label>
              <input type="text" name="interests" value={interestsInput} onChange={handleInterestsInputChange} placeholder={t('interestsPlaceholder')} />
            </div>

            <div className="form-group">
              <label>{t('characterRosterLabel')}</label>
              <input type="text" name="character_roster" value={charactersInput} onChange={handleCharactersInputChange} placeholder={t('characterRosterPlaceholder')} />
            </div>
            
            {/* Other fields omitted for brevity in this refactor, but can be added back if needed */}

            <div className="form-actions">
              <button type="submit" className="btn">{editingProfile ? t('updateProfile') : t('createProfile')}</button>
              <button type="button" onClick={resetForm} className="btn btn-secondary">{t('cancel')}</button>
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
                  <button onClick={() => handleEdit(profile)} className="btn btn-secondary">{t('edit')}</button>
                  <button onClick={() => handleDelete(profile.name)} className="btn btn-secondary">{t('delete')}</button>
                </div>
              </div>
              <div className="profile-details">
                 <div className="detail-row"><strong>{t('age')}:</strong> {profile.dob ? new Date().getFullYear() - new Date(profile.dob).getFullYear() : t('notSpecified')}</div>
                 <div className="detail-row"><strong>Mental Age:</strong> {profile.mental_age || t('notSpecified')}</div>
                 <div className="detail-row"><strong>{t('interests')}:</strong> {profile.interests?.join(', ') || t('noneSpecified')}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default ChildProfileSettings;

