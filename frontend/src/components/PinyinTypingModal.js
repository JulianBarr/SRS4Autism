import React, { useState, useEffect, useRef } from 'react';
import { useLanguage } from '../i18n/LanguageContext';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * PinyinTypingModal - Level 2: Pinyin Typing game for Logic City
 * 
 * Accepts a lessonId (e.g., "1", "2") and loads words from balanced_typing_course.json
 * Displays image, masked pinyin prompt, and audio for typing practice.
 */
const PinyinTypingModal = ({ lessonId, onClose }) => {
  const { language } = useLanguage();
  const [lessonData, setLessonData] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [userInput, setUserInput] = useState('');
  const [feedbackStatus, setFeedbackStatus] = useState(null); // 'correct', 'wrong', null
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);
  const audioRef = useRef(null);
  const containerRef = useRef(null);

  // Load lesson data
  useEffect(() => {
    const loadLessonData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        // Try API endpoint first
        try {
          const response = await fetch(`${API_BASE}/api/typing-course/lesson/${lessonId}`);
          if (response.ok) {
            const data = await response.json();
            setLessonData(data);
            setLoading(false);
            return;
          }
        } catch (apiErr) {
          console.warn('API endpoint not available, trying local file:', apiErr);
        }
        
        // Fallback to local JSON file in public directory
        const response = await fetch('/cloze_typing_course.json');
        if (!response.ok) {
          throw new Error('Failed to fetch course data');
        }
        const jsonData = await response.json();
        const lessonItems = jsonData[lessonId] || [];
        setLessonData(lessonItems);
      } catch (err) {
        console.error('Error loading lesson data:', err);
        setError('Failed to load lesson data. Please ensure cloze_typing_course.json is in the public directory.');
      } finally {
        setLoading(false);
      }
    };

    if (lessonId) {
      loadLessonData();
    }
  }, [lessonId]);

  // Auto-focus input when card changes
  useEffect(() => {
    if (inputRef.current && !loading && lessonData.length > 0) {
      inputRef.current.focus();
    }
  }, [currentIndex, loading, lessonData.length]);

  // Auto-play audio when card changes
  useEffect(() => {
    if (audioRef.current && lessonData.length > 0 && currentIndex < lessonData.length) {
      const currentCard = lessonData[currentIndex];
      if (currentCard.audio) {
        // Reset and play audio
        audioRef.current.load();
        audioRef.current.play().catch(err => {
          console.warn('Audio autoplay prevented:', err);
        });
      }
    }
  }, [currentIndex, lessonData]);

  // Reset feedback after animation
  useEffect(() => {
    if (feedbackStatus) {
      const timer = setTimeout(() => {
        setFeedbackStatus(null);
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [feedbackStatus]);

  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <div style={{ fontSize: '18px', color: '#6b7280' }}>
          {language === 'zh' ? '加载中...' : 'Loading...'}
        </div>
      </div>
    );
  }

  if (error || lessonData.length === 0) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <div style={{ fontSize: '18px', color: '#ef4444', marginBottom: '20px' }}>
          {error || (language === 'zh' ? '课程数据为空' : 'No lesson data available')}
        </div>
        <button
          onClick={onClose}
          style={{
            padding: '10px 20px',
            backgroundColor: '#8b5cf6',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '14px'
          }}
        >
          {language === 'zh' ? '关闭' : 'Close'}
        </button>
      </div>
    );
  }

  const currentCard = lessonData[currentIndex];
  const syllables = currentCard.full_pinyin_raw.split(/\s+/);
  const targetIndex = currentCard.target_index;

  // Parse pinyin to render masked version
  const renderPinyinPrompt = () => {
    return syllables.map((syllable, index) => {
      if (index === targetIndex) {
        return (
          <span key={index} style={{ display: 'inline-flex', alignItems: 'center', margin: '0 4px' }}>
            <input
              ref={index === targetIndex ? inputRef : null}
              type="text"
              value={userInput}
              onChange={(e) => {
                setUserInput(e.target.value.toLowerCase());
                setFeedbackStatus(null);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleSubmit();
                }
              }}
              placeholder="____"
              style={{
                fontSize: '32px',
                fontWeight: 'bold',
                textAlign: 'center',
                padding: '8px 16px',
                border: feedbackStatus === 'correct' 
                  ? '3px solid #10b981' 
                  : feedbackStatus === 'wrong' 
                  ? '3px solid #ef4444' 
                  : '3px solid #8b5cf6',
                borderRadius: '8px',
                backgroundColor: feedbackStatus === 'correct' 
                  ? '#d1fae5' 
                  : feedbackStatus === 'wrong' 
                  ? '#fee2e2' 
                  : '#f3f4f6',
                color: '#1f2937',
                minWidth: '120px',
                outline: 'none',
                transition: 'all 0.3s ease',
                animation: feedbackStatus === 'wrong' ? 'shake 0.5s' : 'none'
              }}
            />
          </span>
        );
      } else {
        return (
          <span key={index} style={{ fontSize: '32px', margin: '0 4px', color: '#1f2937' }}>
            {syllable}
          </span>
        );
      }
    });
  };

  const handleSubmit = () => {
    const cleanInput = userInput.trim().toLowerCase();
    const cleanTarget = currentCard.target_syllable.trim().toLowerCase();

    if (cleanInput === cleanTarget) {
      setFeedbackStatus('correct');
      // Play success sound (if available)
      const successAudio = new Audio('/sounds/ding.mp3');
      successAudio.play().catch(() => {});

      // Move to next card after a delay
      setTimeout(() => {
        if (currentIndex < lessonData.length - 1) {
          setCurrentIndex(currentIndex + 1);
          setUserInput('');
        } else {
          // Lesson complete
          alert(language === 'zh' ? '课程完成！' : 'Lesson complete!');
          onClose();
        }
      }, 800);
    } else {
      setFeedbackStatus('wrong');
      // Shake animation handled by CSS
      setTimeout(() => {
        setUserInput('');
      }, 500);
    }
  };

  const progress = ((currentIndex + 1) / lessonData.length) * 100;

  return (
    <div 
      ref={containerRef}
      style={{
        position: 'relative',
        width: '100%',
        maxWidth: '800px',
        margin: '0 auto'
      }}
    >
      {/* Progress Bar */}
      <div style={{
        marginBottom: '24px',
        backgroundColor: '#e5e7eb',
        borderRadius: '8px',
        height: '8px',
        overflow: 'hidden'
      }}>
        <div style={{
          width: `${progress}%`,
          height: '100%',
          backgroundColor: '#8b5cf6',
          transition: 'width 0.3s ease'
        }} />
      </div>

      {/* Progress Text */}
      <div style={{
        textAlign: 'center',
        fontSize: '14px',
        color: '#6b7280',
        marginBottom: '32px'
      }}>
        {currentIndex + 1} / {lessonData.length}
      </div>

      {/* Image */}
      <div style={{
        textAlign: 'center',
        marginBottom: '32px',
        backgroundColor: '#f9fafb',
        borderRadius: '12px',
        padding: '20px',
        minHeight: '200px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        {currentCard.image ? (
          <img
            src={currentCard.image.startsWith('http') 
              ? currentCard.image 
              : `${API_BASE}/media/${currentCard.image}`}
            alt={currentCard.hanzi}
            style={{
              maxWidth: '100%',
              maxHeight: '300px',
              borderRadius: '8px',
              boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
            }}
            onError={(e) => {
              e.target.style.display = 'none';
            }}
          />
        ) : (
          <div style={{ fontSize: '48px', color: '#9ca3af' }}>
            {currentCard.hanzi}
          </div>
        )}
      </div>

      {/* Pinyin Prompt */}
      <div style={{
        textAlign: 'center',
        marginBottom: '32px',
        padding: '32px',
        backgroundColor: 'white',
        borderRadius: '12px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        minHeight: '120px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexWrap: 'wrap'
      }}>
        {renderPinyinPrompt()}
      </div>

      {/* Audio Player */}
      {currentCard.audio && (
        <div style={{
          textAlign: 'center',
          marginBottom: '24px'
        }}>
          <audio
            ref={audioRef}
            controls
            style={{ width: '100%', maxWidth: '400px' }}
          >
            <source 
              src={currentCard.audio.startsWith('http') 
                ? currentCard.audio 
                : `${API_BASE}/media/audio/${currentCard.audio}`} 
              type="audio/mpeg" 
            />
            {language === 'zh' ? '您的浏览器不支持音频播放' : 'Your browser does not support audio playback'}
          </audio>
        </div>
      )}

      {/* Submit Button */}
      <div style={{ textAlign: 'center' }}>
        <button
          onClick={handleSubmit}
          disabled={!userInput.trim()}
          style={{
            padding: '12px 32px',
            fontSize: '16px',
            fontWeight: 'bold',
            backgroundColor: userInput.trim() ? '#8b5cf6' : '#d1d5db',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: userInput.trim() ? 'pointer' : 'not-allowed',
            transition: 'background-color 0.2s'
          }}
          onMouseEnter={(e) => {
            if (userInput.trim()) {
              e.target.style.backgroundColor = '#7c3aed';
            }
          }}
          onMouseLeave={(e) => {
            if (userInput.trim()) {
              e.target.style.backgroundColor = '#8b5cf6';
            }
          }}
        >
          {language === 'zh' ? '提交' : 'Submit'} (Enter)
        </button>
      </div>

      {/* Shake Animation */}
      <style>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          10%, 30%, 50%, 70%, 90% { transform: translateX(-10px); }
          20%, 40%, 60%, 80% { transform: translateX(10px); }
        }
      `}</style>
    </div>
  );
};

export default PinyinTypingModal;

