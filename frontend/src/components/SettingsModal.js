import React, { useState, useEffect } from 'react';
import { useLanguage } from '../i18n/LanguageContext';

const SettingsModal = ({ isOpen, onClose }) => {
  const { language, t } = useLanguage();
  const [provider, setProvider] = useState('gemini');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');

  // Load settings from localStorage on mount
  useEffect(() => {
    if (isOpen) {
      const savedProvider = localStorage.getItem('llm_provider') || 'gemini';
      const savedApiKey = localStorage.getItem('llm_key') || '';
      const savedBaseUrl = localStorage.getItem('llm_base_url') || '';
      
      setProvider(savedProvider);
      setApiKey(savedApiKey);
      setBaseUrl(savedBaseUrl);
    }
  }, [isOpen]);

  const handleSave = () => {
    // Save to localStorage
    localStorage.setItem('llm_provider', provider);
    localStorage.setItem('llm_key', apiKey);
    localStorage.setItem('llm_base_url', baseUrl);
    
    // Close modal
    onClose();
  };

  const handleCancel = () => {
    // Reset to saved values
    const savedProvider = localStorage.getItem('llm_provider') || 'gemini';
    const savedApiKey = localStorage.getItem('llm_key') || '';
    const savedBaseUrl = localStorage.getItem('llm_base_url') || '';
    
    setProvider(savedProvider);
    setApiKey(savedApiKey);
    setBaseUrl(savedBaseUrl);
    
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
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
      }}
      onClick={handleCancel}
    >
      <div
        style={{
          backgroundColor: 'white',
          borderRadius: '12px',
          maxWidth: '500px',
          width: '100%',
          boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
          position: 'relative'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: '1px solid #e5e7eb',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}
        >
          <h2 style={{ margin: 0, fontSize: '24px', fontWeight: 'bold', color: '#1f2937' }}>
            {language === 'zh' ? '模型配置' : 'Model Configuration'}
          </h2>
          <button
            onClick={handleCancel}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '24px',
              cursor: 'pointer',
              color: '#6b7280',
              padding: '0',
              width: '32px',
              height: '32px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: '4px'
            }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = '#f3f4f6';
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = 'transparent';
            }}
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '24px' }}>
          <div style={{ marginBottom: '20px' }}>
            <label
              style={{
                display: 'block',
                marginBottom: '8px',
                fontSize: '14px',
                fontWeight: '600',
                color: '#374151'
              }}
            >
              {language === 'zh' ? '提供商' : 'Provider'}
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              style={{
                width: '100%',
                padding: '10px',
                fontSize: '14px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                backgroundColor: 'white',
                cursor: 'pointer'
              }}
            >
              <option value="gemini">
                {language === 'zh' ? 'Google Gemini' : 'Google Gemini'}
              </option>
              <option value="deepseek">
                {language === 'zh' ? 'DeepSeek' : 'DeepSeek'}
              </option>
              <option value="openai">
                {language === 'zh' ? 'OpenAI' : 'OpenAI'}
              </option>
            </select>
            <small style={{ display: 'block', marginTop: '4px', color: '#6b7280', fontSize: '12px' }}>
              {language === 'zh'
                ? '选择AI提供商（用于生成图片描述）'
                : 'Select AI provider (for image description generation)'}
            </small>
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label
              style={{
                display: 'block',
                marginBottom: '8px',
                fontSize: '14px',
                fontWeight: '600',
                color: '#374151'
              }}
            >
              {language === 'zh' ? 'API密钥' : 'API Key'}
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={language === 'zh' ? '输入您的API密钥' : 'Enter your API key'}
              style={{
                width: '100%',
                padding: '10px',
                fontSize: '14px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                boxSizing: 'border-box'
              }}
            />
            <small style={{ display: 'block', marginTop: '4px', color: '#6b7280', fontSize: '12px' }}>
              {language === 'zh'
                ? '您的API密钥将安全地存储在本地浏览器中'
                : 'Your API key will be stored securely in your local browser'}
            </small>
          </div>

          <div style={{ marginBottom: '24px' }}>
            <label
              style={{
                display: 'block',
                marginBottom: '8px',
                fontSize: '14px',
                fontWeight: '600',
                color: '#374151'
              }}
            >
              {language === 'zh' ? '自定义代理URL' : 'Custom Base URL'}
            </label>
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.deepseek.com"
              style={{
                width: '100%',
                padding: '10px',
                fontSize: '14px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                boxSizing: 'border-box'
              }}
            />
            <small style={{ display: 'block', marginTop: '4px', color: '#6b7280', fontSize: '12px' }}>
              {language === 'zh'
                ? '用于GFW用户的代理URL（可选）'
                : 'Proxy URL for GFW users (optional)'}
            </small>
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
            <button
              onClick={handleCancel}
              style={{
                padding: '10px 20px',
                fontSize: '14px',
                fontWeight: '600',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                backgroundColor: 'white',
                color: '#374151',
                cursor: 'pointer',
                transition: 'background-color 0.2s'
              }}
              onMouseEnter={(e) => {
                e.target.style.backgroundColor = '#f9fafb';
              }}
              onMouseLeave={(e) => {
                e.target.style.backgroundColor = 'white';
              }}
            >
              {language === 'zh' ? '取消' : 'Cancel'}
            </button>
            <button
              onClick={handleSave}
              style={{
                padding: '10px 20px',
                fontSize: '14px',
                fontWeight: '600',
                border: 'none',
                borderRadius: '6px',
                backgroundColor: '#3b82f6',
                color: 'white',
                cursor: 'pointer',
                transition: 'background-color 0.2s'
              }}
              onMouseEnter={(e) => {
                e.target.style.backgroundColor = '#2563eb';
              }}
              onMouseLeave={(e) => {
                e.target.style.backgroundColor = '#3b82f6';
              }}
            >
              {language === 'zh' ? '保存' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsModal;




