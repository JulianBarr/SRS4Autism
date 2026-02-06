import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const TopicChat = ({ topicId, topicName, rosterId, onClose }) => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [userInput, setUserInput] = useState('');
  const [roster, setRoster] = useState(rosterId || 'yiming');
  const [template, setTemplate] = useState('Basic Grammar Card');
  const [quantity, setQuantity] = useState(5);
  const messagesEndRef = useRef(null);

  // Load chat history on mount
  useEffect(() => {
    const loadHistory = async () => {
      if (!topicId || !roster) return;
      
      setLoading(true);
      try {
        const response = await axios.get(`${API_BASE}/chat/topic/history`, {
          params: { topic_id: topicId, roster_id: roster }
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
  }, [topicId, roster]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleGenerate = async () => {
    if (!userInput.trim() || !topicId || !roster) return;

    const userMessage = userInput.trim();
    setUserInput('');
    setSending(true);

    // Add user message to UI immediately
    const newUserMessage = {
      role: 'user',
      content: userMessage,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, newUserMessage]);

    try {
      const response = await axios.post(`${API_BASE}/chat/topic/message`, {
        topic_id: topicId,
        roster_id: roster,
        content: userMessage,
        template: template,
        quantity: quantity
      });

      // Add assistant response
      setMessages(prev => [...prev, response.data]);
    } catch (error) {
      console.error('Error sending message:', error);
      // Add error message
      setMessages(prev => [...prev, {
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
        <div style={{ marginBottom: '12px' }}>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 'bold', marginBottom: '4px' }}>
            Roster:
          </label>
          <select
            value={roster}
            onChange={(e) => setRoster(e.target.value)}
            style={{
              width: '100%',
              padding: '8px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '14px'
            }}
          >
            <option value="yiming">Yiming</option>
            <option value="general">General</option>
          </select>
        </div>
        <div style={{ marginBottom: '12px' }}>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 'bold', marginBottom: '4px' }}>
            Template:
          </label>
          <select
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
            style={{
              width: '100%',
              padding: '8px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '14px'
            }}
          >
            <option value="Basic Grammar Card">Basic Grammar Card</option>
            <option value="Cloze">Cloze</option>
          </select>
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 'bold', marginBottom: '4px' }}>
            Quantity:
          </label>
          <input
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(parseInt(e.target.value) || 5)}
            min="1"
            max="20"
            style={{
              width: '100%',
              padding: '8px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '14px'
            }}
          />
        </div>
      </div>

      {/* Chat Area */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '20px',
        backgroundColor: '#fafafa'
      }}>
        {loading ? (
          <div style={{ textAlign: 'center', color: '#666', padding: '20px' }}>
            Loading chat history...
          </div>
        ) : messages.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#666', padding: '20px' }}>
            <p>No messages yet. Start a conversation to generate Anki cards!</p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={idx}
              style={{
                marginBottom: '16px',
                display: 'flex',
                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start'
              }}
            >
              <div style={{
                maxWidth: '75%',
                padding: '12px 16px',
                borderRadius: '12px',
                backgroundColor: msg.role === 'user' ? '#007AFF' : '#e0e0e0',
                color: msg.role === 'user' ? 'white' : '#333',
                fontSize: '14px',
                lineHeight: '1.5'
              }}>
                {msg.content}
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Action Area */}
      <div style={{
        padding: '16px',
        borderTop: '1px solid #e0e0e0',
        backgroundColor: 'white'
      }}>
        <div style={{ display: 'flex', gap: '8px' }}>
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
            style={{
              flex: 1,
              padding: '10px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '14px'
            }}
            disabled={sending}
          />
          <button
            onClick={handleGenerate}
            disabled={sending || !userInput.trim()}
            style={{
              padding: '10px 20px',
              backgroundColor: sending ? '#ccc' : '#007AFF',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              fontSize: '14px',
              fontWeight: 'bold',
              cursor: sending || !userInput.trim() ? 'not-allowed' : 'pointer'
            }}
          >
            {sending ? 'Generating...' : 'Generate'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default TopicChat;
