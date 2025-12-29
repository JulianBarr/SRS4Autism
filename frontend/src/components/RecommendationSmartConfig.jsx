import React, { useState, useEffect, useCallback } from 'react';
import { Book, Sparkles, Target, BookOpen } from 'lucide-react';

const PRESETS = {
  vocab: {
    id: 'vocab',
    name: '早期词汇 (具象)',
    description: '聚焦具象名词和实物',
    icon: Book,
    config: {
      beta_concreteness: 2.0,
      beta_frequency: 0.5,
      beta_ppr: 1.0,
      beta_aoa_penalty: 2.0,
      alpha: 0.5,
      max_hsk_level: 1,
    },
  },
  sentence: {
    id: 'sentence',
    name: '句子构建 (动词/抽象)',
    description: '动词和抽象词用于构建句子',
    icon: Target,
    config: {
      beta_concreteness: 0.1,
      beta_frequency: 1.5,
      beta_ppr: 0.8,
      beta_aoa_penalty: 2.0,
      alpha: 0.5,
      max_hsk_level: 3,
    },
  },
  topic: {
    id: 'topic',
    name: '主题探索 (语义关联)',
    description: '深入探索语义关系',
    icon: Sparkles,
    config: {
      beta_ppr: 2.5,
      alpha: 0.85,
      beta_concreteness: 0.5,
      beta_frequency: 0.3,
      beta_aoa_penalty: 2.0,
      max_hsk_level: 6,
    },
  },
  standard: {
    id: 'standard',
    name: '标准课程 (均衡)',
    description: '均衡的通用学习方法',
    icon: BookOpen,
    config: {
      beta_ppr: 1.0,
      beta_concreteness: 0.8,
      beta_frequency: 0.3,
      beta_aoa_penalty: 2.0,
      alpha: 0.5,
      max_hsk_level: 4,
    },
  },
};

const RecommendationSmartConfig = ({ currentLevel, onConfigChange, initialConfig }) => {
  const [activeTab, setActiveTab] = useState('scenario'); // 'scenario' or 'tuning'
  const [selectedScenario, setSelectedScenario] = useState('standard');
  const [zpdLimit, setZpdLimit] = useState(false);
  const [config, setConfig] = useState(initialConfig || {});
  const [currentLevelState, setCurrentLevelState] = useState(currentLevel || 4);
  const [maxLevelState, setMaxLevelState] = useState(initialConfig?.max_hsk_level || 5);

  // Detect if current config matches a scenario
  const detectScenario = useCallback((currentConfig) => {
    for (const [scenarioId, scenario] of Object.entries(PRESETS)) {
      const matches = Object.entries(scenario.config).every(([key, value]) => {
        if (key === 'max_hsk_level') return true; // Ignore max_hsk_level in comparison
        const configValue = currentConfig[key];
        return Math.abs(configValue - value) < 0.01;
      });
      if (matches) {
        return scenarioId;
      }
    }
    return 'standard';
  }, []);

  // Initialize scenario detection
  useEffect(() => {
    if (initialConfig) {
      setConfig(initialConfig);
      const detected = detectScenario(initialConfig);
      setSelectedScenario(detected);
      setMaxLevelState(initialConfig.max_hsk_level || 5);
    }
  }, []); // Only on mount

  // Sync currentLevel prop changes
  useEffect(() => {
    if (currentLevel !== undefined) {
      setCurrentLevelState(currentLevel);
    }
  }, [currentLevel]);

  // Apply scenario configuration
  const applyScenario = useCallback((scenarioId) => {
    const scenario = PRESETS[scenarioId];
    const newConfig = {
      ...scenario.config,
      top_n: config.top_n || 20,
      mental_age: config.mental_age || 5,
      max_hsk_level: zpdLimit ? currentLevelState + 1 : maxLevelState,
    };
    setConfig(newConfig);
    setSelectedScenario(scenarioId);
    onConfigChange(newConfig);
  }, [config.top_n, config.mental_age, zpdLimit, currentLevelState, maxLevelState, onConfigChange]);

  // Handle scenario selection
  const handleScenarioChange = (scenarioId) => {
    applyScenario(scenarioId);
  };

  // Handle ZPD toggle
  const handleZPDToggle = (enabled) => {
    setZpdLimit(enabled);
    const newConfig = {
      ...config,
      max_hsk_level: enabled ? currentLevelState + 1 : maxLevelState,
    };
    setConfig(newConfig);
    onConfigChange(newConfig);
  };

  // Handle level changes
  const handleCurrentLevelChange = (level) => {
    const newLevel = parseInt(level);
    setCurrentLevelState(newLevel);
    const newConfig = {
      ...config,
      max_hsk_level: zpdLimit ? newLevel + 1 : maxLevelState,
    };
    setConfig(newConfig);
    onConfigChange(newConfig);
  };

  const handleMaxLevelChange = (level) => {
    const newLevel = parseInt(level);
    setMaxLevelState(newLevel);
    const newConfig = {
      ...config,
      max_hsk_level: zpdLimit ? currentLevelState + 1 : newLevel,
    };
    setConfig(newConfig);
    onConfigChange(newConfig);
  };

  // Handle parameter slider changes
  const handleParameterChange = (key, value) => {
    const newConfig = {
      ...config,
      [key]: value,
    };
    setConfig(newConfig);
    onConfigChange(newConfig);
  };

  // Update config when initialConfig changes externally
  useEffect(() => {
    if (initialConfig) {
      setConfig(initialConfig);
      const detected = detectScenario(initialConfig);
      setSelectedScenario(detected);
    }
  }, [initialConfig, detectScenario]);

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm mb-4">
      {/* Header with Level Controls */}
      <div className="px-4 pt-4 pb-3 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-4 flex-1">
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">
                当前水平
              </label>
              <select
                value={currentLevelState}
                onChange={(e) => handleCurrentLevelChange(e.target.value)}
                className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
              >
                {[1, 2, 3, 4, 5, 6].map((level) => (
                  <option key={level} value={level}>
                    HSK {level}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">
                最高上限
              </label>
              <select
                value={maxLevelState}
                onChange={(e) => handleMaxLevelChange(e.target.value)}
                disabled={zpdLimit}
                className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {[1, 2, 3, 4, 5, 6].map((level) => (
                  <option key={level} value={level}>
                    HSK {level}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 dark:border-gray-700">
        <button
          onClick={() => setActiveTab('scenario')}
          className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
            activeTab === 'scenario'
              ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400 bg-blue-50 dark:bg-blue-900/20'
              : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700/50'
          }`}
        >
          场景模式
        </button>
        <button
          onClick={() => setActiveTab('tuning')}
          className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
            activeTab === 'tuning'
              ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400 bg-blue-50 dark:bg-blue-900/20'
              : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700/50'
          }`}
        >
          参数微调
        </button>
      </div>

      {/* Tab Content */}
      <div className="p-4">
        {/* Scenario Mode Tab */}
        {activeTab === 'scenario' && (
          <div className="space-y-4">
            {/* Scenario Selection Grid */}
            <div className="grid grid-cols-2 gap-3">
              {Object.values(PRESETS).map((scenario) => {
                const Icon = scenario.icon;
                return (
                  <button
                    key={scenario.id}
                    onClick={() => handleScenarioChange(scenario.id)}
                    className={`p-4 rounded-lg border-2 transition-all text-left ${
                      selectedScenario === scenario.id
                        ? 'border-blue-500 dark:border-blue-400 bg-blue-50 dark:bg-blue-900/30 ring-2 ring-blue-200 dark:ring-blue-800'
                        : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-700 hover:border-blue-300 dark:hover:border-blue-600 hover:bg-blue-50/50 dark:hover:bg-blue-900/10'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <Icon className="w-5 h-5 min-w-[24px] min-h-[24px] text-gray-700 dark:text-gray-300" />
                      <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                        {scenario.name}
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 dark:text-gray-400">{scenario.description}</p>
                  </button>
                );
              })}
            </div>

            {/* ZPD Toggle */}
            <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600">
              <div>
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block">
                  基于最近发展区 (ZPD)
                </label>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  限制为当前水平 + 1
                </p>
              </div>
              <button
                onClick={() => handleZPDToggle(!zpdLimit)}
                className={`relative w-12 h-6 rounded-full transition-colors min-w-[48px] min-h-[24px] ${
                  zpdLimit ? 'bg-blue-500 dark:bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
                }`}
              >
                <span
                  className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${
                    zpdLimit ? 'translate-x-6' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          </div>
        )}

        {/* Parameter Tuning Tab */}
        {activeTab === 'tuning' && (
          <ParameterControls
            config={config}
            onConfigChange={handleParameterChange}
          />
        )}
      </div>
    </div>
  );
};

const ParameterControls = ({ config, onConfigChange }) => {
  const sliderConfigs = [
    {
      key: 'beta_ppr',
      label: '语义关联权重',
      labelEn: 'Semantic',
      min: 0,
      max: 3,
      step: 0.1,
    },
    {
      key: 'beta_concreteness',
      label: '具象程度权重',
      labelEn: 'Concreteness',
      min: 0,
      max: 3,
      step: 0.1,
    },
    {
      key: 'beta_frequency',
      label: '词频权重',
      labelEn: 'Frequency',
      min: 0,
      max: 3,
      step: 0.1,
    },
    {
      key: 'beta_aoa_penalty',
      label: '习得年龄惩罚',
      labelEn: 'AoA',
      min: 0,
      max: 5,
      step: 0.1,
    },
    {
      key: 'alpha',
      label: '探索多样性',
      labelEn: 'Diversity',
      min: 0,
      max: 1,
      step: 0.05,
    },
    {
      key: 'top_n',
      label: '推荐数量',
      labelEn: 'Top N',
      min: 10,
      max: 100,
      step: 10,
    },
  ];

  const formatValue = (value, step) => {
    if (step < 1) {
      return value.toFixed(2);
    }
    return value.toFixed(0);
  };

  return (
    <div className="space-y-6">
      {sliderConfigs.map((slider) => {
        const value = config[slider.key] || (slider.key === 'top_n' ? 20 : 0);
        return (
          <div key={slider.key} className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block">
              {slider.label}
              <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
                ({slider.labelEn})
              </span>
            </label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={slider.min}
                max={slider.max}
                step={slider.step}
                value={value}
                onChange={(e) => onConfigChange(slider.key, parseFloat(e.target.value))}
                className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500 dark:accent-blue-400"
              />
              <span className="text-xs font-mono text-gray-600 dark:text-gray-400 min-w-[50px] px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded border border-gray-300 dark:border-gray-600 text-right">
                {formatValue(value, slider.step)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default RecommendationSmartConfig;

