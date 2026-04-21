import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, useNavigate } from 'react-router-dom';
import ChatAssistant from './components/ChatAssistant';
import CardCuration from './components/CardCuration';
import ChildProfileSettings from './components/ChildProfileSettings';
import LanguageContentManager from './components/LanguageContentManager';
import CognitionContentManager from './components/CognitionContentManager';
import HHHContentManager from './components/HHHContentManager';
import TemplateManager from './components/TemplateManager';
import ContentCategoryNav from './components/ContentCategoryNav';
import MariosWorld from './components/MariosWorld';
import ChineseWordRecognition from './components/ChineseWordRecognition';
import EnglishWordRecognition from './components/EnglishWordRecognition';
import PinyinLearning from './components/PinyinLearning';
import PinyinGapFillAdmin from './components/PinyinGapFillAdmin';
import AdminDashboard from './components/AdminDashboard';
import LogicCityGallery from './components/widgets/LogicCityGallery';
import LogicCityManager from './components/widgets/LogicCityManager';
import PinyinTypingManager from './components/widgets/PinyinTypingManager';
import CharacterRecognition from './components/CharacterRecognition';
import SettingsModal from './components/SettingsModal';
import UserProfile from './components/UserProfile';
import Login from './components/Login';
import ParentDashboard from './components/ParentDashboard';
import ReviewInterventionWorkbench from './components/ReviewInterventionWorkbench';
import TeacherPendingDrafts from './components/TeacherPendingDrafts'; // AI Copilot for Teachers
import GraphTest from './components/GraphTest';
import { useLanguage } from './i18n/LanguageContext';
import businessApi from './utils/api';
import './App.css';

function App() {
  const { language, toggleLanguage, t } = useLanguage();
  const navigate = useNavigate(); // Initialize useNavigate
  
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('access_token'));
  const [currentUser, setCurrentUser] = useState(() => {
    const saved = localStorage.getItem('user_info');
    return saved ? JSON.parse(saved) : null;
  });
  
  // Check if we're on the admin routes
  const isPinyinAdminRoute = window.location.pathname === '/admin/pinyin-gap-fill' || 
                             window.location.pathname.startsWith('/admin/pinyin-gap-fill');
  const isMainAdminRoute = window.location.pathname === '/admin';

  
  // All hooks must be called before any conditional returns
  const [activeTab, setActiveTab] = useState('main');
  const [activeCategory, setActiveCategory] = useState('language'); // Content category
  const [activeContentView, setActiveContentView] = useState(null); // Track specific content view (e.g., 'pinyin-learning')
  const [showPinyinModal, setShowPinyinModal] = useState(false); // Modal state for Pinyin Learning
  const [stealthMode, setStealthMode] = useState(() => typeof localStorage !== 'undefined' && localStorage.getItem('stealth_mode') === 'true');
  /** Ontology feed for quest library: QCQ (default KG) vs HHH (parallel adapter). */
  const [ontologySource, setOntologySource] = useState('QCQ');
  const [cognitionLanguage, setCognitionLanguage] = useState(null); // 'zh' | 'en' for Cognition Cove modal
  const [cognitionContentType, setCognitionContentType] = useState(null); // Content type based on language
  const [cognitionContentView, setCognitionContentView] = useState('quests'); // 'quests' | 'daily-deck'
  const [hhhContentView, setHhhContentView] = useState('library'); // 'library' | 'daily-deck'
  const [showLogicCityModal, setShowLogicCityModal] = useState(false); // Modal state for Logic City
  const [logicCityContentType, setLogicCityContentType] = useState(null); // Content type for Logic City ('vocab-advanced', etc.)
  const [profiles, setProfiles] = useState([]);
  const [currentProfile, setCurrentProfile] = useState(null);
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [logoError, setLogoError] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      loadData();
    }
  }, [isAuthenticated]);

  // Effect for "Security Route Ejection"
  useEffect(() => {
    if (stealthMode && activeCategory === 'hhh') {
      setActiveCategory('cognition'); // Redirect to default cognition page
      setOntologySource('QCQ'); // Reset ontology source
      // Optionally, show a subtle notification to the user about the redirect
      // For example, using a toast notification library
    }
  }, [stealthMode, activeCategory, navigate]); // Add navigate to dependency array


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
      const isParent = String(currentUser?.role || '').toLowerCase() === 'parent';
      
      const profilesRes = await businessApi.get('/profiles').catch(e => {
        console.error('Error loading profiles:', e);
        return { data: [] };
      });
      setProfiles(profilesRes.data);
      
      if (!isParent) {
        const cardsRes = await businessApi.get('/cards').catch(e => {
          console.error('Error loading cards:', e);
          return { data: [] };
        });
        setCards(cardsRes.data);
      }
    } catch (error) {
      console.error('Error in loadData:', error);
    } finally {
      setLoading(false);
    }
  };

  /** Lightweight profile update for autosave - no loading overlay, no refetch. */
  const handleProfileUpdate = (updatedProfile) => {
    if (updatedProfile) {
      setProfiles(prev => prev.map(p =>
        (p.name === updatedProfile.name || p.id === updatedProfile.id) ? updatedProfile : p
      ));
      setCurrentProfile(prev =>
        prev && (prev.name === updatedProfile.name || prev.id === updatedProfile.id)
          ? updatedProfile
          : prev
      );
    } else {
      loadData();
    }
  };

  /** Cards-only refresh for curation panel. Does not trigger full loading overlay. */
  const loadCardsOnly = async () => {
    try {
      const cardsRes = await businessApi.get('/cards');
      setCards(cardsRes.data);
    } catch (error) {
      console.error('Error loading cards:', error);
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
      await businessApi.put(`/cards/${cardId}/approve`);
      setCards(prev => prev.map(card => 
        card.id === cardId ? { ...card, status: 'approved' } : card
      ));
    } catch (error) {
      console.error('Error approving card:', error);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_info');
    setIsAuthenticated(false);
    setCurrentUser(null);
  };

  // If admin route, render admin interface (after all hooks)
  if (isPinyinAdminRoute) {
    if (!isAuthenticated) {
      return <Login onLoginSuccess={(token, user) => {
        setIsAuthenticated(true);
        if (user) setCurrentUser(user);
      }} />;
    }
    if (!currentUser?.role?.toUpperCase()?.includes('ADMIN')) {
      return (
        <div className="container" style={{ padding: '2rem', textAlign: 'center' }}>
          <h2>Access Denied</h2>
          <p>You need administrator privileges to access this page.</p>
        </div>
      );
    }
    return <PinyinGapFillAdmin />;
  }
  
  if (isMainAdminRoute) {
    if (!isAuthenticated) {
      return <Login onLoginSuccess={(token, user) => {
        setIsAuthenticated(true);
        if (user) setCurrentUser(user);
      }} />;
    }
    if (!currentUser?.role?.toUpperCase()?.includes('ADMIN')) {
      return (
        <div className="container" style={{ padding: '2rem', textAlign: 'center' }}>
          <h2>Access Denied</h2>
          <p>You need administrator privileges to access this page.</p>
        </div>
      );
    }
    return <AdminDashboard />;
  }

  // Handle authentication logic here
  const handleLoginSuccess = (token, user) => {
    setIsAuthenticated(true);
    if (user) setCurrentUser(user);
    // Login component now handles navigation based on role, so no need to navigate here
  };

  if (!isAuthenticated) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  const isParent = String(currentUser?.role || '').toLowerCase() === 'parent';

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
              <h1 data-lang={language}>
                {language === 'zh' ? (
                  <img 
                    src="/star_lingxi.png" 
                    alt="好奇马力" 
                    style={{ height: '43.2px', marginTop: '4px' }} 
                  />
                ) : (
                  t('appTitle')
                )}
              </h1>
            </div>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px', marginLeft: 'auto' }}>
              {/* Profile Selector - always visible */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '1.2em' }}>🧒</span>
                {isParent ? (
                  <span style={{ padding: '5px', fontWeight: 'bold' }}>
                    {currentProfile ? currentProfile.name : '（无儿童）'}
                  </span>
                ) : (
                  <select 
                    value={currentProfile ? currentProfile.id : ''}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (!val) return;
                      const selectedLocal = profiles.find(p => p.id === val);
                      if (selectedLocal) {
                        setCurrentProfile(selectedLocal);
                      }
                    }}
                    style={{ padding: '5px', borderRadius: '4px', border: '1px solid #ccc', minWidth: '100px' }}
                  >
                    <option value="">{profiles.length === 0 ? '（无儿童）' : '选择儿童'}</option>
                    {profiles.map(p => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                )}
              </div>

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
              
              {currentUser && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', marginRight: '8px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#555' }}>
                    {currentUser.role?.toUpperCase()}
                  </span>
                  <span style={{ fontSize: '10px', color: '#888' }}>
                    {currentUser.email}
                  </span>
                </div>
              )}

              <button 
                onClick={handleLogout}
                title="Logout"
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
                🚪
              </button>
              
              <button 
                onClick={() => setActiveTab('userProfile')}
                title={language === 'en' ? 'Profile' : '个人设置'}
                style={{
                  background: 'transparent',
                  border: 'none',
                  fontSize: '20px',
                  cursor: 'pointer',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  transition: 'background 0.2s',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
                onMouseEnter={(e) => e.target.style.background = '#f0f0f0'}
                onMouseLeave={(e) => e.target.style.background = 'transparent'}
              >
                👤
              </button>

              <button 
                onClick={() => setShowSettingsModal(true)}
                title={language === 'en' ? 'Settings' : '设置'}
                style={{
                  background: 'transparent',
                  border: 'none',
                  fontSize: '20px',
                  cursor: 'pointer',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  transition: 'background 0.2s',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
                onMouseEnter={(e) => e.target.style.background = '#f0f0f0'}
                onMouseLeave={(e) => e.target.style.background = 'transparent'}
              >
                ⚙️
              </button>
            </div>
          </div>
          <nav className="tab-nav">
            {isParent ? (
              <button 
                className={activeTab !== 'userProfile' ? 'active' : ''}
                onClick={() => setActiveTab('main')}
              >
                {language === 'en' ? 'Daily Tasks' : '今日任务'}
              </button>
            ) : (
              <>
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
                {currentUser?.role?.toUpperCase()?.includes('ADMIN') && (
                  <button 
                    className={activeTab === 'admin' ? 'active' : ''}
                    onClick={() => setActiveTab('admin')}
                  >
                    控制台
                  </button>
                )}
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="container">
        {isParent ? (
          activeTab === 'userProfile' ? (
            <UserProfile 
              currentUser={currentUser}
              onUserUpdate={setCurrentUser}
            />
          ) : (
            <ParentDashboard 
              currentUser={currentUser} 
              currentProfile={currentProfile}
            />
          )
        ) : (
          <>
            {activeTab === 'main' && (
              <div className="flex flex-col space-y-4">
                <TeacherPendingDrafts />
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
                      onRefresh={loadCardsOnly}
                    />
                  </div>
                </div>
              </div>
            )}

        {activeTab === 'content' && (
          <div>
            {/* Content Category Navigation */}
            <ContentCategoryNav 
              activeCategory={activeCategory}
              onCategoryChange={({ categoryId }) => {
                setActiveCategory(categoryId);
                if (categoryId === 'cognition') setOntologySource('QCQ');
              }}
              stealthMode={stealthMode}
            />
            
            {/* Category Content */}
            {activeCategory === 'language' && (
               <div style={{ marginTop: '20px', padding: '20px', backgroundColor: '#f5f5f5', borderRadius: '8px' }}>
                  <LanguageContentManager 
                    profile={currentProfile} 
                    onProfileUpdate={handleProfileUpdate}
                  />
               </div>
            )}

            {activeCategory === 'cognition' && (
              <div style={{ marginTop: '20px' }}>
                <div style={{ display: 'flex', gap: '12px', marginBottom: '16px' }}>
                  <button
                    onClick={() => setCognitionContentView('quests')}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '8px',
                      border: 'none',
                      cursor: 'pointer',
                      fontWeight: cognitionContentView === 'quests' ? 600 : 400,
                      background: cognitionContentView === 'quests' ? '#e0e7ff' : '#f3f4f6',
                      color: cognitionContentView === 'quests' ? '#4338ca' : '#6b7280',
                    }}
                  >
                    🧠 任务库
                  </button>
                  <button
                    onClick={() => setCognitionContentView('daily-deck')}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '8px',
                      border: 'none',
                      cursor: 'pointer',
                      fontWeight: cognitionContentView === 'daily-deck' ? 600 : 400,
                      background: cognitionContentView === 'daily-deck' ? '#fef3c7' : '#f3f4f6',
                      color: cognitionContentView === 'daily-deck' ? '#b45309' : '#6b7280',
                    }}
                  >
                    📋 QCQ 每日靶向课表
                  </button>
                </div>
                {cognitionContentView === 'daily-deck' ? (
                  <ReviewInterventionWorkbench
                    dailyDeckProps={{
                      childName: currentProfile?.name || null,
                      childId: currentProfile?.id,
                      scheduleSource: 'qcq',
                    }}
                  />
                ) : (
                  <CognitionContentManager source={ontologySource} />
                )}
              </div>
            )}

            {activeCategory === 'hhh' && (
              <div style={{ marginTop: '20px' }}>
                <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    onClick={() => setHhhContentView('library')}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '8px',
                      border: 'none',
                      cursor: 'pointer',
                      fontWeight: hhhContentView === 'library' ? 600 : 400,
                      background: hhhContentView === 'library' ? '#e0f2fe' : '#f3f4f6',
                      color: hhhContentView === 'library' ? '#0369a1' : '#6b7280',
                    }}
                  >
                    📚 HHH 课程浏览
                  </button>
                  <button
                    type="button"
                    onClick={() => setHhhContentView('daily-deck')}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '8px',
                      border: 'none',
                      cursor: 'pointer',
                      fontWeight: hhhContentView === 'daily-deck' ? 600 : 400,
                      background: hhhContentView === 'daily-deck' ? '#fef3c7' : '#f3f4f6',
                      color: hhhContentView === 'daily-deck' ? '#b45309' : '#6b7280',
                    }}
                  >
                    📋 HHS 每日靶向课表
                  </button>
                </div>
                {hhhContentView === 'daily-deck' ? (
                  <ReviewInterventionWorkbench
                    dailyDeckProps={{
                      childName: currentProfile?.name || null,
                      childId: currentProfile?.id,
                      scheduleSource: 'hhs',
                      showDemoButton: false,
                    }}
                  />
                ) : (
                  <HHHContentManager />
                )}
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

            <div style={{ marginTop: '20px' }}>
              <GraphTest />
            </div>
          </div>
        )}

        {activeTab === 'profiles' && (
          <ChildProfileSettings 
            profiles={profiles}
            onProfilesChange={setProfiles}
            currentUser={currentUser}
          />
        )}
        {activeTab === 'templates' && (
          <TemplateManager />
        )}

        {activeTab === 'admin' && currentUser?.role?.toUpperCase()?.includes('ADMIN') && (
          <AdminDashboard />
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
              } else if (action === 'logic-city') {
                // Navigate to Logic City vocabulary gallery
                setActiveTab('content');
                setActiveCategory('language');
                setActiveContentView('logic-city');
              } else if (action === 'logic-city-vocab-advanced') {
                // Show Logic City modal with Advanced Vocabulary
                setLogicCityContentType('vocab-advanced');
                setShowLogicCityModal(true);
              } else if (action === 'logic-city-character-recognition') {
                // Show Logic City modal with Character Recognition
                setLogicCityContentType('character-recognition');
                setShowLogicCityModal(true);
              } else if (action === 'pinyin-typing-level2') {
                // Show Logic City modal with Pinyin Typing management
                setLogicCityContentType('pinyin-typing');
                setShowLogicCityModal(true);
              }
            }}
          />
        )}

        {/* Logic City Vocabulary View */}
        {activeContentView === 'logic-city' && (
          <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
            <button
              onClick={() => {
                setActiveContentView(null);
                setActiveTab('mariosWorld');
              }}
              style={{
                marginBottom: '16px',
                padding: '8px 16px',
                backgroundColor: '#6b7280',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '500'
              }}
            >
              ← {language === 'zh' ? '返回' : 'Back to Mario\'s World'}
            </button>
            <LogicCityGallery />
          </div>
        )}

        {/* Logic City Modal */}
        {showLogicCityModal && (
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
            setShowLogicCityModal(false);
            setLogicCityContentType(null);
          }}>
            <div style={{
              backgroundColor: 'white',
              borderRadius: '24px',
              maxWidth: '1400px',
              width: '100%',
              maxHeight: '90vh',
              overflow: 'auto',
              boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
              position: 'relative'
            }} onClick={(e) => e.stopPropagation()}>
              {/* Header */}
              <div style={{
                background: 'linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%)',
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
                      Logic City
                    </div>
                    <h2 style={{ fontSize: '36px', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
                      {language === 'zh' ? '逻辑城市' : 'Logic City'}
                    </h2>
                    <p style={{ fontSize: '16px', color: 'rgba(255,255,255,0.9)', fontWeight: '500' }}>
                      {language === 'zh' 
                        ? '结构与逻辑：词汇进阶管理' 
                        : 'Structure & Logic: Advanced Vocabulary Management'}
                    </p>
                  </div>
                </div>
                <button 
                  onClick={() => {
                    setShowLogicCityModal(false);
                    setLogicCityContentType(null);
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
                {logicCityContentType === 'vocab-advanced' ? (
                  <LogicCityManager 
                    profile={currentProfile}
                    onClose={() => {
                      setShowLogicCityModal(false);
                      setLogicCityContentType(null);
                    }}
                  />
                ) : logicCityContentType === 'character-recognition' ? (
                  <CharacterRecognition 
                    profile={currentProfile}
                    onProfileUpdate={() => {
                      // Refresh profile if needed
                    }}
                  />
                ) : logicCityContentType === 'pinyin-typing' ? (
                  <PinyinTypingManager 
                    profile={currentProfile}
                    onClose={() => {
                      setShowLogicCityModal(false);
                      setLogicCityContentType(null);
                    }}
                  />
                ) : (
                  /* Level 1: Content Type Selection */
                  <div>
                    <h3 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '20px', color: '#1f2937' }}>
                      {language === 'zh' ? '选择内容类型' : 'Select Content Type'}
                    </h3>
                    <div style={{ display: 'flex', gap: '20px', marginTop: '30px', flexWrap: 'wrap' }}>
                      <button
                        onClick={() => setLogicCityContentType('vocab-advanced')}
                        style={{
                          flex: '1 1 45%',
                          minWidth: '200px',
                          padding: '24px',
                          fontSize: '20px',
                          fontWeight: 'bold',
                          border: '2px solid #8b5cf6',
                          borderRadius: '12px',
                          backgroundColor: '#f3e8ff',
                          color: '#8b5cf6',
                          cursor: 'pointer',
                          transition: 'all 0.2s'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = '#e9d5ff';
                          e.currentTarget.style.transform = 'scale(1.02)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = '#f3e8ff';
                          e.currentTarget.style.transform = 'scale(1)';
                        }}
                      >
                        {language === 'zh' ? '📚 词汇进阶' : '📚 Advanced Vocabulary'}
                      </button>
                      <button
                        onClick={() => setLogicCityContentType('pinyin-typing')}
                        style={{
                          flex: '1 1 45%',
                          minWidth: '200px',
                          padding: '24px',
                          fontSize: '20px',
                          fontWeight: 'bold',
                          border: '2px solid #10b981',
                          borderRadius: '12px',
                          backgroundColor: '#d1fae5',
                          color: '#059669',
                          cursor: 'pointer',
                          transition: 'all 0.2s'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = '#a7f3d0';
                          e.currentTarget.style.transform = 'scale(1.02)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = '#d1fae5';
                          e.currentTarget.style.transform = 'scale(1)';
                        }}
                      >
                        {language === 'zh' ? '⌨️ 拼音打字学校' : '⌨️ Pinyin Typing School'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
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

        {activeTab === 'userProfile' && !isParent && (
          <UserProfile 
            currentUser={currentUser}
            onUserUpdate={setCurrentUser}
          />
        )}
          </>
        )}
      </main>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
        stealthMode={stealthMode}
        setStealthMode={setStealthMode}
      />
    </div>
  );
}

export default function AppWrapper() {
  return (
    <Router>
      <App />
    </Router>
  );
}
