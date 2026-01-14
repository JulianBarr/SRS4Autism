import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { useLanguage } from '../i18n/LanguageContext';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const ChatAssistant = ({ profiles, onNewCard }) => {
  const { t, language } = useLanguage();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(0);
  const [cursorPosition, setCursorPosition] = useState(0);
  const [noteTypes, setNoteTypes] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [lastIntent, setLastIntent] = useState(null);
  const [expandedMentionGroups, setExpandedMentionGroups] = useState({});
  const [expandedMessages, setExpandedMessages] = useState(new Set());
  const [availableModels, setAvailableModels] = useState({ card_models: [], image_models: [] });
  const [selectedCardModel, setSelectedCardModel] = useState(null);
  const [selectedImageModel, setSelectedImageModel] = useState(null);
  const [showModelSettings, setShowModelSettings] = useState(false);
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const inputRef = useRef(null);

  const getProfileSlug = (profile) => {
    if (!profile) return 'profile';
    const rawId = (profile.id || '').toString().trim();
    if (rawId) {
      return rawId.toLowerCase().replace(/^@+/, '');
    }
    const generated = generateSlug(profile.name || '');
    return generated ? generated.toLowerCase().replace(/^@+/, '') : 'profile';
  };

  const scrollToBottom = () => {
    // Only scroll within the chat messages container, not the whole page
    if (messagesContainerRef.current && messagesEndRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    // Only auto-scroll if there are messages and we're not at the top
    if (messages.length > 0) {
      scrollToBottom();
    }
  }, [messages]);

  useEffect(() => {
    const handleCardIdClicked = (event) => {
      const cardId = event.detail;
      if (!cardId) return;
      setInput(prev => {
        const prefix = prev ? `${prev.trimEnd()} ` : '';
        return `${prefix}${cardId} `;
      });
      setTimeout(() => {
        inputRef.current?.focus();
        const pos = inputRef.current?.value.length ?? 0;
        inputRef.current?.setSelectionRange(pos, pos);
      }, 0);
    };

    window.addEventListener('card-id-clicked', handleCardIdClicked);
    return () => window.removeEventListener('card-id-clicked', handleCardIdClicked);
  }, []);

  useEffect(() => {
    // Load chat history on mount
    loadChatHistory();
    loadNoteTypes();
    loadTemplates();
    loadAvailableModels();
  }, []);

  const loadChatHistory = async () => {
    try {
      const response = await axios.get(`${API_BASE}/chat/history`);
      setMessages(response.data);
    } catch (error) {
      console.error('Error loading chat history:', error);
    }
  };

  const loadNoteTypes = async () => {
    try {
      const response = await axios.get(`${API_BASE}/anki/note-types`);
      setNoteTypes(response.data.note_types || []);
      console.log('Loaded note types:', response.data.note_types);
    } catch (error) {
      console.error('Error loading note types:', error);
      // Fallback to common note types
      setNoteTypes([
        'CUMA - Basic',
        'CUMA - Basic (and reversed card)',
        'CUMA - Cloze',
        'CUMA - Interactive Cloze'
      ]);
    }
  };

  const loadTemplates = async () => {
    try {
      const response = await axios.get(`${API_BASE}/templates`);
      setTemplates(response.data || []);
      console.log('Loaded templates:', response.data);
    } catch (error) {
      console.error('Error loading templates:', error);
      setTemplates([]);
    }
  };

  const loadAvailableModels = async () => {
    try {
      const response = await axios.get(`${API_BASE}/config/models`);
      setAvailableModels(response.data || { card_models: [], image_models: [] });
      
      // Load saved selections from localStorage
      const savedCardModel = localStorage.getItem('selectedCardModel');
      const savedImageModel = localStorage.getItem('selectedImageModel');
      
      // Set default selections (first model in each category) or use saved
      if (response.data?.card_models?.length > 0) {
        if (savedCardModel && response.data.card_models.find(m => m.id === savedCardModel)) {
          setSelectedCardModel(savedCardModel);
        } else if (!selectedCardModel) {
          const defaultModel = response.data.card_models[0].id;
          setSelectedCardModel(defaultModel);
          localStorage.setItem('selectedCardModel', defaultModel);
        }
      }
      if (response.data?.image_models?.length > 0) {
        if (savedImageModel && response.data.image_models.find(m => m.id === savedImageModel)) {
          setSelectedImageModel(savedImageModel);
        } else if (!selectedImageModel) {
          const defaultModel = response.data.image_models[0].id;
          setSelectedImageModel(defaultModel);
          localStorage.setItem('selectedImageModel', defaultModel);
        }
      }
    } catch (error) {
      console.error('Error loading available models:', error);
      setAvailableModels({ card_models: [], image_models: [] });
    }
  };

  const handleClearHistory = async () => {
    if (window.confirm('Are you sure you want to clear chat history?')) {
      try {
        await axios.delete(`${API_BASE}/chat/history`);
        setMessages([]);
      } catch (error) {
        console.error('Error clearing chat history:', error);
      }
    }
  };

  // Helper function to generate slugs (same logic as backend)
  const generateSlug = (str) => {
    return str
      .toLowerCase()
      .replace(/\s+/g, '-')
      .replace(/[^\w\u4e00-\u9fff-]/g, '')
      .replace(/-+/g, '-')
      .trim();
  };

  const getAllMentionables = () => {
    const mentionables = [];
    console.log('[DEBUG] getAllMentionables:', {
      templates: templates,
      templatesCount: templates?.length || 0,
      noteTypesCount: noteTypes?.length || 0,
      profilesCount: profiles?.length || 0
    });
    
    // Add profiles (use ID as value, name for display/search)
    profiles.forEach(profile => {
      const profileSlug = getProfileSlug(profile);
      mentionables.push({
        type: 'profile',
        display: profile.name,
        value: profileSlug,
        searchTerms: [
          profile.name.toLowerCase(),
          profileSlug,
          profile.id?.toLowerCase() || ''
        ]
      });
    });
    
    // Add characters from all profiles
    const allCharacters = new Set();
    profiles.forEach(profile => {
      if (profile.character_roster) {
        profile.character_roster.forEach(char => allCharacters.add(char));
      }
    });
    
    allCharacters.forEach(char => {
      const slug = generateSlug(char);
      mentionables.push({
        type: 'character',
        display: char,
        value: slug,  // Use slug as the value for mentions
        searchTerms: [char.toLowerCase(), slug.toLowerCase()]
      });
    });
    
    // Add note types
    noteTypes.forEach(noteType => {
      // Generate slug for note type (handles spaces, special chars, etc.)
      const slug = generateSlug(noteType);
      mentionables.push({
        type: 'notetype',
        display: noteType,
        value: slug,  // Use slug as the value for mentions
        searchTerms: [noteType.toLowerCase(), slug.toLowerCase()]
      });
    });
    
    // Add templates
    templates.forEach(template => {
      // Generate slug for template name
      const slug = generateSlug(template.name);
      mentionables.push({
        type: 'template',
        display: `${template.name} - ${template.description || 'Custom template'}`,
        value: slug,  // Use slug as the value for mentions
        searchTerms: [template.name.toLowerCase(), slug.toLowerCase(), template.description?.toLowerCase() || '']
      });
    });
    
    // Add @roster special mention
    mentionables.push({
      type: 'roster',
      display: 'roster (use entire character roster)',
      value: 'roster',
      searchTerms: ['roster', 'characters', 'all']
    });
    
    return mentionables;
  };

  const handleInputChange = (e) => {
    const value = e.target.value;
    const cursorPos = e.target.selectionStart;
    
    setInput(value);
    setCursorPosition(cursorPos);
    
    // Check if user is typing a mention
    const textBeforeCursor = value.substring(0, cursorPos);
    const atIndex = textBeforeCursor.lastIndexOf('@');
    
    if (atIndex !== -1 && atIndex === cursorPos - 1) {
      // User just typed @, show all suggestions
      const allSuggestions = getAllMentionables();
      setSuggestions(allSuggestions);
      setShowSuggestions(true);
      setActiveSuggestionIndex(0);
    } else if (atIndex !== -1) {
      // User is typing after @
      const query = textBeforeCursor.substring(atIndex + 1);

      const colonIndex = query.indexOf(':');

      if (colonIndex === -1) {
        // Filter suggestions based on query (mention type or display)
        const allSuggestions = getAllMentionables();
        const filtered = allSuggestions.filter(item => {
          return item.searchTerms.some(term =>
            term.includes(query.toLowerCase())
          ) || item.type.toLowerCase().startsWith(query.toLowerCase());
        });

        if (filtered.length > 0) {
          setSuggestions(filtered);
          setShowSuggestions(true);
          setActiveSuggestionIndex(0);
        } else {
          setShowSuggestions(false);
        }
      } else {
        // Query contains a colon -> user is specifying @type:value
        const typePart = query.substring(0, colonIndex).toLowerCase();
        const valuePart = query.substring(colonIndex + 1).toLowerCase();

        const allSuggestions = getAllMentionables();
        const typeMatches = allSuggestions.filter(item =>
          item.type.toLowerCase().startsWith(typePart)
        );

        if (typeMatches.length === 0) {
          setShowSuggestions(false);
          return;
        }

        const filteredByValue = valuePart.length === 0
          ? typeMatches
          : typeMatches.filter(item =>
              item.searchTerms.some(term => term.includes(valuePart))
            );

        if (filteredByValue.length > 0) {
          setSuggestions(filteredByValue);
          setShowSuggestions(true);
          setActiveSuggestionIndex(0);
        } else {
          setShowSuggestions(false);
        }
      }
    } else {
      setShowSuggestions(false);
    }
  };

  const insertMentionText = (mentionText, insertionStart, insertionEnd) => {
    const before = input.substring(0, insertionStart);
    const after = input.substring(insertionEnd);
    const newInput = `${before}${mentionText}${after}`;
    setInput(newInput);
    setShowSuggestions(false);

    setTimeout(() => {
      if (inputRef.current) {
        const newCursorPos = insertionStart + mentionText.length;
        inputRef.current.focus();
        inputRef.current.setSelectionRange(newCursorPos, newCursorPos);
      }
    }, 0);
  };

  const selectSuggestion = (suggestion) => {
    const textBeforeCursor = input.substring(0, cursorPosition);
    const atIndex = textBeforeCursor.lastIndexOf('@');
    
    if (atIndex !== -1) {
      const before = input.substring(0, atIndex);
      const after = input.substring(cursorPosition);
      
      // Special handling for @roster - just insert @roster without :value
      let mentionText;
      if (suggestion.type === 'roster') {
        mentionText = '@roster ';
      } else {
        mentionText = `@${suggestion.type}:${suggestion.value} `;
      }
      insertMentionText(mentionText, atIndex, cursorPosition);
    } else {
      if (inputRef.current) {
        const selectionStart = inputRef.current.selectionStart ?? input.length;
        const selectionEnd = inputRef.current.selectionEnd ?? selectionStart;
        const mentionText = suggestion.type === 'roster'
          ? '@roster '
          : `@${suggestion.type}:${suggestion.value} `;
        insertMentionText(mentionText, selectionStart, selectionEnd);
      } else {
        const mentionText = suggestion.type === 'roster'
          ? '@roster '
          : `@${suggestion.type}:${suggestion.value} `;
        insertMentionText(mentionText, input.length, input.length);
      }
    }
  };

  const handleKeyDown = (e) => {
    if (!showSuggestions) return;
    
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveSuggestionIndex(prev => 
        prev < suggestions.length - 1 ? prev + 1 : 0
      );
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveSuggestionIndex(prev => 
        prev > 0 ? prev - 1 : suggestions.length - 1
      );
    } else if (e.key === 'Enter' && suggestions.length > 0) {
      e.preventDefault();
      selectSuggestion(suggestions[activeSuggestionIndex]);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    // Build config object if models are selected
    const config = {};
    if (selectedCardModel) {
      config.card_model = selectedCardModel;
    }
    if (selectedImageModel) {
      config.image_model = selectedImageModel;
    }

    const userMessage = {
      id: Date.now().toString(),
      content: input,
      role: 'user',
      timestamp: new Date().toISOString(),
      mentions: extractMentions(input),
      ...(Object.keys(config).length > 0 && { config })
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Send message to backend
      const llmProvider = localStorage.getItem('llm_provider') || 'gemini';
      const llmKey = localStorage.getItem('llm_key') || '';
      const llmBaseUrl = localStorage.getItem('llm_base_url') || '';

      // Prepare headers with LLM configuration
      const headers = {
        'X-LLM-Provider': llmProvider,
        'X-LLM-Key': llmKey,
        'X-LLM-Base-URL': llmBaseUrl
      };

      const response = await axios.post(`${API_BASE}/chat`, userMessage, { headers });
      const assistantMessage = response.data;
      
      // Check if the response contains intent information
      if (response.data.intent) {
        setLastIntent(response.data.intent);
      }
      
      setMessages(prev => [...prev, assistantMessage]);

      // Trigger parent component to refresh cards
      // The backend already generated and saved cards
      if (onNewCard) {
        // Signal to parent that new cards may be available
        onNewCard({ refresh: true });
      }
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        content: 'Sorry, there was an error processing your message.',
        role: 'assistant',
        timestamp: new Date().toISOString(),
        mentions: []
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const extractMentions = (text) => {
    const mentions = [];
    const normalizeValue = (profile) => getProfileSlug(profile);
    
    // Only extract @profile:ID patterns (actual profile mentions)
    // Don't extract @template:, @word:, @roster, etc. - those are context tags, not mentions
    const profilePattern = /(?:^|[\s,])@profile:([^\s,]+)/g;
    let match;
    while ((match = profilePattern.exec(text)) !== null) {
      mentions.push(match[1]); // Extract the ID/value after @profile:
    }

    // Also check for profile names/IDs directly mentioned (backwards compatibility)
    profiles.forEach(profile => {
      const slug = normalizeValue(profile);
      // Check if profile ID or name is mentioned
      if (profile.id && text.includes(profile.id)) {
        mentions.push(profile.id);
      } else if (text.includes(slug)) {
        mentions.push(slug);
      } else if (profile.name && text.toLowerCase().includes(profile.name.toLowerCase())) {
        mentions.push(slug);
      }
    });

    return [...new Set(mentions)]; // Remove duplicates
  };

  const generateCardsFromConversation = async (prompt, mentions) => {
    try {
      // This would integrate with the AI agent to generate cards
      // For now, create a simple example card
      const exampleCard = {
        id: Date.now().toString(),
        front: `What is ${prompt.split(' ').slice(0, 3).join(' ')}?`,
        back: `This is about ${prompt.split(' ').slice(0, 3).join(' ')}`,
        card_type: 'basic',
        tags: mentions,
        created_at: new Date().toISOString(),
        status: 'pending'
      };

      // Send to backend
      await axios.post(`${API_BASE}/cards`, exampleCard);
      onNewCard(exampleCard);
    } catch (error) {
      console.error('Error generating cards:', error);
    }
  };

  const toggleMentionGroup = (type) => {
    setExpandedMentionGroups(prev => ({
      ...prev,
      [type]: !prev[type]
    }));
  };

  const toggleMessageExpand = (messageId) => {
    setExpandedMessages(prev => {
      const next = new Set(prev);
      if (next.has(messageId)) {
        next.delete(messageId);
      } else {
        next.add(messageId);
      }
      return next;
    });
  };

  const formatMessage = (message, isExpanded = false) => {
    let content = message.content;
    
    // For card generation messages, show only first line when collapsed
    const isCardGeneration = content.includes('✨ 成功为您生成了');
    if (isCardGeneration && !isExpanded) {
      const firstLineEnd = content.indexOf('\n');
      if (firstLineEnd > 0) {
        content = content.substring(0, firstLineEnd);
      }
    }
    
    // Helper function to escape special regex characters
    const escapeRegex = (str) => {
      return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    };
    
    // Highlight mentions
    message.mentions.forEach(mention => {
      const escapedMention = escapeRegex(mention);
      const regex = new RegExp(`@?${escapedMention}`, 'gi');
      content = content.replace(regex, `<span class="mention">@${mention}</span>`);
    });

    // Convert markdown images to HTML
    content = content.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width: 100%; height: auto; border-radius: 8px; margin: 10px 0; border: 1px solid #ddd;" />');

    return content;
  };

  return (
    <div className="card">
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <div>
          <h2>{t('chatTitle')}</h2>
          <p>{t('chatDescription')}</p>
          {lastIntent && (
            <div className="intent-indicator">
              <span className="intent-badge intent-{lastIntent.intent}">
                {lastIntent.intent === 'conversation' && '💬 Chat'}
                {lastIntent.intent === 'card_generation' && '🎴 Cards'}
                {lastIntent.intent === 'image_generation' && '🖼️ Images'}
                {lastIntent.intent === 'card_update' && '✏️ Update'}
              </span>
              <span className="intent-confidence">
                {Math.round(lastIntent.confidence * 100)}% confidence
              </span>
            </div>
          )}
        </div>
        <div style={{display: 'flex', gap: '10px', alignItems: 'center'}}>
          <button 
            onClick={() => setShowModelSettings(!showModelSettings)} 
            className="btn btn-secondary"
            style={{fontSize: '0.9em', padding: '6px 12px'}}
            title="AI Model Settings"
          >
            ⚙️ Models
          </button>
          {messages.length > 0 && (
            <button onClick={handleClearHistory} className="btn btn-secondary clear-history-btn">
              {t('clearHistory')}
            </button>
          )}
        </div>
      </div>
      
      {/* Model Selection Panel */}
      {showModelSettings && (
        <div style={{
          marginBottom: '15px',
          padding: '15px',
          backgroundColor: '#f8f9fa',
          borderRadius: '8px',
          border: '1px solid #dee2e6'
        }}>
          <h4 style={{marginTop: 0, marginBottom: '10px'}}>🤖 AI Model Configuration</h4>
          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px'}}>
            <div>
              <label style={{display: 'block', marginBottom: '5px', fontWeight: 'bold', fontSize: '0.9em'}}>
                Card Generation Model:
              </label>
              <select
                value={selectedCardModel || ''}
                onChange={(e) => {
                  setSelectedCardModel(e.target.value);
                  localStorage.setItem('selectedCardModel', e.target.value);
                }}
                style={{
                  width: '100%',
                  padding: '8px',
                  borderRadius: '4px',
                  border: '1px solid #ced4da',
                  fontSize: '0.9em'
                }}
              >
                {availableModels.card_models.map(model => (
                  <option key={model.id} value={model.id}>
                    {model.name} ({model.provider})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label style={{display: 'block', marginBottom: '5px', fontWeight: 'bold', fontSize: '0.9em'}}>
                Image Generation Model:
              </label>
              <select
                value={selectedImageModel || ''}
                onChange={(e) => {
                  setSelectedImageModel(e.target.value);
                  localStorage.setItem('selectedImageModel', e.target.value);
                }}
                style={{
                  width: '100%',
                  padding: '8px',
                  borderRadius: '4px',
                  border: '1px solid #ced4da',
                  fontSize: '0.9em'
                }}
              >
                {availableModels.image_models.map(model => (
                  <option key={model.id} value={model.id}>
                    {model.name} ({model.provider})
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div style={{marginTop: '10px', fontSize: '0.85em', color: '#6c757d'}}>
            <strong>Selected:</strong> {selectedCardModel && (
              <span>Card: {availableModels.card_models.find(m => m.id === selectedCardModel)?.name || selectedCardModel}</span>
            )}
            {selectedCardModel && selectedImageModel && ' | '}
            {selectedImageModel && (
              <span>Image: {availableModels.image_models.find(m => m.id === selectedImageModel)?.name || selectedImageModel}</span>
            )}
            {!selectedCardModel && !selectedImageModel && 'Using default models'}
          </div>
        </div>
      )}
      
      <div className="chat-container">
        <div className="chat-messages" ref={messagesContainerRef}>
          {messages.length === 0 ? (
            <div className="welcome-message">
              <p>{t('welcomeMessage')}</p>
              <p>{t('tryAsking')}</p>
              <ul>
                <li>"Create cards about colors for @Alex"</li>
                <li>"Teach @Emma about animals"</li>
                <li>"Make flashcards for numbers"</li>
              </ul>
            </div>
          ) : (
            messages.map(message => (
              <div key={message.id} className={`message ${message.role}`}>
                <div 
                  className={`message-content ${expandedMessages.has(message.id) ? 'expanded' : 'collapsible'}`}
                  style={{maxWidth: message.role === 'user' ? '70%' : '75%'}}
                >
                  <div 
                    dangerouslySetInnerHTML={{ 
                      __html: formatMessage(message, expandedMessages.has(message.id)) 
                    }} 
                  />
                  {(message.content.length > 400 || message.content.includes('✨ 成功为您生成了')) && (
                    <div 
                      className="show-more-toggle"
                      onClick={() => toggleMessageExpand(message.id)}
                    >
                      {message.content.includes('✨ 成功为您生成了') ? (
                        expandedMessages.has(message.id) ? '收起 ▲' : '查看详情 ▼'
                      ) : (
                        expandedMessages.has(message.id) ? 'Show less ▲' : 'Show more ▼'
                      )}
                    </div>
                  )}
                  <div className="message-time">
                    {new Date(message.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))
          )}
          {isLoading && (
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

        <form className="chat-input" onSubmit={handleSendMessage}>
          <div style={{position: 'relative', flex: 1}}>
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder={language === 'en' ? "Ask me to create flashcards... (type @ for mentions)" : "请告诉我为您创建闪卡... (输入 @ 查看提及)"}
              disabled={isLoading}
              style={{width: '100%'}}
            />
            
            {/* Autocomplete dropdown */}
            {showSuggestions && suggestions.length > 0 && (
              <div className="mention-dropdown">
                {suggestions.map((suggestion, index) => (
                  <div
                    key={`${suggestion.type}-${suggestion.value}`}
                    className={`mention-dropdown-item ${index === activeSuggestionIndex ? 'active' : ''}`}
                    onClick={() => selectSuggestion(suggestion)}
                    onMouseEnter={() => setActiveSuggestionIndex(index)}
                  >
                    <span className="mention-type-badge">{suggestion.type}</span>
                    <span className="mention-value">{suggestion.display}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <button type="submit" disabled={!input.trim() || isLoading}>
            {t('send')}
          </button>
        </form>
      </div>
      <div className="mention-suggestions">
        <h4>{t('availableMentions')}</h4>
        
        <div className="mention-groups-grid">
        {/* Group mentionables by type */}
        {['profile', 'roster', 'character', 'template', 'notetype'].map(type => {
          const items = getAllMentionables().filter(m => m.type === type);
          if (items.length === 0) return null;
          
          const labels = {
            profile: t('mentionChildProfile'),
            roster: t('mentionRoster'),
            character: t('mentionCharacter'),
            template: t('mentionTemplate'),
            notetype: t('mentionNoteType')
          };
          
          const isExpanded = expandedMentionGroups[type];
          const maxInitial = 3;
          const visibleItems = isExpanded ? items : items.slice(0, maxInitial);
          const hasMore = items.length > maxInitial;
          
          return (
            <div key={type} className="mention-group">
              <strong>{labels[type]}:</strong>
              <div className="mention-items">
                {visibleItems.map(item => (
                  <span 
                    key={`${item.type}-${item.value}`} 
                    className="mention-tag"
                    onClick={() => selectSuggestion(item)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        selectSuggestion(item);
                      }
                    }}
                  >
                    {type === 'roster' ? '@roster' : `@${type}:${item.value}`}
                  </span>
                ))}
                {hasMore && (
                  <span 
                    className="mention-expand-link" 
                    onClick={() => toggleMentionGroup(type)}
                  >
                    {isExpanded ? ' ... less' : ' ... more'}
                  </span>
                )}
              </div>
            </div>
          );
        })}
        </div>
      </div>
    </div>
  );
};

export default ChatAssistant;

