import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './Library.css';
import LibraryItem from './LibraryItem';

function Library({ user, onLogout }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('all');
  const [allUsers, setAllUsers] = useState([]);

  useEffect(() => {
    fetchLibrary();
    fetchUsers();
  }, []);

  const fetchLibrary = async () => {
    try {
      setLoading(true);
      setError('');
      const res = await axios.get('/api/library');
      setItems(res.data.items);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load library');
    } finally {
      setLoading(false);
    }
  };

  const fetchUsers = async () => {
    try {
      const res = await axios.get('/api/users');
      setAllUsers(res.data.users);
    } catch (err) {
      console.error('Failed to fetch users:', err);
    }
  };

  const handleToggleWatched = async (plex_id, currentlyWatched) => {
    try {
      if (currentlyWatched) {
        await axios.delete(`/api/watched/${plex_id}`);
      } else {
        await axios.post('/api/watched', { plex_id });
      }
      fetchLibrary();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to update watched status');
    }
  };

  const filterItems = () => {
    if (filter === 'watched') return items.filter(item => item.watched_by_me);
    if (filter === 'movies') return items.filter(item => item.type === 'movie');
    if (filter === 'shows') return items.filter(item => item.type === 'show');
    if (filter === 'ready') return items.filter(item => item.watch_count === allUsers.length);
    return items;
  };

  const filteredItems = filterItems();
  const totalUsers = allUsers.length;

  return (
    <div className="library">
      <header className="library-header">
        <div className="header-content">
          <h1>🎬 Plex Watch Tracker</h1>
          <div className="user-info">
            <span className="username">👤 {user.username}</span>
            <button onClick={onLogout} className="logout-btn">Logout</button>
          </div>
        </div>
      </header>

      <div className="library-controls">
        <div className="filter-buttons">
          <button
            className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All ({items.length})
          </button>
          <button
            className={`filter-btn ${filter === 'movies' ? 'active' : ''}`}
            onClick={() => setFilter('movies')}
          >
            Movies ({items.filter(i => i.type === 'movie').length})
          </button>
          <button
            className={`filter-btn ${filter === 'shows' ? 'active' : ''}`}
            onClick={() => setFilter('shows')}
          >
            Shows ({items.filter(i => i.type === 'show').length})
          </button>
          <button
            className={`filter-btn ${filter === 'watched' ? 'active' : ''}`}
            onClick={() => setFilter('watched')}
          >
            I've Watched ({items.filter(i => i.watched_by_me).length})
          </button>
          <button
            className={`filter-btn ${filter === 'ready' ? 'active' : ''}`}
            onClick={() => setFilter('ready')}
          >
            Ready to Delete ✓
          </button>
        </div>

        <button onClick={fetchLibrary} className="refresh-btn">
          🔄 Sync Library
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {loading ? (
        <div className="loading">Loading library...</div>
      ) : filteredItems.length === 0 ? (
        <div className="empty-state">
          <p>📭 No items to display</p>
        </div>
      ) : (
        <div className="library-grid">
          {filteredItems.map(item => (
            <LibraryItem
              key={item.plex_id}
              item={item}
              isWatched={item.watched_by_me}
              watchCount={item.watch_count}
              totalUsers={totalUsers}
              onToggleWatched={handleToggleWatched}
              allUsers={allUsers}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default Library;
