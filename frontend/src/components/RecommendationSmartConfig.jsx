import React, { useState, useEffect } from 'react';
import { Book, Sparkles, Target, BookOpen } from 'lucide-react';

const PRESETS = {
  vocab: {
    id: 'vocab',
    label: { zh: '早期词汇', en: 'Early Vocab' },
    description: 'Focus on concrete nouns/objects.',
    icon: Book,
    config: {
      beta_concreteness: 1.2,
      beta_frequency: 0.2,
      beta_ppr: 0.8,
      beta_aoa_penalty: 2.0,
      alpha: 0.5,
    },
  },
  sentence: {
    id: 'sentence',
    label: { zh: '句子构建', en: 'Sentence Building' },
    description: 'Focus on verbs and functional words.',
    icon: Target,
    config: {
      beta_concreteness: 0.2,
      beta_frequency: 1.0,
      beta_ppr: 0.8,
      beta_aoa_penalty: 2.0,
      alpha: 0.5,
    },
  },
  topic: {
    id: 'topic',
    label: { zh: '主题探索', en: 'Theme Exploration' },
    description: 'Focus on words semantically close to what is known.',
    icon: Sparkles,
    config: {
      beta_concreteness: 0.5,
      beta_frequency: 0.3,
      beta_ppr: 1.5,
      beta_aoa_penalty: 2.0,
      alpha: 0.85,
    },
  },
  standard: {
    id: 'standard',
    label: { zh: '标准课程', en: 'Standard Course' },
    description: 'The default balanced mode.',
    icon: BookOpen,
    config: {
      beta_concreteness: 0.8,
      beta_frequency: 0.4,
      beta_ppr: 1.0,
      beta_aoa_penalty: 2.0,
      alpha: 0.5,
    },
  },
};

const RecommendationSmartConfig = ({ currentLevel, onConfigChange, initialConfig, language = 'zh' }) => {
  // Persistence keys
  const strategyKey = `srs_rec_strategy_${language}`;
  const excludeMultiKey = `srs_rec_exclude_multi_${language}`;
  
  const [selectedScenario, setSelectedScenario] = useState(() => {
    const saved = localStorage.getItem(strategyKey);
    return saved && PRESETS[saved] ? saved : 'standard';
  });

  const [activeTab, setActiveTab] = useState('mode'); // 'mode' or 'expert'

  const [excludeMultiword, setExcludeMultiword] = useState(() => {
    const saved = localStorage.getItem(excludeMultiKey);
    return saved !== null ? saved === 'true' : true;
  });
  
  // Current config values (independent of whether a scenario is selected)
  const [config, setConfig] = useState(() => {
    const scenario = PRESETS[selectedScenario || 'standard'];
    return {
      ...scenario.config,
      ...initialConfig
    };
  });

  const [currentLevelState, setCurrentLevelState] = useState(currentLevel || 1);
  const [maxLevelState, setMaxLevelState] = useState(initialConfig?.max_hsk_level || 4);

  // Sync with parent whenever key local state changes
  useEffect(() => {
    const finalConfig = {
      ...initialConfig,
      ...config,
      max_hsk_level: maxLevelState,
      exclude_multiword: excludeMultiword,
      mental_age: initialConfig?.mental_age || 8.0,
      top_n: initialConfig?.top_n || 50
    };
    onConfigChange(finalConfig);
  }, [config, maxLevelState, excludeMultiword]);

  // Sync currentLevel prop changes from parent
  useEffect(() => {
    if (currentLevel !== undefined && currentLevel !== currentLevelState) {
      setCurrentLevelState(currentLevel);
    }
  }, [currentLevel]);

  const handleScenarioChange = (scenarioId) => {
    const scenario = PRESETS[scenarioId];
    setSelectedScenario(scenarioId);
    setConfig(prev => ({
      ...prev,
      ...scenario.config
    }));
    localStorage.setItem(strategyKey, scenarioId);
  };

  const handleSliderChange = (key, value) => {
    // If sliders are adjusted, we are effectively in "expert" mode, but we keep the tab selection as is.
    // However, we should deselect the preset scenario as it's modified.
    if (selectedScenario) {
        setSelectedScenario(null); 
        localStorage.removeItem(strategyKey);
    }
    setConfig(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const handleExcludeMultiToggle = () => {
    const newValue = !excludeMultiword;
    setExcludeMultiword(newValue);
    localStorage.setItem(excludeMultiKey, newValue.toString());
  };

  const handleCurrentLevelChange = (level) => {
    const newLevel = parseInt(level);
    setCurrentLevelState(newLevel);
    if (newLevel > maxLevelState) {
      setMaxLevelState(newLevel);
    }
  };

  const handleMaxLevelChange = (level) => {
    const newLevel = parseInt(level);
    setMaxLevelState(newLevel);
  };

  const levelLabel = language === 'zh' ? 'HSK' : 'Level';

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm mb-6 overflow-hidden">
      {/* Header with Level Controls and Toggle */}
      <div style={{ padding: '20px 24px', borderBottom: '1px solid #eee', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label style={{ 
            fontSize: '14px', 
            fontWeight: '600', 
            color: '#374151', 
            whiteSpace: 'nowrap',
            marginRight: '8px' 
          }}>
            {language === 'zh' ? '当前水平' : 'Current Level'}
          </label>
          <select
            value={currentLevelState}
            onChange={(e) => handleCurrentLevelChange(e.target.value)}
            style={{
              padding: '6px 12px',
              fontSize: '14px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              backgroundColor: 'white',
              color: '#111827',
              outline: 'none'
            }}
          >
            {[1, 2, 3, 4, 5, 6].map((level) => (
              <option key={level} value={level}>
                {levelLabel} {level}
              </option>
            ))}
          </select>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label style={{ 
            fontSize: '14px', 
            fontWeight: '600', 
            color: '#374151', 
            whiteSpace: 'nowrap',
            marginRight: '8px' 
          }}>
            {language === 'zh' ? '最高上限' : 'Max Level'}
          </label>
          <select
            value={maxLevelState}
            onChange={(e) => handleMaxLevelChange(e.target.value)}
            style={{
              padding: '6px 12px',
              fontSize: '14px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              backgroundColor: 'white',
              color: '#111827',
              outline: 'none'
            }}
          >
            {[1, 2, 3, 4, 5, 6].map((level) => (
              <option key={level} value={level}>
                {levelLabel} {level}
              </option>
            ))}
          </select>
        </div>
        
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <div style={{ position: 'relative' }}>
              <input
                type="checkbox"
                checked={excludeMultiword}
                onChange={handleExcludeMultiToggle}
                style={{ 
                  position: 'absolute',
                  opacity: 0,
                  width: 0,
                  height: 0
                }}
              />
              <div style={{ 
                width: '40px', 
                height: '20px', 
                borderRadius: '999px', 
                transition: 'background-color 0.2s',
                backgroundColor: excludeMultiword ? '#3b82f6' : '#d1d5db'
              }}></div>
              <div style={{ 
                position: 'absolute',
                left: '2px',
                top: '2px',
                backgroundColor: 'white',
                width: '16px',
                height: '16px',
                borderRadius: '50%',
                transition: 'transform 0.2s',
                transform: excludeMultiword ? 'translateX(20px)' : 'translateX(0)'
              }}></div>
            </div>
            <span style={{ 
              fontSize: '14px', 
              fontWeight: '600', 
              color: '#374151'
            }}>
              {language === 'zh' ? '排除多词短语' : 'Exclude Multi-word'}
            </span>
          </label>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ 
        display: 'flex', 
        borderBottom: '1px solid #eee',
        marginBottom: '20px'
      }}>
        <button
           onClick={() => setActiveTab('mode')}
           style={{
             flex: 1,
             padding: '12px 0',
             fontSize: '14px',
             fontWeight: '700',
             textAlign: 'center',
             transition: 'all 0.2s',
             position: 'relative',
             border: 'none',
             background: activeTab === 'mode' ? 'white' : '#f9fafb',
             color: activeTab === 'mode' ? '#2563eb' : '#6b7280',
             cursor: 'pointer'
           }}
        >
          {language === 'zh' ? '模式选择' : 'Mode Selection'}
          {activeTab === 'mode' && <div style={{ position: 'absolute', bottom: 0, left: 0, width: '100%', height: '2px', backgroundColor: '#3b82f6' }}></div>}
        </button>
        <button
           onClick={() => setActiveTab('expert')}
           style={{
             flex: 1,
             padding: '12px 0',
             fontSize: '14px',
             fontWeight: '700',
             textAlign: 'center',
             transition: 'all 0.2s',
             position: 'relative',
             border: 'none',
             background: activeTab === 'expert' ? 'white' : '#f9fafb',
             color: activeTab === 'expert' ? '#2563eb' : '#6b7280',
             cursor: 'pointer'
           }}
        >
          {language === 'zh' ? '专家微调' : 'Expert Tuning'}
          {activeTab === 'expert' && <div style={{ position: 'absolute', bottom: 0, left: 0, width: '100%', height: '2px', backgroundColor: '#3b82f6' }}></div>}
        </button>
      </div>

      <div style={{ padding: '0 24px 24px 24px' }}>
        {activeTab === 'mode' && (
            <div>
                <div style={{ display: 'flex', gap: '12px', width: '100%', marginBottom: '20px' }}>
                {Object.values(PRESETS).map((scenario) => {
                    const isActive = selectedScenario === scenario.id;
                    return (
                    <button
                        key={scenario.id}
                        onClick={() => handleScenarioChange(scenario.id)}
                        style={{
                          flex: 1,
                          padding: '12px',
                          borderRadius: '8px',
                          transition: 'all 0.2s',
                          textAlign: 'center',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '16px',
                          fontWeight: '500',
                          cursor: 'pointer',
                          boxShadow: isActive ? '0 2px 4px rgba(0,0,0,0.1)' : 'none',
                          border: isActive ? 'none' : '1px solid #d9d9d9',
                          backgroundColor: isActive ? '#1890ff' : '#f5f5f5',
                          color: isActive ? 'white' : '#555'
                        }}
                        title={scenario.description}
                    >
                        {language === 'zh' ? scenario.label.zh : scenario.label.en}
                    </button>
                    );
                })}
                </div>
            </div>
        )}

        {activeTab === 'expert' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <ParameterControls
                config={config}
                onConfigChange={handleSliderChange}
                language={language}
              />
            </div>
        )}
      </div>
    </div>
  );
};

const ParameterControls = ({ config, onConfigChange, language }) => {
  const sliders = [
    {
      key: 'beta_ppr',
      label: language === 'zh' ? 'PPR 权重' : 'PPR Weight',
      min: 0, max: 3, step: 0.1
    },
    {
      key: 'beta_concreteness',
      label: language === 'zh' ? '具象权重' : 'Concreteness Weight',
      min: 0, max: 3, step: 0.1
    },
    {
      key: 'beta_frequency',
      label: language === 'zh' ? '频率权重' : 'Frequency Weight',
      min: 0, max: 3, step: 0.1
    },
    {
      key: 'beta_aoa_penalty',
      label: language === 'zh' ? 'AoA 惩罚' : 'AoA Penalty',
      min: 0, max: 5, step: 0.1
    },
    {
      key: 'alpha',
      label: language === 'zh' ? '多样性 (Alpha)' : 'Diversity (Alpha)',
      min: 0, max: 1, step: 0.05
    }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {sliders.map(s => (
        <div key={s.key} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <label style={{ fontSize: '15px', fontWeight: '600', color: '#374151' }}>
              {s.label}
            </label>
            <span style={{ 
              fontSize: '14px', 
              fontFamily: 'monospace', 
              fontWeight: '700', 
              color: '#2563eb', 
              backgroundColor: '#eff6ff', 
              padding: '2px 8px', 
              borderRadius: '4px' 
            }}>
              {config[s.key]?.toFixed(2) || '0.00'}
            </span>
          </div>
          <input
            type="range"
            min={s.min}
            max={s.max}
            step={s.step}
            value={config[s.key] || 0}
            onChange={(e) => onConfigChange(s.key, parseFloat(e.target.value))}
            style={{
              width: '100%',
              height: '6px',
              backgroundColor: '#e5e7eb',
              borderRadius: '999px',
              appearance: 'none',
              cursor: 'pointer',
              outline: 'none'
            }}
          />
        </div>
      ))}
    </div>
  );
};

export default RecommendationSmartConfig;
