import React, { useState } from 'react';
import axios from 'axios';
import './Login.css';

function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await axios.post('/api/auth/login', { username });
      onLogin(res.data.user);
    } catch (err) {
      setError(err.response?.data?.error || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <h1>🎬 Plex Watch Tracker</h1>
        <p className="subtitle">Track what you've watched and remove it when everyone's done</p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">Your Name</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your name (e.g., You, Jeff, Brad)"
              disabled={loading}
              autoFocus
            />
          </div>

          {error && <div className="error">{error}</div>}

          <button type="submit" disabled={loading || !username}>
            {loading ? 'Loading...' : 'Enter'}
          </button>
        </form>

        <div className="info">
          <p>Just enter your name to get started. This app tracks watched movies and shows across your Plex server.</p>
        </div>
      </div>
    </div>
  );
}

export default Login;
