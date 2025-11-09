import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ChatAssistant from './components/ChatAssistant';
import CardCuration from './components/CardCuration';
import ProfileManager from './components/ProfileManager';
import TemplateManager from './components/TemplateManager';
import { useLanguage } from './i18n/LanguageContext';
import './App.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const { language, toggleLanguage, t } = useLanguage();
  const [activeTab, setActiveTab] = useState('main');
  const [profiles, setProfiles] = useState([]);
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [logoError, setLogoError] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

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

  const handleNewCard = (newCard) => {
    // Refresh cards from backend
    loadData();
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
        <div className="container">
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
            <button 
              className="language-toggle"
              onClick={toggleLanguage}
              title={language === 'en' ? '切换到中文' : 'Switch to English'}
            >
              {language === 'en' ? '中文' : 'English'}
            </button>
          </div>
          <nav className="tab-nav">
            <button 
              className={activeTab === 'main' ? 'active' : ''}
              onClick={() => setActiveTab('main')}
            >
              {t('mainWorkflow')}
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
              Templates
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
        {activeTab === 'profiles' && (
          <ProfileManager 
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

