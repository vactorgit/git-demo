import React, { useState } from 'react';
import axios from 'axios';
import './LibraryItem.css';

function LibraryItem({ item, isWatched, watchCount, totalUsers, onToggleWatched, allUsers }) {
  const [watchers, setWatchers] = useState([]);
  const [showWatchers, setShowWatchers] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleWatchersClick = async () => {
    if (showWatchers) {
      setShowWatchers(false);
      return;
    }

    try {
      setLoading(true);
      const res = await axios.get(`/api/watched/${item.plex_id}`);
      setWatchers(res.data.watchers);
      setShowWatchers(true);
    } catch (err) {
      console.error('Failed to fetch watchers:', err);
    } finally {
      setLoading(false);
    }
  };

  const readyToDelete = watchCount === totalUsers;

  return (
    <div className={`library-item ${isWatched ? 'watched' : ''} ${readyToDelete ? 'ready-to-delete' : ''}`}>
      <div className="item-poster">
        {item.poster_url ? (
          <img src={item.poster_url} alt={item.title} onError={(e) => {
            e.target.style.display = 'none';
            e.target.parentElement.innerHTML = '<div class="no-poster">📺</div>';
          }} />
        ) : (
          <div className="no-poster">📺</div>
        )}
      </div>

      <div className="item-content">
        <h3 className="item-title">{item.title}</h3>

        <div className="item-type">
          {item.type === 'movie' ? '🎬 Movie' : '📺 Show'}
        </div>

        <div className="watch-status">
          <button
            className={`watch-button ${isWatched ? 'watched-btn' : 'unwatched-btn'}`}
            onClick={() => onToggleWatched(item.plex_id, isWatched)}
          >
            {isWatched ? '✓ Watched' : 'Mark Watched'}
          </button>
        </div>

        <div className="watch-counter">
          <button
            className="watchers-btn"
            onClick={handleWatchersClick}
            disabled={watchCount === 0}
          >
            {watchCount}/{totalUsers} watched
          </button>

          {readyToDelete && (
            <div className="ready-badge">✓ Ready to Delete!</div>
          )}
        </div>

        {showWatchers && (
          <div className="watchers-list">
            {loading ? (
              <div className="loading-small">Loading...</div>
            ) : watchers.length === 0 ? (
              <div className="no-watchers">No one has watched yet</div>
            ) : (
              <ul>
                {watchers.map((watcher, idx) => (
                  <li key={idx}>
                    <span className="watcher-name">{watcher.username}</span>
                    <span className="watcher-date">
                      {new Date(watcher.watched_at).toLocaleDateString()}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default LibraryItem;
