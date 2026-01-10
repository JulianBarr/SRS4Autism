import React, { useState, useEffect, useRef } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import HandVisual from './HandVisual';
import './KeyboardTutorModal.css';

// Lesson configurations
const TUTORIAL_CONFIG = {
  "1": {
    "title": "Home Row: Index Fingers",
    "drillSequence": "fff jjj fjf jfj",
  },
  "2": {
    "title": "Reaching Up: D & K",
    "drillSequence": "ddd kkk dkd kdk",
  }
};

const KEYBOARD_LAYOUT = [
  ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
  ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'],
  ['z', 'x', 'c', 'v', 'b', 'n', 'm'],
  ['SPACE'] 
];

const FINGER_MAP = {
  'q': 'l-pinky', 'a': 'l-pinky', 'z': 'l-pinky',
  'w': 'l-ring',  's': 'l-ring',  'x': 'l-ring',
  'e': 'l-middle','d': 'l-middle','c': 'l-middle',
  'r': 'l-index', 'f': 'l-index', 'v': 'l-index', 't': 'l-index', 'g': 'l-index', 'b': 'l-index',
  'y': 'r-index', 'h': 'r-index', 'n': 'r-index', 'u': 'r-index', 'j': 'r-index', 'm': 'r-index',
  'i': 'r-middle', 'k': 'r-middle',
  'o': 'r-ring',   'l': 'r-ring',
  'p': 'r-pinky',
  ' ': 'r-thumb'
};

const KeyboardTutorModal = ({ lessonId, onClose, onComplete }) => {
  const { language } = useLanguage();
  const config = TUTORIAL_CONFIG[lessonId] || TUTORIAL_CONFIG["1"];
  const drillSequence = config.drillSequence;
  
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isError, setIsError] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const inputRef = useRef(null);

  // Derived state
  const targetChar = drillSequence[currentIndex];
  const activeFinger = targetChar ? FINGER_MAP[targetChar] : null;

  // Focus trap
  useEffect(() => {
    if (inputRef.current) inputRef.current.focus();
  });

  const handleInput = (e) => {
    const val = e.target.value;
    if (!val) return;

    // Get last char typed (to handle fast typing)
    const char = val.slice(-1).toLowerCase();
    
    // Clear input immediately to keep trap clean
    e.target.value = '';

    if (isComplete) return;

    if (char === targetChar) {
      // Correct
      setIsError(false);
      const nextIndex = currentIndex + 1;
      if (nextIndex >= drillSequence.length) {
        setIsComplete(true);
      } else {
        setCurrentIndex(nextIndex);
      }
    } else {
      // Wrong
      setIsError(true);
      setTimeout(() => setIsError(false), 400);
    }
  };

  const renderDrillSequence = () => (
    <div className="drill-display">
      {drillSequence.split('').map((char, idx) => {
        let className = "drill-char";
        if (idx < currentIndex) className += " completed";
        else if (idx === currentIndex) className += " current";
        return (
          <span key={idx} className={className}>
            {char === ' ' ? '␣' : char}
          </span>
        );
      })}
    </div>
  );

  const renderKeyboard = () => (
    <div className="keyboard-container">
      {KEYBOARD_LAYOUT.map((row, rowIndex) => (
        <div key={rowIndex} className="keyboard-row">
          {row.map((keyChar) => {
            const isTarget = keyChar === (targetChar === ' ' ? 'SPACE' : targetChar);
            const isSpace = keyChar === 'SPACE';
            const fingerClass = FINGER_MAP[isSpace ? ' ' : keyChar]?.split('-')[1] || '';
            
            let className = `key ${fingerClass}`;
            if (isTarget) className += " active";
            if (isTarget && isError) className += " error";
            if (isSpace) className += " key-space";

            return (
              <div key={keyChar} className={className}>
                {isSpace ? 'SPACE' : keyChar}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );

  return (
    <div className="keyboard-tutor-modal-overlay">
      <div className="keyboard-tutor-modal" onClick={() => inputRef.current?.focus()}>
        <button className="close-button" onClick={onClose}>×</button>
        
        {/* Hidden Input Trap */}
        <input 
          ref={inputRef}
          type="text" 
          autoFocus
          autoComplete="off"
          onChange={handleInput}
          style={{ opacity: 0, position: 'absolute', width: 1, height: 1, pointerEvents: 'none' }} 
        />

        {/* 1. Hands Visual (Compact) */}
        <div className="hand-visual-section">
           <HandVisual activeFinger={activeFinger} />
        </div>

        {/* 2. Drill Text */}
        {renderDrillSequence()}

        {/* 3. Keyboard Grid */}
        {renderKeyboard()}

        {/* Completion Overlay */}
        {isComplete && (
          <div className="completion-overlay">
            <div className="completion-content">
              <div style={{ fontSize: '48px', marginBottom: '16px' }}>🎉</div>
              <h3>{language === 'zh' ? '做得很好！' : 'Great Job!'}</h3>
              <button
                onClick={(e) => {
                  e.stopPropagation();
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