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
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Load chat history on mount
    loadChatHistory();
    loadNoteTypes();
    loadTemplates();
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
      setNoteTypes(['Basic', 'Basic (and reversed card)', 'Cloze', 'Interactive Cloze']);
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
      mentionables.push({
        type: 'profile',
        display: profile.name,
        value: profile.id || profile.name,  // Use ID if available, fallback to name
        searchTerms: [profile.name.toLowerCase(), profile.id?.toLowerCase() || '']
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
      
      // Check if it's a typed mention (@word:value)
      if (query.includes(':')) {
        setShowSuggestions(false);
        return;
      }
      
      // Filter suggestions based on query
      const allSuggestions = getAllMentionables();
      const filtered = allSuggestions.filter(item => {
        return item.searchTerms.some(term => 
          term.includes(query.toLowerCase())
        );
      });
      
      if (filtered.length > 0 && query.length > 0) {
        setSuggestions(filtered);
        setShowSuggestions(true);
        setActiveSuggestionIndex(0);
      } else {
        setShowSuggestions(false);
      }
    } else {
      setShowSuggestions(false);
    }
  };

  const selectSuggestion = (suggestion) => {
    const textBeforeCursor = input.substring(0, cursorPosition);
    const atIndex = textBeforeCursor.lastIndexOf('@');
    
    if (atIndex !== -1) {
      const before = input.substring(0, atIndex);
      const after = input.substring(cursorPosition);
      
      // Special handling for @roster - just insert @roster without :value
      let newInput;
      if (suggestion.type === 'roster') {
        newInput = `${before}@roster ${after}`;
      } else {
        newInput = `${before}@${suggestion.type}:${suggestion.value} ${after}`;
      }
      
      setInput(newInput);
      setShowSuggestions(false);
      
      // Focus back on input
      setTimeout(() => {
        if (inputRef.current) {
          const newCursorPos = suggestion.type === 'roster' 
            ? atIndex + 8  // length of "@roster "
            : atIndex + suggestion.type.length + suggestion.value.length + 3;
          inputRef.current.focus();
          inputRef.current.setSelectionRange(newCursorPos, newCursorPos);
        }
      }, 0);
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

    const userMessage = {
      id: Date.now().toString(),
      content: input,
      role: 'user',
      timestamp: new Date().toISOString(),
      mentions: extractMentions(input)
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Send message to backend
      const response = await axios.post(`${API_BASE}/chat`, userMessage);
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
    
    // Only extract @profile:ID patterns (actual profile mentions)
    // Don't extract @template:, @word:, @roster, etc. - those are context tags, not mentions
    const profilePattern = /(?:^|[\s,])@profile:([^\s,]+)/g;
    let match;
    while ((match = profilePattern.exec(text)) !== null) {
      mentions.push(match[1]); // Extract the ID/value after @profile:
    }

    // Also check for profile names/IDs directly mentioned (backwards compatibility)
    profiles.forEach(profile => {
      // Check if profile ID or name is mentioned
      if (profile.id && text.includes(profile.id)) {
        mentions.push(profile.id);
      } else if (text.toLowerCase().includes(profile.name.toLowerCase())) {
        mentions.push(profile.id || profile.name);
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

  const formatMessage = (message) => {
    let content = message.content;
    
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
        {messages.length > 0 && (
          <button onClick={handleClearHistory} className="btn btn-secondary">
            {t('clearHistory')}
          </button>
        )}
      </div>
      
      <div className="mention-suggestions">
        <h4>{t('availableMentions')}</h4>
        
        {/* Group mentionables by type */}
        {['profile', 'roster', 'character', 'template', 'notetype'].map(type => {
          const items = getAllMentionables().filter(m => m.type === type);
          if (items.length === 0) return null;
          
          const labels = {
            profile: t('childProfile'),
            roster: 'Character Roster (All)',
            character: 'Individual Character',
            template: 'Prompt Template',
            notetype: 'Note Type'
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
                  <span key={item.value} className="mention-tag">
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

      <div className="chat-container">
        <div className="chat-messages">
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
                <div className="message-content">
                  <div 
                    dangerouslySetInnerHTML={{ 
                      __html: formatMessage(message) 
                    }} 
                  />
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
    </div>
  );
};

export default ChatAssistant;

