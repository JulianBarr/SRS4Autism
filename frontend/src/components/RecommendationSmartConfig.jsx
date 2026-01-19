import React, { useState, useEffect, useCallback } from 'react';
import { Book, Sparkles, Target, BookOpen, Settings2, ChevronDown, ChevronUp } from 'lucide-react';

const PRESETS = {
  vocab: {
    id: 'vocab',
    name: '早期词汇 / Early Vocab (具象)',
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
    name: '句子构建 / Sentence Building (动词/抽象)',
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
    name: '主题探索 / Theme Exploration (语义关联)',
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
    name: '标准课程 / Standard Course (均衡)',
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
  const advancedKey = `srs_rec_advanced_${language}`;
  
  const [selectedScenario, setSelectedScenario] = useState(() => {
    const saved = localStorage.getItem(strategyKey);
    return saved && PRESETS[saved] ? saved : 'standard';
  });

  const [excludeMultiword, setExcludeMultiword] = useState(() => {
    const saved = localStorage.getItem(excludeMultiKey);
    return saved !== null ? saved === 'true' : true;
  });

  const [showAdvanced, setShowAdvanced] = useState(() => {
    return localStorage.getItem(advancedKey) === 'true';
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
    setSelectedScenario(null); // Manual change "unlocks" strategy selection
    localStorage.removeItem(strategyKey);
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

  const handleAdvancedToggle = () => {
    const newValue = !showAdvanced;
    setShowAdvanced(newValue);
    localStorage.setItem(advancedKey, newValue.toString());
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
      <div className="px-4 py-3 bg-gray-50/50 dark:bg-gray-700/30 border-b border-gray-200 dark:border-gray-700">
        <div className="flex flex-wrap items-center gap-6">
          <div className="flex items-center gap-2">
            <label className="text-sm font-semibold text-gray-700 dark:text-gray-300 whitespace-nowrap">
              {language === 'zh' ? '当前水平' : 'Current Level'}
            </label>
            <select
              value={currentLevelState}
              onChange={(e) => handleCurrentLevelChange(e.target.value)}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {[1, 2, 3, 4, 5, 6].map((level) => (
                <option key={level} value={level}>
                  {levelLabel} {level}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm font-semibold text-gray-700 dark:text-gray-300 whitespace-nowrap">
              {language === 'zh' ? '最高上限' : 'Max Level'}
            </label>
            <select
              value={maxLevelState}
              onChange={(e) => handleMaxLevelChange(e.target.value)}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {[1, 2, 3, 4, 5, 6].map((level) => (
                <option key={level} value={level}>
                  {levelLabel} {level}
                </option>
              ))}
            </select>
          </div>
          
          <div className="flex items-center gap-2 ml-auto">
            <label className="flex items-center gap-2 cursor-pointer group">
              <div className="relative">
                <input
                  type="checkbox"
                  checked={excludeMultiword}
                  onChange={handleExcludeMultiToggle}
                  className="sr-only"
                />
                <div className={`w-10 h-5 rounded-full transition-colors ${excludeMultiword ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'}`}></div>
                <div className={`absolute left-0.5 top-0.5 bg-white w-4 h-4 rounded-full transition-transform ${excludeMultiword ? 'translate-x-5' : 'translate-x-0'}`}></div>
              </div>
              <span className="text-sm font-semibold text-gray-700 dark:text-gray-300 group-hover:text-blue-600 transition-colors">
                {language === 'zh' ? '排除多词短语' : 'Exclude Multi-word'}
              </span>
            </label>
          </div>
        </div>
      </div>

      {/* Strategy Grid */}
      <div className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {Object.values(PRESETS).map((scenario) => {
            const Icon = scenario.icon;
            const isActive = selectedScenario === scenario.id;
            return (
              <button
                key={scenario.id}
                onClick={() => handleScenarioChange(scenario.id)}
                className={`group p-4 rounded-xl border-2 transition-all text-left flex flex-col gap-2 ${
                  isActive
                    ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-900/20 ring-1 ring-blue-500/50'
                    : 'border-gray-100 dark:border-gray-700 bg-white dark:bg-gray-800 hover:border-blue-200 dark:hover:border-blue-800 hover:bg-blue-50/20'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg transition-colors ${
                    isActive 
                      ? 'bg-blue-500 text-white' 
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-500 group-hover:bg-blue-100 dark:group-hover:bg-blue-900/30 group-hover:text-blue-600'
                  }`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className={`text-sm font-bold transition-colors ${
                    isActive ? 'text-blue-700 dark:text-blue-300' : 'text-gray-900 dark:text-gray-100'
                  }`}>
                    {scenario.name}
                  </span>
                </div>
                <p className={`text-xs leading-relaxed transition-colors ${
                  isActive ? 'text-blue-600/80 dark:text-blue-300/70' : 'text-gray-500 dark:text-gray-400'
                }`}>
                  {scenario.description}
                </p>
              </button>
            );
          })}
        </div>

        {/* Advanced Toggle */}
        <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
          <button
            onClick={handleAdvancedToggle}
            className="flex items-center gap-2 text-xs font-bold text-gray-400 hover:text-blue-500 transition-colors uppercase tracking-wider"
          >
            <Settings2 className="w-3.5 h-3.5" />
            {language === 'zh' ? '专家模式 / Advanced Tuning' : 'Advanced Tuning / Expert Mode'}
            {showAdvanced ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>

          {showAdvanced && (
            <div className="mt-4 grid grid-cols-1 gap-4 p-4 bg-gray-50 dark:bg-gray-900/40 rounded-xl border border-gray-100 dark:border-gray-700">
              <ParameterControls
                config={config}
                onConfigChange={handleSliderChange}
                language={language}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const ParameterControls = ({ config, onConfigChange, language }) => {
  const sliders = [
    {
      key: 'beta_ppr',
      label: language === 'zh' ? '语义关联权重' : 'PPR Weight',
      sub: 'beta_ppr',
      min: 0, max: 3, step: 0.1
    },
    {
      key: 'beta_concreteness',
      label: language === 'zh' ? '具象程度权重' : 'Concreteness Weight',
      sub: 'beta_concreteness',
      min: 0, max: 3, step: 0.1
    },
    {
      key: 'beta_frequency',
      label: language === 'zh' ? '词频权重' : 'Frequency Weight',
      sub: 'beta_frequency',
      min: 0, max: 3, step: 0.1
    },
    {
      key: 'beta_aoa_penalty',
      label: language === 'zh' ? '习得年龄惩罚' : 'AoA Penalty',
      sub: 'beta_aoa_penalty',
      min: 0, max: 5, step: 0.1
    },
    {
      key: 'alpha',
      label: language === 'zh' ? '探索多样性' : 'Diversity (Alpha)',
      sub: 'alpha',
      min: 0, max: 1, step: 0.05
    }
  ];

  return (
    <div className="space-y-4">
      {sliders.map(s => (
        <div key={s.key} className="space-y-1.5">
          <div className="flex justify-between items-center">
            <label className="text-xs font-bold text-gray-700 dark:text-gray-300">
              {s.label}
              <span className="ml-2 font-mono text-[10px] text-gray-400 font-normal">{s.sub}</span>
            </label>
            <span className="text-xs font-mono font-bold text-blue-600 bg-blue-50 dark:bg-blue-900/30 px-2 py-0.5 rounded">
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
            className="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
          />
        </div>
      ))}
    </div>
  );
};

export default RecommendationSmartConfig;
