import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ChatAssistant from './components/ChatAssistant';
import CardCuration from './components/CardCuration';
import ChildProfileSettings from './components/ChildProfileSettings';
import LanguageContentManager from './components/LanguageContentManager';
import TemplateManager from './components/TemplateManager';
import ContentCategoryNav from './components/ContentCategoryNav';
import { useLanguage } from './i18n/LanguageContext';
import './App.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const { language, toggleLanguage, t } = useLanguage();
  const [activeTab, setActiveTab] = useState('main');
  const [activeCategory, setActiveCategory] = useState('language'); // Content category
  const [profiles, setProfiles] = useState([]);
  const [currentProfile, setCurrentProfile] = useState(null);
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [logoError, setLogoError] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  // Ensure currentProfile is valid when profiles change
  useEffect(() => {
    if (profiles.length > 0) {
      if (!currentProfile) {
        // Default to first profile if none selected
        setCurrentProfile(profiles[0]);
      } else {
        // Verify selected profile still exists, update ref if data changed
        const found = profiles.find(p => p.name === currentProfile.name || p.id === currentProfile.id);
        if (found) {
          // Only update if data is different to avoid loops, but profiles usually come from API fresh
          if (JSON.stringify(found) !== JSON.stringify(currentProfile)) {
             setCurrentProfile(found);
          }
        } else {
          // Profile was deleted, switch to first or null
          setCurrentProfile(profiles[0] || null);
        }
      }
    } else {
      setCurrentProfile(null);
    }
  }, [profiles, currentProfile]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [profilesRes, cardsRes] = await Promise.all([
        axios.get(`${API_BASE}/profiles`),
        axios.get(`${API_BASE}/cards`)
      ]);
      setProfiles(profilesRes.data);
      setCards(cardsRes.data);
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleNewCard = async (newCard) => {
    // Optimistically add the new card without full page reload
    if (newCard) {
      setCards(prev => {
        // Check if card already exists to avoid duplicates
        const exists = prev.some(c => c.id === newCard.id);
        if (exists) return prev;
        return [newCard, ...prev];
      });
    }
    // Optionally refresh in background (non-blocking)
    setTimeout(() => {
      loadData();
    }, 1000);
  };

  const handleApproveCard = async (cardId) => {
    try {
      await axios.put(`${API_BASE}/cards/${cardId}/approve`);
      setCards(prev => prev.map(card => 
        card.id === cardId ? { ...card, status: 'approved' } : card
      ));
    } catch (error) {
      console.error('Error approving card:', error);
    }
  };

  if (loading) {
                return (
                  <div className="container">
                    <div className="card">
                      <h2>Loading Curious Mario (好奇马力)...</h2>
                    </div>
                  </div>
                );
  }

  return (
    <div className="App">
      <header className="app-header">
        <div className="container header-inner">
          <div className="header-top">
            <div className="logo-container">
              {!logoError && (
                <img 
                  src="/logo.png" 
                  alt="Curious Mario Logo" 
                  className="app-logo"
                  onError={() => setLogoError(true)}
                />
              )}
              <h1>{t('appTitle')}</h1>
            </div>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px', marginLeft: 'auto' }}>
              {/* Profile Selector */}
              {profiles.length > 0 && (
                 <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                   <span style={{ fontSize: '1.2em' }}>🧒</span>
                   <select 
                     value={currentProfile?.name || ''}
                     onChange={(e) => {
                       const selected = profiles.find(p => p.name === e.target.value);
                       setCurrentProfile(selected);
                     }}
                     style={{ padding: '5px', borderRadius: '4px', border: '1px solid #ccc' }}
                   >
                     {profiles.map(p => (
                       <option key={p.name} value={p.name}>{p.name}</option>
                     ))}
                   </select>
                 </div>
              )}

              <button 
                className="language-toggle"
                onClick={toggleLanguage}
                title={language === 'en' ? '切换到中文' : 'Switch to English'}
              >
                {language === 'en' ? '中文' : 'English'}
              </button>
            </div>
          </div>
          <nav className="tab-nav">
            <button 
              className={activeTab === 'main' ? 'active' : ''}
              onClick={() => setActiveTab('main')}
            >
              {t('mainWorkflow')}
            </button>
            <button 
              className={activeTab === 'content' ? 'active' : ''}
              onClick={() => setActiveTab('content')}
            >
              {t('contentManagement') || (language === 'en' ? 'Content Management' : '内容管理')}
            </button>
            <button 
              className={activeTab === 'profiles' ? 'active' : ''}
              onClick={() => setActiveTab('profiles')}
            >
              {t('profiles')}
            </button>
            <button 
              className={activeTab === 'templates' ? 'active' : ''}
              onClick={() => setActiveTab('templates')}
            >
              {t('templates')}
            </button>
          </nav>
        </div>
      </header>

      <main className="container">
        {activeTab === 'main' && (
          <div className="main-workflow">
            <div className="workflow-left">
              <ChatAssistant 
                profiles={profiles}
                currentProfile={currentProfile}
                onNewCard={handleNewCard}
              />
            </div>
            <div className="workflow-right">
              <CardCuration 
                cards={cards}
                onApproveCard={handleApproveCard}
                onRefresh={loadData}
              />
            </div>
          </div>
        )}

        {activeTab === 'content' && (
          <div>
            {/* Content Category Navigation */}
            <ContentCategoryNav 
              activeCategory={activeCategory}
              onCategoryChange={setActiveCategory}
            />
            
            {/* Category Content */}
            {activeCategory === 'language' && (
               <div style={{ marginTop: '20px', padding: '20px', backgroundColor: '#f5f5f5', borderRadius: '8px' }}>
                  <LanguageContentManager 
                    profile={currentProfile} 
                    onProfileUpdate={loadData}
                  />
               </div>
            )}
            
            {activeCategory === 'math' && (
              <div style={{ marginTop: '20px', padding: '20px', textAlign: 'center', color: '#666' }}>
                <h2>🔢 {t('math')}</h2>
                <p>Math learning content coming soon...</p>
              </div>
            )}
            
            {activeCategory === 'knowledge' && (
              <div style={{ marginTop: '20px', padding: '20px', textAlign: 'center', color: '#666' }}>
                <h2>🌍 {t('commonKnowledge')}</h2>
                <p>Common knowledge content coming soon...</p>
              </div>
            )}
            
            {activeCategory === 'culture' && (
              <div style={{ marginTop: '20px', padding: '20px', textAlign: 'center', color: '#666' }}>
                <h2>🎭 {t('culture')}</h2>
                <p>Culture content coming soon...</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'profiles' && (
          <ChildProfileSettings 
            profiles={profiles}
            onProfilesChange={setProfiles}
          />
        )}
        {activeTab === 'templates' && (
          <TemplateManager />
        )}
      </main>
    </div>
  );
}

export default App;
