import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ChatAssistant from './components/ChatAssistant';
import CardCuration from './components/CardCuration';
import ChildProfileSettings from './components/ChildProfileSettings';
import LanguageContentManager from './components/LanguageContentManager';
import TemplateManager from './components/TemplateManager';
import ContentCategoryNav from './components/ContentCategoryNav';
import MariosWorld from './components/MariosWorld';
import ChineseWordRecognition from './components/ChineseWordRecognition';
import EnglishWordRecognition from './components/EnglishWordRecognition';
import PinyinLearning from './components/PinyinLearning';
import { useLanguage } from './i18n/LanguageContext';
import './App.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const { language, toggleLanguage, t } = useLanguage();
  const [activeTab, setActiveTab] = useState('main');
  const [activeCategory, setActiveCategory] = useState('language'); // Content category
  const [activeContentView, setActiveContentView] = useState(null); // Track specific content view (e.g., 'pinyin-learning')
  const [showPinyinModal, setShowPinyinModal] = useState(false); // Modal state for Pinyin Learning
  const [cognitionLanguage, setCognitionLanguage] = useState(null); // 'zh' or 'en' for Cognition Cove
  const [cognitionContentType, setCognitionContentType] = useState(null); // Content type based on language
  const [profiles, setProfiles] = useState([]);
  const [currentProfile, setCurrentProfile] = useState(null);
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [logoError, setLogoError] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  // Scroll to top when switching to workbench tab
  useEffect(() => {
    if (activeTab === 'main') {
      window.scrollTo({ top: 0, behavior: 'instant' });
    }
  }, [activeTab]);

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
              <h1 data-lang={language}>{t('appTitle')}</h1>
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
                style={{
                  background: 'transparent',
                  border: 'none',
                  fontSize: '24px',
                  cursor: 'pointer',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  transition: 'background 0.2s'
                }}
                onMouseEnter={(e) => e.target.style.background = '#f0f0f0'}
                onMouseLeave={(e) => e.target.style.background = 'transparent'}
              >
                {language === 'en' ? '🇨🇳' : '🇺🇸'}
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
              className={activeTab === 'mariosWorld' ? 'active' : ''}
              onClick={() => setActiveTab('mariosWorld')}
            >
              {t('mariosWorld') || (language === 'en' ? "Mario's World" : '马力世界')}
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

        {activeTab === 'mariosWorld' && (
          <MariosWorld 
            profile={currentProfile}
            onNavigateToContent={(action) => {
              // Navigate to content management tab
              setActiveTab('content');
              setActiveCategory('language');
              // Store action to trigger after navigation
              if (action === 'word-recognition-zh') {
                // Use setTimeout to ensure tab switch completes first
                setTimeout(() => {
                  window.dispatchEvent(new CustomEvent('openWordRecognition', { detail: { language: 'zh' } }));
                }, 100);
              } else if (action === 'word-recognition-en') {
                setTimeout(() => {
                  window.dispatchEvent(new CustomEvent('openWordRecognition', { detail: { language: 'en' } }));
                }, 100);
              } else if (action === 'pinyin-learning') {
                // Show pinyin learning modal - set to Chinese and Pinyin directly
                setCognitionLanguage('zh');
                setCognitionContentType('pinyin');
                setShowPinyinModal(true);
              }
            }}
          />
        )}

        {/* Cognition Cove Modal */}
        {showPinyinModal && (
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '20px'
          }} onClick={() => {
            setShowPinyinModal(false);
            setCognitionLanguage(null);
            setCognitionContentType(null);
          }}>
            <div style={{
              backgroundColor: 'white',
              borderRadius: '24px',
              maxWidth: '1200px',
              width: '100%',
              maxHeight: '90vh',
              overflow: 'auto',
              boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
              position: 'relative'
            }} onClick={(e) => e.stopPropagation()}>
              {/* Header */}
              <div style={{
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                padding: '32px',
                borderRadius: '24px 24px 0 0',
                position: 'relative',
                overflow: 'hidden'
              }}>
                <div style={{
                  position: 'absolute',
                  top: '-50px',
                  right: '-50px',
                  width: '200px',
                  height: '200px',
                  backgroundColor: 'rgba(255,255,255,0.1)',
                  borderRadius: '50%',
                  filter: 'blur(40px)'
                }}></div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', position: 'relative', zIndex: 10 }}>
                  <div>
                    <div style={{ fontSize: '12px', fontWeight: 'bold', color: 'rgba(255,255,255,0.8)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                      Cognition Cove
                    </div>
                    <h2 style={{ fontSize: '36px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
                      {language === 'zh' ? '基础认知' : 'Basic Cognition'}
                    </h2>
                    <p style={{ fontSize: '16px', color: 'rgba(255,255,255,0.9)', fontWeight: '500' }}>
                      {language === 'zh' 
                        ? '基础认知：命名、颜色、数字' 
                        : 'Foundations: Naming, Colors, Numbers'}
                    </p>
                  </div>
                </div>
                <button 
                  onClick={() => {
                    setShowPinyinModal(false);
                    setCognitionLanguage(null);
                    setCognitionContentType(null);
                  }}
                  style={{
                    position: 'absolute',
                    top: '16px',
                    right: '16px',
                    backgroundColor: 'rgba(255,255,255,0.3)',
                    border: 'none',
                    borderRadius: '50%',
                    width: '40px',
                    height: '40px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '24px',
                    color: 'white',
                    zIndex: 20
                  }}
                >
                  ×
                </button>
              </div>

              {/* Content */}
              <div style={{ padding: '32px', backgroundColor: '#f9fafb' }}>
                {!cognitionLanguage ? (
                  /* Level 1: Language Selection */
                  <div>
                    <h3 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '20px', color: '#1f2937' }}>
                      {language === 'zh' ? '选择语言' : 'Select Language'}
                    </h3>
                    <div style={{ display: 'flex', gap: '20px', marginTop: '30px' }}>
                      <button
                        onClick={() => setCognitionLanguage('zh')}
                        style={{
                          flex: 1,
                          padding: '24px',
                          fontSize: '20px',
                          fontWeight: 'bold',
                          border: '2px solid #10b981',
                          borderRadius: '12px',
                          backgroundColor: '#f0fdf4',
                          color: '#10b981',
                          cursor: 'pointer',
                          transition: 'all 0.2s'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = '#dcfce7';
                          e.currentTarget.style.transform = 'scale(1.02)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = '#f0fdf4';
                          e.currentTarget.style.transform = 'scale(1)';
                        }}
                      >
                        {language === 'zh' ? '中文' : 'Chinese'}
                      </button>
                      <button
                        onClick={() => setCognitionLanguage('en')}
                        style={{
                          flex: 1,
                          padding: '24px',
                          fontSize: '20px',
                          fontWeight: 'bold',
                          border: '2px solid #10b981',
                          borderRadius: '12px',
                          backgroundColor: '#f0fdf4',
                          color: '#10b981',
                          cursor: 'pointer',
                          transition: 'all 0.2s'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = '#dcfce7';
                          e.currentTarget.style.transform = 'scale(1.02)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = '#f0fdf4';
                          e.currentTarget.style.transform = 'scale(1)';
                        }}
                      >
                        {language === 'zh' ? '英文' : 'English'}
                      </button>
                    </div>
                  </div>
                ) : !cognitionContentType ? (
                  /* Level 2: Content Type Selection */
                  <div>
                    <button
                      onClick={() => setCognitionLanguage(null)}
                      style={{
                        marginBottom: '20px',
                        padding: '8px 16px',
                        fontSize: '14px',
                        border: '1px solid #ddd',
                        borderRadius: '6px',
                        backgroundColor: 'white',
                        cursor: 'pointer',
                        color: '#666'
                      }}
                    >
                      ← {language === 'zh' ? '返回' : 'Back'}
                    </button>
                    <h3 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '20px', color: '#1f2937' }}>
                      {language === 'zh' ? '选择内容类型' : 'Select Content Type'}
                    </h3>
                    <div style={{ display: 'flex', gap: '20px', marginTop: '30px', flexWrap: 'wrap' }}>
                      {cognitionLanguage === 'zh' ? (
                        <>
                          <button
                            onClick={() => setCognitionContentType('naming')}
                            style={{
                              flex: '1 1 45%',
                              minWidth: '200px',
                              padding: '24px',
                              fontSize: '20px',
                              fontWeight: 'bold',
                              border: '2px solid #10b981',
                              borderRadius: '12px',
                              backgroundColor: '#f0fdf4',
                              color: '#10b981',
                              cursor: 'pointer',
                              transition: 'all 0.2s'
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = '#dcfce7';
                              e.currentTarget.style.transform = 'scale(1.02)';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = '#f0fdf4';
                              e.currentTarget.style.transform = 'scale(1)';
                            }}
                          >
                            基础命名
                          </button>
                          <button
                            onClick={() => setCognitionContentType('pinyin')}
                            style={{
                              flex: '1 1 45%',
                              minWidth: '200px',
                              padding: '24px',
                              fontSize: '20px',
                              fontWeight: 'bold',
                              border: '2px solid #10b981',
                              borderRadius: '12px',
                              backgroundColor: '#f0fdf4',
                              color: '#10b981',
                              cursor: 'pointer',
                              transition: 'all 0.2s'
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = '#dcfce7';
                              e.currentTarget.style.transform = 'scale(1.02)';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = '#f0fdf4';
                              e.currentTarget.style.transform = 'scale(1)';
                            }}
                          >
                            基础拼音
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={() => setCognitionContentType('naming')}
                            style={{
                              flex: '1 1 45%',
                              minWidth: '200px',
                              padding: '24px',
                              fontSize: '20px',
                              fontWeight: 'bold',
                              border: '2px solid #10b981',
                              borderRadius: '12px',
                              backgroundColor: '#f0fdf4',
                              color: '#10b981',
                              cursor: 'pointer',
                              transition: 'all 0.2s'
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = '#dcfce7';
                              e.currentTarget.style.transform = 'scale(1.02)';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = '#f0fdf4';
                              e.currentTarget.style.transform = 'scale(1)';
                            }}
                          >
                            Naming
                          </button>
                          <button
                            onClick={() => setCognitionContentType('phonics')}
                            style={{
                              flex: '1 1 45%',
                              minWidth: '200px',
                              padding: '24px',
                              fontSize: '20px',
                              fontWeight: 'bold',
                              border: '2px solid #10b981',
                              borderRadius: '12px',
                              backgroundColor: '#f0fdf4',
                              color: '#10b981',
                              cursor: 'pointer',
                              transition: 'all 0.2s'
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor = '#dcfce7';
                              e.currentTarget.style.transform = 'scale(1.02)';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor = '#f0fdf4';
                              e.currentTarget.style.transform = 'scale(1)';
                            }}
                          >
                            Phonics
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ) : (
                  /* Level 3: Actual Content Component */
                  <div>
                    <button
                      onClick={() => {
                        setCognitionContentType(null);
                      }}
                      style={{
                        marginBottom: '20px',
                        padding: '8px 16px',
                        fontSize: '14px',
                        border: '1px solid #ddd',
                        borderRadius: '6px',
                        backgroundColor: 'white',
                        cursor: 'pointer',
                        color: '#666'
                      }}
                    >
                      ← {language === 'zh' ? '返回' : 'Back'}
                    </button>
                    {cognitionLanguage === 'zh' && cognitionContentType === 'naming' && (
                      <ChineseWordRecognition 
                        profile={currentProfile} 
                        onProfileUpdate={loadData}
                      />
                    )}
                    {cognitionLanguage === 'zh' && cognitionContentType === 'pinyin' && (
                      <PinyinLearning 
                        profile={currentProfile} 
                        onProfileUpdate={loadData}
                      />
                    )}
                    {cognitionLanguage === 'en' && cognitionContentType === 'naming' && (
                      <EnglishWordRecognition 
                        profile={currentProfile} 
                        onProfileUpdate={loadData}
                      />
                    )}
                    {cognitionLanguage === 'en' && cognitionContentType === 'phonics' && (
                      <div style={{ padding: '40px', textAlign: 'center' }}>
                        <h3 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '20px', color: '#1f2937' }}>
                          Phonics Learning
                        </h3>
                        <p style={{ color: '#666', fontSize: '16px' }}>
                          Phonics learning feature coming soon...
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
