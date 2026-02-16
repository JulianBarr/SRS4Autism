import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const TopicChat = ({ topicId, topicName, profile, onClose }) => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [userInput, setUserInput] = useState('');
  const [templates, setTemplates] = useState([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState('auto');
  const [availableModels, setAvailableModels] = useState({ card_models: [] });
  const [selectedCardModel, setSelectedCardModel] = useState(null);
  const [quantity, setQuantity] = useState(5);
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);

  // Get roster_id from profile (implicit)
  const rosterId = profile?.id || profile?.name || 'yiming';

  // Load templates on mount and Apply Smart Selection
  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const response = await axios.get(`${API_BASE}/templates`);
        const templatesList = response.data || [];
        setTemplates(templatesList);

        // --- SMART SELECTION LOGIC ---
        // Only override if currently 'auto'
        if (selectedTemplateId === 'auto' && topicId) {
          const lowerTopic = topicId.toLowerCase();
          const isGrammar = lowerTopic.includes('grammar') || lowerTopic.includes('语法') || lowerTopic.includes('句式');

          if (isGrammar) {
            const hasChineseChars = /[\u4e00-\u9fa5]/.test(topicId);

            if (hasChineseChars) {
              const zhTemplate = templatesList.find(t => t.id === 'Grammar_Chinese');
              if (zhTemplate) setSelectedTemplateId('Grammar_Chinese');
            } else {
              const enTemplate = templatesList.find(t => t.id === 'Grammar_English');
              if (enTemplate) setSelectedTemplateId('Grammar_English');
            }
          }
        }
      } catch (error) {
        console.error('Error loading templates:', error);
        setTemplates([]);
      }
    };

    loadTemplates();
  }, [topicId, topicName]);

  // Load available models on mount and sync selected model state
  useEffect(() => {
    const loadAvailableModels = async () => {
      try {
        const response = await axios.get(`${API_BASE}/config/models`);
        const modelsData = response.data || { card_models: [] };
        setAvailableModels(modelsData);
        
        // Load saved selection from localStorage and sync with state
        const savedCardModel = localStorage.getItem('selectedCardModel');
        if (savedCardModel && modelsData.card_models?.find(m => m.id === savedCardModel)) {
          setSelectedCardModel(savedCardModel);
        } else if (modelsData.card_models?.length > 0 && !selectedCardModel) {
          // Set default to first model if no saved selection
          const defaultModel = modelsData.card_models[0].id;
          setSelectedCardModel(defaultModel);
          localStorage.setItem('selectedCardModel', defaultModel);
        }
      } catch (error) {
        console.error('Error loading available models:', error);
        setAvailableModels({ card_models: [] });
      }
    };

    loadAvailableModels();
  }, []);

  // Load chat history on mount
  useEffect(() => {
    const loadHistory = async () => {
      if (!topicId || !rosterId) return;
      
      setLoading(true);
      try {
        const response = await axios.get(`${API_BASE}/chat/topic/history`, {
          params: { topic_id: topicId, roster_id: rosterId }
        });
        setMessages(response.data.messages || []);
      } catch (error) {
        console.error('Error loading chat history:', error);
        setMessages([]);
      } finally {
        setLoading(false);
      }
    };

    loadHistory();
  }, [topicId, rosterId]);

  // Scroll to bottom when messages change
  const scrollToBottom = () => {
    if (messagesContainerRef.current && messagesEndRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    if (messages.length > 0) {
      scrollToBottom();
    }
  }, [messages]);

  const handleGenerate = async () => {
    // Allow empty input if we have a template/mode selected (e.g. just clicking Generate for 5 cards)
    if (!selectedTemplateId || !topicId || !rosterId) return;

    const finalQty = quantity && quantity >= 1 ? Math.min(20, quantity) : 5;
    const finalInstruction = `${userInput.trim()} @quantity:${finalQty}`.trim();

    setUserInput('');
    setSending(true);

    // Add user message to UI immediately
    const newUserMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: finalInstruction,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, newUserMessage]);

    try {
      // 1. Link the UI selection to the data payload
      const activeModel = availableModels.card_models?.find(m => m.id === selectedCardModel);

      if (!activeModel) {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: 'No model selected. Please check AI Model Configuration.',
          timestamp: new Date().toISOString()
        }]);
        setSending(false);
        return;
      }

      // 2. Prepare dynamic headers: use keys from localStorage (SettingsModal), not backend config
      const activeProvider = activeModel.provider === 'gemini' ? 'google' : activeModel.provider;
      const storageKey = activeModel.provider; // gemini, deepseek, openai - matches SettingsModal
      const savedKeys = JSON.parse(localStorage.getItem('llm_keys_map') || '{}') || {};
      const savedUrls = JSON.parse(localStorage.getItem('llm_urls_map') || '{}') || {};
      const headers = {
        'Content-Type': 'application/json',
        'X-Llm-Provider': activeProvider,
        'X-Llm-Model': activeModel.id,
        'X-Llm-Key': savedKeys[storageKey] || localStorage.getItem('llm_key') || '',
        'X-Llm-Base-Url': savedUrls[storageKey] || localStorage.getItem('llm_base_url') || ''
      };

      // 3. Send the request
      const response = await axios.post(`${API_BASE}/agent/generate`, {
        topic_id: topicId,
        roster_id: rosterId,
        template_id: selectedTemplateId === 'auto' ? null : selectedTemplateId,
        chat_instruction: finalInstruction
      }, { headers });

      // Add assistant response
      const assistantMessage = {
        id: Date.now().toString(),
        role: 'assistant',
        content: response.data.content || response.data.message || 'Cards generated successfully!',
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      // Add error message
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: 'Sorry, there was an error processing your request.',
        timestamp: new Date().toISOString()
      }]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      right: 0,
      height: '100vh',
      width: '500px',
      backgroundColor: 'white',
      boxShadow: '-2px 0 10px rgba(0,0,0,0.1)',
      display: 'flex',
      flexDirection: 'column',
      zIndex: 1001
    }}>
      {/* Header */}
      <div style={{
        padding: '20px',
        borderBottom: '1px solid #e0e0e0',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        backgroundColor: '#f8f9fa'
      }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 'bold' }}>
            Grammar: {topicName || topicId}
          </h3>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#666' }}>
            Contextual Copilot
          </p>
        </div>
        <button
          onClick={onClose}
          style={{
            border: 'none',
            background: 'none',
            fontSize: '24px',
            cursor: 'pointer',
            color: '#666',
            padding: '0',
            width: '32px',
            height: '32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          ×
        </button>
      </div>

      {/* The Flight Deck (Controls) */}
      <div style={{
        padding: '16px',
        borderBottom: '1px solid #e0e0e0',
        backgroundColor: '#f8f9fa'
      }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 'bold', marginBottom: '4px' }}>
              Template:
            </label>
            <select
              value={selectedTemplateId || 'auto'}
              onChange={(e) => setSelectedTemplateId(e.target.value)}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                fontSize: '14px'
              }}
              disabled={templates.length === 0}
            >
              <option value="auto">🪄 Automatic (AI decides)</option>
              {templates.length === 0 ? (
                <option value="">Loading templates...</option>
              ) : (
                templates.map(template => (
                  <option key={template.id} value={template.id}>
                    {template.name} {template.description ? `- ${template.description}` : ''}
                  </option>
                ))
              )}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 'bold', marginBottom: '4px' }}>
              AI Model:
            </label>
            <select
              value={selectedCardModel || ''}
              onChange={(e) => {
                const newModel = e.target.value;
                setSelectedCardModel(newModel);
                localStorage.setItem('selectedCardModel', newModel);
                console.log('✅ Model changed to:', newModel);
              }}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                fontSize: '14px'
              }}
              disabled={availableModels.card_models.length === 0}
            >
              {availableModels.card_models.length === 0 ? (
                <option value="">Loading models...</option>
              ) : (
                availableModels.card_models.map(model => (
                  <option key={model.id} value={model.id}>
                    {model.name} ({model.provider})
                  </option>
                ))
              )}
            </select>
          </div>
        </div>
      </div>

      {/* Chat Area */}
      <div className="chat-messages" ref={messagesContainerRef}>
        {loading ? (
          <div className="welcome-message">
            Loading chat history...
          </div>
        ) : messages.length === 0 ? (
          <div className="welcome-message">
            <p>No messages yet. Start a conversation to generate Anki cards!</p>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id || msg.timestamp} className={`message ${msg.role}`}>
              <div className="message-content" style={{maxWidth: msg.role === 'user' ? '70%' : '75%'}}>
                {msg.content}
                <div className="message-time">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))
        )}
        {sending && (
          <div className="message assistant">
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Action Area */}
      <form className="chat-input" onSubmit={(e) => { e.preventDefault(); handleGenerate(); }}>
        <div style={{ marginRight: '8px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <label style={{ fontSize: '0.65rem', color: '#888', marginBottom: '2px', textAlign: 'center' }}>Qty</label>
          <input
            type="number"
            min="1"
            max="20"
            value={quantity}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10);
              setQuantity(isNaN(v) ? 5 : Math.min(20, Math.max(1, v)));
            }}
            placeholder="5"
            style={{
              width: '45px',
              padding: '6px',
              borderRadius: '6px',
              border: '1px solid #ddd',
              textAlign: 'center',
              fontSize: '0.9rem'
            }}
          />
        </div>
        <input
          type="text"
          value={userInput}
          onChange={(e) => setUserInput(e.target.value)}
          onKeyPress={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleGenerate();
            }
          }}
          placeholder="Instructions (optional)..."
          disabled={sending || !selectedTemplateId}
        />
        <button
          type="submit"
          disabled={sending || !selectedTemplateId}
          className="btn"
        >
          {sending ? 'Generating...' : 'Generate'}
        </button>
      </form>
    </div>
  );
};

export default TopicChat;
