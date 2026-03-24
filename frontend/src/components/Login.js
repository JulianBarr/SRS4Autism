import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLanguage } from '../i18n/LanguageContext';
import { cloudApi } from '../utils/api';
import './Login.css';

function Login({ onLoginSuccess }) {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // standard OAuth2 password flow uses form-urlencoded
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const response = await cloudApi.post('/auth/login', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      if (response.data && response.data.access_token) {
        localStorage.setItem('access_token', response.data.access_token);
        if (response.data.user) {
          localStorage.setItem('user_info', JSON.stringify(response.data.user));
        }
        // Decode JWT to get user ID or just let subsequent requests use it
        // Call onLoginSuccess for App.js to update auth state, then navigate based on role
        onLoginSuccess(response.data.access_token, response.data.user);
        if (response.data.user && response.data.user.role === 'PARENT') {
          navigate('/parent');
        } else {
          navigate('/');
        }
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <div className="login-header">
          <img src="/cuma_logo.png" alt="CUMA Logo" className="login-logo" onError={(e) => { e.target.onerror = null; e.target.src = ''; e.target.style.display = 'none'; }} />
          <h2>Welcome to Curious Mario</h2>
        </div>
        
        {error && <div className="login-error">{error}</div>}
        
        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="teacher_a@qcq.com"
              required
              autoComplete="email"
            />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="cuma123"
              required
              autoComplete="current-password"
            />
          </div>
          <button type="submit" className="login-button" disabled={loading}>
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>
        
        <div className="login-footer">
          <p>Default Accounts:</p>
          <ul style={{textAlign: 'left', fontSize: '12px', color: '#666'}}>
            <li>Teacher: teacher_a@qcq.com / cuma123</li>
            <li>Parent: parent_b@test.com / cuma123</li>
            <li>Agent: ai@cuma.com / cuma123</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default Login;
