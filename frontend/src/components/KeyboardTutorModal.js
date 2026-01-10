import React, { useState, useEffect, useRef } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import HandVisual from './HandVisual';
import './KeyboardTutorModal.css';

// Lesson configurations
const TUTORIAL_CONFIG = {
  "1": {
    "title": "Home Row: Index Fingers",
    "newKeys": ["f", "j"],
    "fingerColor": "#3b82f6",
    "fingerName": "Index Finger",
    "drillSequence": "fff jjj fjf jfj",
    "instruction": "Place your Index fingers on F and J"
  },
  "2": {
    "title": "Reaching Up: D & K",
    "newKeys": ["d", "k"],
    "fingerColor": "#10b981",
    "fingerName": "Middle Finger",
    "drillSequence": "ddd kkk dkd kdk",
    "instruction": "Use your Middle fingers to reach D and K"
  }
};

// QWERTY keyboard layout
const KEYBOARD_LAYOUT = [
  ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
  ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'],
  ['z', 'x', 'c', 'v', 'b', 'n', 'm'],
  ['SPACE'] // Spacebar row
];

// Finger mapping: which finger should type which key (format: l-pinky, r-index, etc.)
const FINGER_MAP = {
  // Pinky - Left
  'q': 'l-pinky', 'a': 'l-pinky', 'z': 'l-pinky',
  // Pinky - Right
  'p': 'r-pinky',
  // Ring - Left
  'w': 'l-ring', 's': 'l-ring', 'x': 'l-ring',
  // Ring - Right
  'o': 'r-ring', 'l': 'r-ring',
  // Middle - Left
  'e': 'l-middle', 'd': 'l-middle', 'c': 'l-middle',
  // Middle - Right
  'i': 'r-middle', 'k': 'r-middle',
  // Index - Left
  'r': 'l-index', 'f': 'l-index', 'v': 'l-index', 't': 'l-index', 'g': 'l-index', 'b': 'l-index',
  // Index - Right
  'y': 'r-index', 'h': 'r-index', 'n': 'r-index', 'u': 'r-index', 'j': 'r-index', 'm': 'r-index',
  // Thumb - Right (standard convention for spacebar)
  ' ': 'r-thumb'
};

// Color mapping for fingers
const FINGER_COLORS = {
  'pinky': '#f87171',   // Red/Pink
  'ring': '#fbbf24',    // Yellow/Orange
  'middle': '#10b981',  // Green
  'index': '#3b82f6',   // Blue
  'thumb': '#9ca3af'    // Gray
};

/**
 * KeyboardTutorModal - Finger positioning tutorial before starting typing lessons
 * 
 * Acts as a gatekeeper to ensure users learn proper finger placement before playing.
 */
const KeyboardTutorModal = ({ lessonId, onClose, onComplete }) => {
  const { language } = useLanguage();
  const [config, setConfig] = useState(null);
  const [currentDrillIndex, setCurrentDrillIndex] = useState(0);
  const [isComplete, setIsComplete] = useState(false);
  const [shake, setShake] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeFinger, setActiveFinger] = useState(null);
  const keyboardRef = useRef(null);
  const inputRef = useRef(null);

  // Load config
  useEffect(() => {
    const loadConfig = async () => {
      try {
        // Try to load from public directory first
        const response = await fetch('/typing_tutorial_config.json');
        if (response.ok) {
          const data = await response.json();
          setConfig(data[lessonId] || null);
        } else {
          // Fallback to embedded config
          setConfig(TUTORIAL_CONFIG[lessonId] || null);
        }
      } catch (err) {
        console.warn('Failed to load config, using embedded:', err);
        setConfig(TUTORIAL_CONFIG[lessonId] || null);
      } finally {
        setLoading(false);
      }
    };

    if (lessonId) {
      loadConfig();
    }
  }, [lessonId]);

  // Focus management: Auto-focus the hidden input on mount and when config changes
  useEffect(() => {
    if (!config || isComplete || loading) return;

    // Focus the hidden input when component is ready
    const focusInput = () => {
      if (inputRef.current) {
        inputRef.current.focus();
      }
    };

    // Small delay to ensure DOM is ready
    const timer = setTimeout(focusInput, 100);
    return () => clearTimeout(timer);
  }, [config, isComplete, loading]);

  // Handle input from hidden input trap
  const handleInputChange = (e) => {
    if (!config || isComplete) return;

    const inputValue = e.target.value;
    if (!inputValue || inputValue.length === 0) return;

    // Get the last character typed
    const lastChar = inputValue.slice(-1);
    // Normalize: lowercase for letters, keep space as-is
    const pressedKey = lastChar === ' ' ? ' ' : lastChar.toLowerCase();

    // Handle letter keys (a-z) and space
    if (!/[a-z ]/.test(pressedKey)) {
      // Clear the input for non-letter, non-space keys
      e.target.value = '';
      return;
    }

    const targetKey = config.drillSequence[currentDrillIndex];
    const normalizedTargetKey = targetKey === ' ' ? ' ' : targetKey.toLowerCase();
    
    if (pressedKey === normalizedTargetKey) {
      // Correct key pressed
      playClickSound();
      setCurrentDrillIndex(prev => {
        const next = prev + 1;
        if (next >= config.drillSequence.length) {
          setIsComplete(true);
        }
        return next;
      });
    } else {
      // Wrong key pressed
      setShake(true);
      playErrorSound();
      setTimeout(() => setShake(false), 500);
    }

    // Immediately clear the input to prepare for next keystroke
    e.target.value = '';
    
    // Refocus to keep the trap active
    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus();
      }
    }, 0);
  };

  // Handle input blur - aggressively refocus
  const handleInputBlur = () => {
    if (inputRef.current && !isComplete) {
      setTimeout(() => {
        inputRef.current?.focus();
      }, 0);
    }
  };

  // Handle clicks on modal to refocus the input trap
  const handleModalClick = (e) => {
    // Only refocus if clicking on non-interactive elements
    // Exclude: buttons, completion overlay, and hand visual (for calibration)
    const isInteractive = e.target.tagName === 'BUTTON' || 
                          e.target.closest('button') ||
                          e.target.closest('.completion-overlay') ||
                          e.target.closest('.hand-visual-wrapper') ||
                          e.target.closest('.hand-visual-container');
    
    if (!isInteractive && inputRef.current && !isComplete) {
      inputRef.current.focus();
    }
  };

  const playClickSound = () => {
    // Create a simple click sound using Web Audio API
    try {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      
      oscillator.frequency.value = 800;
      oscillator.type = 'sine';
      
      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.1);
      
      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.1);
    } catch (err) {
      console.warn('Could not play click sound:', err);
    }
  };

  const playErrorSound = () => {
    try {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      
      oscillator.frequency.value = 200;
      oscillator.type = 'sawtooth';
      
      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);
      
      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.2);
    } catch (err) {
      console.warn('Could not play error sound:', err);
    }
  };

  const getCurrentTargetKey = () => {
    if (!config || currentDrillIndex >= config.drillSequence.length) return null;
    const char = config.drillSequence[currentDrillIndex];
    // Keep space as-is, lowercase everything else
    return char === ' ' ? ' ' : char.toLowerCase();
  };

  // Update active finger when drill index or config changes
  useEffect(() => {
    if (!config) return;
    const targetKey = getCurrentTargetKey();
    if (targetKey) {
      const fingerId = FINGER_MAP[targetKey];
      setActiveFinger(fingerId || null);
    } else {
      setActiveFinger(null);
    }
  }, [currentDrillIndex, config]);

  const getCurrentFingerHint = () => {
    const targetKey = getCurrentTargetKey();
    if (!targetKey) return '';

    const fingerId = FINGER_MAP[targetKey];
    if (!fingerId) return '';

    // Parse finger ID (e.g., 'l-index' -> 'Left Index Finger')
    const parts = fingerId.split('-');
    const side = parts[0]; // 'l' or 'r'
    const fingerType = parts[1]; // 'pinky', 'ring', 'middle', 'index', 'thumb'

    const fingerNames = {
      'pinky': language === 'zh' ? '小指' : 'Pinky',
      'ring': language === 'zh' ? '无名指' : 'Ring Finger',
      'middle': language === 'zh' ? '中指' : 'Middle Finger',
      'index': language === 'zh' ? '食指' : 'Index Finger',
      'thumb': language === 'zh' ? '拇指' : 'Thumb'
    };

    const sideText = side === 'l'
      ? (language === 'zh' ? '左手' : 'Left')
      : (language === 'zh' ? '右手' : 'Right');

    return `${sideText} ${fingerNames[fingerType] || 'Finger'}`;
  };


  const renderKeyboard = () => {
    if (!config) return null;

    const targetKey = getCurrentTargetKey();

    return (
      <div 
        ref={keyboardRef}
        className={`keyboard-visual ${shake ? 'shake' : ''}`}
      >
        {KEYBOARD_LAYOUT.map((row, rowIndex) => (
          <div key={rowIndex} className="keyboard-row">
            {row.map((key) => {
              // Handle SPACE special case
              const isSpace = key === 'SPACE';
              const actualKey = isSpace ? ' ' : key;
              const fingerId = FINGER_MAP[actualKey];
              // Extract finger type from ID (e.g., 'l-index' -> 'index')
              const fingerType = fingerId ? fingerId.split('-')[1] : 'pinky';
              const color = FINGER_COLORS[fingerType] || '#e5e7eb';
              const isActive = targetKey === actualKey;
              const isNewKey = config.newKeys.includes(actualKey === ' ' ? ' ' : actualKey.toLowerCase());
              const isHighlighted = isNewKey || isActive;

              return (
                <div
                  key={key}
                  className={`key ${isActive ? 'active' : ''} ${isHighlighted ? 'highlighted' : ''} ${isSpace ? 'space-key' : ''}`}
                  style={{
                    backgroundColor: isActive ? '#3b82f6' : (isHighlighted ? `${color}40` : color),
                    border: isActive 
                      ? `3px solid #2563eb` 
                      : isHighlighted 
                      ? `2px solid ${color}` 
                      : `1px solid #d1d5db`,
                    animation: isActive ? 'pulse 1s ease-in-out infinite' : 'none',
                    color: isActive ? 'white' : '#1f2937',
                    fontWeight: isActive ? 'bold' : 'normal',
                    fontSize: isActive ? '18px' : '14px',
                    boxShadow: isActive 
                      ? `0 0 15px rgba(59, 130, 246, 0.5), inset 0 0 10px rgba(255, 255, 255, 0.2)` 
                      : 'none',
                    boxSizing: 'border-box',
                    // Spacebar styling: wider to look like a real spacebar
                    ...(isSpace ? {
                      minWidth: '300px',
                      maxWidth: '400px',
                      width: '60%',
                      flexGrow: 1
                    } : {})
                  }}
                >
                  {isSpace ? (language === 'zh' ? '空格' : 'SPACE') : key.toUpperCase()}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    );
  };

  const renderDrillSequence = () => {
    if (!config) return null;

    return (
      <div className="drill-sequence">
        {config.drillSequence.split('').map((char, index) => (
          <span
            key={index}
            className={`drill-char ${index === currentDrillIndex ? 'current' : index < currentDrillIndex ? 'completed' : ''}`}
            style={char === ' ' ? {
              padding: '8px 20px',
              backgroundColor: index === currentDrillIndex ? '#dbeafe' : index < currentDrillIndex ? '#d1fae5' : 'transparent',
              border: index === currentDrillIndex ? '2px solid #3b82f6' : 'none',
              borderRadius: '4px'
            } : {}}
          >
            {char === ' ' ? '⎵' : char}
          </span>
        ))}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="keyboard-tutor-modal-overlay">
        <div className="keyboard-tutor-modal">
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <div style={{ fontSize: '18px', color: '#6b7280' }}>
              {language === 'zh' ? '加载中...' : 'Loading...'}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="keyboard-tutor-modal-overlay">
        <div className="keyboard-tutor-modal">
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <div style={{ fontSize: '18px', color: '#ef4444', marginBottom: '20px' }}>
              {language === 'zh' ? '未找到课程配置' : 'Lesson configuration not found'}
            </div>
            <button onClick={onClose} className="close-button">
              {language === 'zh' ? '关闭' : 'Close'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const progress = ((currentDrillIndex) / config.drillSequence.length) * 100;

  return (
    <div className="keyboard-tutor-modal-overlay" onClick={handleModalClick}>
      <div className="keyboard-tutor-modal" onClick={handleModalClick} style={{ position: 'relative' }}>
        {/* Hidden Input Trap - captures all keystrokes */}
        <input
          ref={inputRef}
          type="text"
          autoFocus
          autoComplete="off"
          onChange={handleInputChange}
          onBlur={handleInputBlur}
          onKeyDown={(e) => {
            // Prevent arrow keys, backspace, etc. from being typed
            if (e.key.length > 1 && !['Space', 'Enter'].includes(e.key)) {
              e.preventDefault();
            }
          }}
          style={{
            opacity: 0,
            position: 'absolute',
            top: 0,
            left: 0,
            height: '1px',
            width: '1px',
            cursor: 'default',
            fontSize: '16px', // Prevents iOS zoom on focus
            pointerEvents: 'none', // Allow clicks to pass through!
            zIndex: 1,
            border: 'none',
            outline: 'none',
            background: 'transparent',
            color: 'transparent',
            caretColor: 'transparent' // Hide the caret
          }}
          tabIndex={0}
        />

        {/* Close Button */}
        <button 
          onClick={(e) => {
            e.stopPropagation();
            onClose();
          }} 
          className="close-button"
          style={{ zIndex: 1001 }}
        >
          ×
        </button>

        {/* Header */}
        <div className="tutor-header">
          <h2 style={{ margin: '0 0 8px 0', fontSize: '24px', fontWeight: 'bold', color: '#1f2937' }}>
            {config.title}
          </h2>
          <p style={{ margin: 0, fontSize: '16px', color: '#6b7280' }}>
            {config.instruction}
          </p>
        </div>

        {/* Progress Bar */}
        <div className="progress-bar-container">
          <div 
            className="progress-bar" 
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Section 1: Hand Visual (Top - ~35% height) */}
        <div style={{ 
          flex: '0 0 35%', 
          minHeight: 0, 
          display: 'flex', 
          flexDirection: 'column', 
          justifyContent: 'center',
          alignItems: 'center',
          width: '100%',
          zIndex: 10,
          position: 'relative'
        }}>
          <HandVisual activeFinger={activeFinger} />
        </div>

        {/* Section 2: Finger Hint & Drill Sequence (Middle) */}
        <div style={{ flex: '0 0 auto', marginBottom: '8px' }}>
          <div className="finger-hint">
            <span style={{ 
              fontWeight: 'bold', 
              color: config.fingerColor 
            }}>
              {language === 'zh' ? '使用您的' : 'Use your'} {getCurrentFingerHint()}!
            </span>
          </div>
        </div>

        <div style={{ flex: '0 0 auto', marginBottom: '8px' }}>
          {renderDrillSequence()}
        </div>

        {/* Section 3: Keyboard (Bottom - flex to fill remaining space) */}
        <div style={{ flex: '1 1 auto', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          {renderKeyboard()}
        </div>

        {/* Completion Overlay */}
        {isComplete && (
          <div className="completion-overlay">
            <div className="completion-content">
              <div style={{ fontSize: '48px', marginBottom: '16px' }}>🎉</div>
              <h3 style={{ fontSize: '28px', margin: '0 0 16px 0', color: '#1f2937' }}>
                {language === 'zh' ? '做得很好！' : 'Great Job!'}
              </h3>
              <p style={{ fontSize: '16px', color: '#6b7280', marginBottom: '24px' }}>
                {language === 'zh' 
                  ? '您已掌握正确的指法，可以开始游戏了！' 
                  : 'You\'ve mastered the correct finger placement. Ready to start the game!'}
              </p>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  // Mark tutorial as completed in localStorage
                  localStorage.setItem(`tutorialCompleted_${lessonId}`, 'true');
                  onComplete();
                }}
                className="start-game-button"
              >
                {language === 'zh' ? '开始游戏' : 'Start Game'}
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

export default KeyboardTutorModal;

