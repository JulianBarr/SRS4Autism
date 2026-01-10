import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useLanguage } from '../../i18n/LanguageContext';
import KeyboardTutorModal from '../KeyboardTutorModal';
import PinyinTypingModal from '../PinyinTypingModal';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * PinyinTypingManager - Management Dashboard for Pinyin Typing Curriculum
 * 
 * This is a management/admin interface to visualize the curriculum and sync to Anki.
 * NOT a game or review interface - CUMA is a manager for Anki content.
 */
const PinyinTypingManager = ({ profile, onClose }) => {
  const { language } = useLanguage();
  const [courseData, setCourseData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState(null);
  const [expandedLessons, setExpandedLessons] = useState(new Set());
  const [showTutorModal, setShowTutorModal] = useState(false);
  const [showGameModal, setShowGameModal] = useState(false);
  const [selectedLessonId, setSelectedLessonId] = useState(null);

  useEffect(() => {
    loadCourseData();
  }, []);

  const loadCourseData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await axios.get(`${API_BASE}/api/typing-course`);
      setCourseData(response.data);
    } catch (err) {
      console.error('Error loading course data:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to load course data');
      setCourseData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSyncToAnki = async () => {
    try {
      setSyncing(true);
      setSyncStatus(null);
      
      const response = await axios.post(`${API_BASE}/api/typing-course/sync`, {
        profile_id: profile?.id
      });
      
      setSyncStatus({
        success: true,
        message: response.data.message || 'Successfully synced to Anki',
        details: response.data.details
      });
    } catch (err) {
      console.error('Error syncing to Anki:', err);
      setSyncStatus({
        success: false,
        message: err.response?.data?.detail || err.message || 'Failed to sync to Anki'
      });
    } finally {
      setSyncing(false);
    }
  };

  const toggleLesson = (lessonId) => {
    const newExpanded = new Set(expandedLessons);
    if (newExpanded.has(lessonId)) {
      newExpanded.delete(lessonId);
    } else {
      newExpanded.add(lessonId);
    }
    setExpandedLessons(newExpanded);
  };

  const getTotalWords = () => {
    if (!courseData) return 0;
    return Object.values(courseData).reduce((sum, items) => sum + (items?.length || 0), 0);
  };

  // Helper function to extract filename from HTML string
  const extractFilename = (htmlString) => {
    if (!htmlString) return null;
    
    // Handle image: <img src="filename.png">
    const imgMatch = htmlString.match(/<img\s+src=["']([^"']+)["']/i);
    if (imgMatch) return imgMatch[1];
    
    // Handle audio: [sound:filename.mp3]
    const soundMatch = htmlString.match(/\[sound:([^\]]+)\]/i);
    if (soundMatch) return soundMatch[1];
    
    // If no wrapper, assume it's already a filename
    return htmlString.trim();
  };

  const renderPinyinPrompt = (fullPinyinRaw, targetIndex) => {
    const syllables = fullPinyinRaw.split(/\s+/);
    return syllables.map((syl, idx) => {
      if (idx === targetIndex) {
        return (
          <span key={idx} style={{ 
            backgroundColor: '#fee2e2', 
            padding: '2px 6px', 
            borderRadius: '4px',
            fontWeight: 'bold',
            color: '#dc2626'
          }}>
            [{syl}]
          </span>
        );
      }
      return <span key={idx} style={{ marginRight: '4px' }}>{syl}</span>;
    });
  };

  const checkTutorialCompleted = (lessonId) => {
    return localStorage.getItem(`tutorialCompleted_${lessonId}`) === 'true';
  };

  const handleStartLesson = (lessonId, e) => {
    e.stopPropagation(); // Prevent expanding/collapsing the lesson
    
    setSelectedLessonId(lessonId);
    
    // Check if tutorial is completed
    if (checkTutorialCompleted(lessonId)) {
      // Tutorial already completed, go straight to game
      setShowGameModal(true);
    } else {
      // Tutorial not completed, show tutor first
      setShowTutorModal(true);
    }
  };

  const handleTutorComplete = () => {
    setShowTutorModal(false);
    // Tutorial completed, now show the game
    if (selectedLessonId) {
      setShowGameModal(true);
    }
  };

  const handleGameClose = () => {
    setShowGameModal(false);
    setSelectedLessonId(null);
  };

  const handleTutorClose = () => {
    setShowTutorModal(false);
    setSelectedLessonId(null);
  };

  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <div style={{ fontSize: '18px', color: '#6b7280' }}>
          {language === 'zh' ? '加载中...' : 'Loading curriculum...'}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '40px' }}>
        <div style={{ 
          padding: '20px', 
          backgroundColor: '#fee2e2', 
          borderRadius: '8px',
          border: '1px solid #fecaca',
          marginBottom: '20px'
        }}>
          <h3 style={{ color: '#dc2626', marginTop: 0 }}>
            {language === 'zh' ? '错误' : 'Error'}
          </h3>
          <p style={{ color: '#991b1b' }}>{error}</p>
          <p style={{ fontSize: '14px', color: '#991b1b', marginTop: '10px' }}>
            {language === 'zh' 
              ? '请确保 data/cloze_typing_course.json 文件存在于项目根目录。' 
              : 'Please ensure data/cloze_typing_course.json exists in the project root.'}
          </p>
        </div>
        <button
          onClick={loadCourseData}
          style={{
            padding: '10px 20px',
            backgroundColor: '#3b82f6',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '14px'
          }}
        >
          {language === 'zh' ? '重试' : 'Retry'}
        </button>
      </div>
    );
  }

  if (!courseData || Object.keys(courseData).length === 0) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <div style={{ fontSize: '18px', color: '#6b7280' }}>
          {language === 'zh' ? '课程数据为空' : 'No course data available'}
        </div>
      </div>
    );
  }

  const lessonIds = Object.keys(courseData).sort((a, b) => parseInt(a) - parseInt(b));

  return (
    <>
      {/* Keyboard Tutor Modal */}
      {showTutorModal && selectedLessonId && (
        <KeyboardTutorModal
          lessonId={selectedLessonId}
          onClose={handleTutorClose}
          onComplete={handleTutorComplete}
        />
      )}

      {/* Pinyin Typing Game Modal */}
      {showGameModal && selectedLessonId && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px'
        }}>
          <div style={{
            background: 'white',
            borderRadius: '16px',
            padding: '32px',
            maxWidth: '900px',
            width: '100%',
            maxHeight: '90vh',
            overflowY: 'auto',
            position: 'relative'
          }}>
            <button
              onClick={handleGameClose}
              style={{
                position: 'absolute',
                top: '16px',
                right: '16px',
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                border: 'none',
                backgroundColor: '#f3f4f6',
                color: '#6b7280',
                fontSize: '24px',
                fontWeight: 'bold',
                cursor: 'pointer',
                zIndex: 1001
              }}
            >
              ×
            </button>
            <PinyinTypingModal
              lessonId={selectedLessonId}
              onClose={handleGameClose}
            />
          </div>
        </div>
      )}

      <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
        {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ 
          fontSize: '28px', 
          fontWeight: 'bold', 
          color: '#1f2937',
          marginBottom: '8px'
        }}>
          {language === 'zh' ? '拼音打字课程管理' : 'Pinyin Typing Curriculum Manager'}
        </h2>
        <p style={{ color: '#6b7280', fontSize: '14px' }}>
          {language === 'zh' 
            ? '查看和同步拼音打字课程到 Anki。这不是游戏界面 - 请使用 Anki 客户端进行复习。' 
            : 'View and sync Pinyin Typing curriculum to Anki. This is not a game interface - use Anki client for reviews.'}
        </p>
        <div style={{ 
          marginTop: '12px', 
          padding: '12px', 
          backgroundColor: '#f0f9ff', 
          borderRadius: '8px',
          border: '1px solid #bae6fd'
        }}>
          <strong style={{ color: '#0369a1' }}>
            {language === 'zh' ? '总计:' : 'Total:'} 
          </strong>
          <span style={{ color: '#0369a1', marginLeft: '8px' }}>
            {lessonIds.length} {language === 'zh' ? '课程' : 'lessons'} • {getTotalWords()} {language === 'zh' ? '个词' : 'words'}
          </span>
        </div>
      </div>

      {/* Sync Status */}
      {syncStatus && (
        <div style={{ 
          padding: '16px', 
          backgroundColor: syncStatus.success ? '#d1fae5' : '#fee2e2',
          borderRadius: '8px',
          border: `1px solid ${syncStatus.success ? '#a7f3d0' : '#fecaca'}`,
          marginBottom: '20px'
        }}>
          <div style={{ 
            color: syncStatus.success ? '#065f46' : '#991b1b',
            fontWeight: '600'
          }}>
            {syncStatus.message}
          </div>
          {syncStatus.details && (
            <div style={{ 
              marginTop: '8px', 
              fontSize: '14px',
              color: syncStatus.success ? '#047857' : '#991b1b'
            }}>
              {JSON.stringify(syncStatus.details, null, 2)}
            </div>
          )}
        </div>
      )}

      {/* Sync Button */}
      <div style={{ marginBottom: '24px' }}>
        <button
          onClick={handleSyncToAnki}
          disabled={syncing || !courseData}
          style={{
            padding: '12px 24px',
            fontSize: '16px',
            fontWeight: 'bold',
            backgroundColor: syncing ? '#9ca3af' : '#10b981',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: syncing ? 'not-allowed' : 'pointer',
            transition: 'background-color 0.2s'
          }}
          onMouseEnter={(e) => {
            if (!syncing) {
              e.target.style.backgroundColor = '#059669';
            }
          }}
          onMouseLeave={(e) => {
            if (!syncing) {
              e.target.style.backgroundColor = '#10b981';
            }
          }}
        >
          {syncing 
            ? (language === 'zh' ? '同步中...' : 'Syncing...')
            : (language === 'zh' ? '📤 同步到 Anki' : '📤 Sync to Anki')
          }
        </button>
      </div>

      {/* Curriculum List */}
      <div style={{ 
        backgroundColor: 'white',
        borderRadius: '12px',
        border: '1px solid #e5e7eb',
        overflow: 'hidden'
      }}>
        {lessonIds.map((lessonId) => {
          const items = courseData[lessonId] || [];
          const isExpanded = expandedLessons.has(lessonId);
          
          return (
            <div key={lessonId} style={{ borderBottom: '1px solid #e5e7eb' }}>
              {/* Lesson Header */}
              <div
                onClick={() => toggleLesson(lessonId)}
                style={{
                  padding: '16px 20px',
                  backgroundColor: isExpanded ? '#f9fafb' : 'white',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  transition: 'background-color 0.2s'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#f9fafb';
                }}
                onMouseLeave={(e) => {
                  if (!isExpanded) {
                    e.currentTarget.style.backgroundColor = 'white';
                  }
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1 }}>
                  <span style={{ fontSize: '20px' }}>
                    {isExpanded ? '▼' : '▶'}
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#1f2937' }}>
                      {language === 'zh' ? '课程' : 'Lesson'} {lessonId}
                    </div>
                    <div style={{ fontSize: '14px', color: '#6b7280', marginTop: '2px' }}>
                      {items.length} {language === 'zh' ? '个词' : 'words'}
                      {checkTutorialCompleted(lessonId) && (
                        <span style={{ marginLeft: '12px', color: '#10b981', fontSize: '12px' }}>
                          ✓ {language === 'zh' ? '指法已通过' : 'Tutorial Passed'}
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={(e) => handleStartLesson(lessonId, e)}
                    style={{
                      padding: '10px 20px',
                      fontSize: '14px',
                      fontWeight: 'bold',
                      backgroundColor: '#8b5cf6',
                      color: 'white',
                      border: 'none',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      whiteSpace: 'nowrap'
                    }}
                    onMouseEnter={(e) => {
                      e.target.style.backgroundColor = '#7c3aed';
                      e.target.style.transform = 'translateY(-2px)';
                    }}
                    onMouseLeave={(e) => {
                      e.target.style.backgroundColor = '#8b5cf6';
                      e.target.style.transform = 'translateY(0)';
                    }}
                  >
                    {language === 'zh' ? '🎮 开始游戏' : '🎮 Start Lesson'}
                  </button>
                </div>
              </div>

              {/* Lesson Content */}
              {isExpanded && (
                <div style={{ padding: '20px', backgroundColor: '#f9fafb' }}>
                  <table style={{ 
                    width: '100%', 
                    borderCollapse: 'collapse',
                    fontSize: '14px'
                  }}>
                    <thead>
                      <tr style={{ 
                        borderBottom: '2px solid #e5e7eb',
                        textAlign: 'left'
                      }}>
                        <th style={{ padding: '8px', color: '#6b7280', fontWeight: '600' }}>
                          {language === 'zh' ? '汉字' : 'Hanzi'}
                        </th>
                        <th style={{ padding: '8px', color: '#6b7280', fontWeight: '600' }}>
                          {language === 'zh' ? '拼音提示' : 'Pinyin Prompt'}
                        </th>
                        <th style={{ padding: '8px', color: '#6b7280', fontWeight: '600' }}>
                          {language === 'zh' ? '目标音节' : 'Target Syllable'}
                        </th>
                        <th style={{ padding: '8px', color: '#6b7280', fontWeight: '600' }}>
                          {language === 'zh' ? '位置' : 'Position'}
                        </th>
                        <th style={{ padding: '8px', color: '#6b7280', fontWeight: '600' }}>
                          {language === 'zh' ? '媒体' : 'Media'}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item, idx) => (
                        <tr 
                          key={idx}
                          style={{ 
                            borderBottom: '1px solid #f3f4f6',
                            backgroundColor: idx % 2 === 0 ? 'white' : '#fafafa'
                          }}
                        >
                          <td style={{ padding: '12px 8px', fontWeight: '600', color: '#1f2937' }}>
                            {item.hanzi || '-'}
                          </td>
                          <td style={{ padding: '12px 8px', fontFamily: 'monospace' }}>
                            {renderPinyinPrompt(item.full_pinyin_raw || '', item.target_index || 0)}
                          </td>
                          <td style={{ padding: '12px 8px', color: '#059669', fontWeight: '600' }}>
                            {item.target_syllable || '-'}
                          </td>
                          <td style={{ padding: '12px 8px', color: '#6b7280' }}>
                            {item.target_index !== undefined ? item.target_index : '-'}
                          </td>
                          <td style={{ padding: '12px 8px', fontSize: '12px', color: '#6b7280' }}>
                            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                              {(() => {
                                const audioFile = extractFilename(item.audio);
                                const imageFile = extractFilename(item.image);
                                return (
                                  <>
                                    {audioFile && (
                                      <audio
                                        controls
                                        style={{ height: '24px', width: '150px' }}
                                        src={`${API_BASE}/media/audio/${audioFile}`}
                                        onError={(e) => {
                                          console.warn('Audio load failed:', audioFile);
                                          e.target.style.display = 'none';
                                        }}
                                      >
                                        {language === 'zh' ? '您的浏览器不支持音频' : 'Audio not supported'}
                                      </audio>
                                    )}
                                    {imageFile && (
                                      <img
                                        src={`${API_BASE}/media/${imageFile}`}
                                        alt={item.hanzi || 'Word image'}
                                        style={{
                                          maxWidth: '60px',
                                          maxHeight: '60px',
                                          borderRadius: '4px',
                                          objectFit: 'cover'
                                        }}
                                        onError={(e) => {
                                          console.warn('Image load failed:', imageFile);
                                          e.target.style.display = 'none';
                                        }}
                                      />
                                    )}
                                    {!audioFile && !imageFile && '-'}
                                  </>
                                );
                              })()}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
    </>
  );
};

export default PinyinTypingManager;

