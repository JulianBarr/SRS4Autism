import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const TopicChat = ({ topicId, topicName, profile, onClose }) => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [userInput, setUserInput] = useState('');
  const [templates, setTemplates] = useState([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState(null);
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);

  // Get roster_id from profile (implicit)
  const rosterId = profile?.id || profile?.name || 'yiming';

  // Load templates on mount
  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const response = await axios.get(`${API_BASE}/templates`);
        const templatesList = response.data || [];
        setTemplates(templatesList);
        // Set default template (first one, or filter for Grammar if available)
        if (templatesList.length > 0) {
          const grammarTemplate = templatesList.find(t => 
            t.name?.toLowerCase().includes('grammar') || 
            t.description?.toLowerCase().includes('grammar')
          );
          setSelectedTemplateId(grammarTemplate?.id || templatesList[0].id);
        }
      } catch (error) {
        console.error('Error loading templates:', error);
        setTemplates([]);
      }
    };

    loadTemplates();
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
    if (!userInput.trim() || !topicId || !rosterId || !selectedTemplateId) return;

    const chatInstruction = userInput.trim();
    setUserInput('');
    setSending(true);

    // Add user message to UI immediately
    const newUserMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: chatInstruction,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, newUserMessage]);

    try {
      const response = await axios.post(`${API_BASE}/agent/generate`, {
        topic_id: topicId,
        roster_id: rosterId,
        template_id: selectedTemplateId,
        chat_instruction: chatInstruction
      });

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
        <div>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 'bold', marginBottom: '4px' }}>
            Template:
          </label>
          <select
            value={selectedTemplateId || ''}
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
          placeholder="Enter specific instructions (e.g., 'Use Kung Fu Panda examples')"
          disabled={sending || !selectedTemplateId}
        />
        <button
          type="submit"
          disabled={sending || !userInput.trim() || !selectedTemplateId}
          className="btn"
        >
          {sending ? 'Generating...' : 'Generate'}
        </button>
      </form>
    </div>
  );
};

export default TopicChat;
