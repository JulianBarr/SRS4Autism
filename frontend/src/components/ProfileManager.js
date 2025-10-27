import React, { useState } from 'react';
import axios from 'axios';
import { useLanguage } from '../i18n/LanguageContext';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const ProfileManager = ({ profiles, onProfilesChange }) => {
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

  // Just update the input text, don't process until submit
  const handleInterestsInputChange = (e) => {
    setInterestsInput(e.target.value);
  };

  const handleCharactersInputChange = (e) => {
    setCharactersInput(e.target.value);
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
        character_roster
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
        raw_input: '',
        extracted_data: {}
      });
      setInterestsInput('');
      setCharactersInput('');
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
      raw_input: '',
      extracted_data: {}
    });
    setInterestsInput('');
    setCharactersInput('');
    setShowForm(false);
    setEditingProfile(null);
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
                {profile.raw_input && (
                  <div className="detail-row">
                    <strong>{t('additionalNotes')}:</strong> {profile.raw_input}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default ProfileManager;

