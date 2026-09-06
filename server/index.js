const express = require('express');
const cors = require('cors');
const session = require('express-session');
const sqlite3 = require('sqlite3').verbose();
const axios = require('axios');
const path = require('path');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 5000;
const DB_PATH = path.join(__dirname, 'plex_tracker.db');

// Middleware
app.use(cors());
app.use(express.json());
app.use(session({
  secret: process.env.SESSION_SECRET || 'dev-secret-key',
  resave: false,
  saveUninitialized: true
}));

// Database setup
const db = new sqlite3.Database(DB_PATH, (err) => {
  if (err) console.error(err);
  else console.log('Connected to SQLite database');
});

db.serialize(() => {
  db.run(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS watched_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      plex_id TEXT NOT NULL,
      title TEXT NOT NULL,
      type TEXT NOT NULL,
      user_id INTEGER NOT NULL,
      watched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (user_id) REFERENCES users(id),
      UNIQUE(plex_id, user_id)
    )
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS plex_library (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      plex_id TEXT UNIQUE NOT NULL,
      title TEXT NOT NULL,
      type TEXT NOT NULL,
      poster_url TEXT,
      synced_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `);
});

// Helper functions
const getUser = (username) => {
  return new Promise((resolve, reject) => {
    db.get('SELECT * FROM users WHERE username = ?', [username], (err, row) => {
      if (err) reject(err);
      else resolve(row);
    });
  });
};

const createUser = (username) => {
  return new Promise((resolve, reject) => {
    db.run('INSERT INTO users (username) VALUES (?)', [username], function(err) {
      if (err) reject(err);
      else resolve({ id: this.lastID, username });
    });
  });
};

const ensureUser = async (username) => {
  let user = await getUser(username);
  if (!user) {
    user = await createUser(username);
  }
  return user;
};

// Routes

// Login/register
app.post('/api/auth/login', async (req, res) => {
  try {
    const { username } = req.body;
    if (!username) return res.status(400).json({ error: 'Username required' });

    const user = await ensureUser(username);
    req.session.userId = user.id;
    req.session.username = user.username;

    res.json({ user });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get current user
app.get('/api/auth/me', (req, res) => {
  if (req.session.userId) {
    res.json({ userId: req.session.userId, username: req.session.username });
  } else {
    res.status(401).json({ error: 'Not logged in' });
  }
});

// Logout
app.post('/api/auth/logout', (req, res) => {
  req.session.destroy((err) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ success: true });
  });
});

// Get Plex library (requires PLEX_URL and PLEX_TOKEN in .env)
app.get('/api/plex/library', async (req, res) => {
  try {
    const plexUrl = process.env.PLEX_URL;
    const plexToken = process.env.PLEX_TOKEN;

    if (!plexUrl || !plexToken) {
      return res.status(400).json({ error: 'Plex server not configured. Set PLEX_URL and PLEX_TOKEN in .env' });
    }

    // Fetch movies
    const moviesRes = await axios.get(`${plexUrl}/library/sections/1/all?X-Plex-Token=${plexToken}`);
    // Fetch TV shows
    const showsRes = await axios.get(`${plexUrl}/library/sections/2/all?X-Plex-Token=${plexToken}`);

    const items = [];

    if (moviesRes.data.MediaContainer.Metadata) {
      moviesRes.data.MediaContainer.Metadata.forEach(movie => {
        items.push({
          plex_id: movie.ratingKey,
          title: movie.title,
          type: 'movie',
          poster_url: movie.thumb ? `${plexUrl}${movie.thumb}?X-Plex-Token=${plexToken}` : null
        });
      });
    }

    if (showsRes.data.MediaContainer.Metadata) {
      showsRes.data.MediaContainer.Metadata.forEach(show => {
        items.push({
          plex_id: show.ratingKey,
          title: show.title,
          type: 'show',
          poster_url: show.thumb ? `${plexUrl}${show.thumb}?X-Plex-Token=${plexToken}` : null
        });
      });
    }

    // Sync to database
    items.forEach(item => {
      db.run(
        `INSERT OR REPLACE INTO plex_library (plex_id, title, type, poster_url) VALUES (?, ?, ?, ?)`,
        [item.plex_id, item.title, item.type, item.poster_url]
      );
    });

    res.json({ items });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get all library items with watch status
app.get('/api/library', async (req, res) => {
  try {
    if (!req.session.userId) {
      return res.status(401).json({ error: 'Not logged in' });
    }

    const items = await new Promise((resolve, reject) => {
      db.all(`
        SELECT
          pl.*,
          CASE WHEN wi.id IS NOT NULL THEN 1 ELSE 0 END as watched_by_me,
          (SELECT COUNT(*) FROM watched_items WHERE plex_id = pl.plex_id) as watch_count
        FROM plex_library pl
        LEFT JOIN watched_items wi ON pl.plex_id = wi.plex_id AND wi.user_id = ?
        ORDER BY pl.title
      `, [req.session.userId], (err, rows) => {
        if (err) reject(err);
        else resolve(rows);
      });
    });

    res.json({ items });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Mark item as watched
app.post('/api/watched', async (req, res) => {
  try {
    if (!req.session.userId) {
      return res.status(401).json({ error: 'Not logged in' });
    }

    const { plex_id } = req.body;
    if (!plex_id) return res.status(400).json({ error: 'plex_id required' });

    await new Promise((resolve, reject) => {
      db.run(
        `INSERT OR IGNORE INTO watched_items (plex_id, user_id, title, type)
         SELECT plex_id, ?, title, type FROM plex_library WHERE plex_id = ?`,
        [req.session.userId, plex_id],
        function(err) {
          if (err) reject(err);
          else resolve();
        }
      );
    });

    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Unmark item as watched
app.delete('/api/watched/:plex_id', async (req, res) => {
  try {
    if (!req.session.userId) {
      return res.status(401).json({ error: 'Not logged in' });
    }

    const { plex_id } = req.params;

    await new Promise((resolve, reject) => {
      db.run(
        `DELETE FROM watched_items WHERE plex_id = ? AND user_id = ?`,
        [plex_id, req.session.userId],
        function(err) {
          if (err) reject(err);
          else resolve();
        }
      );
    });

    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get watch status for an item
app.get('/api/watched/:plex_id', async (req, res) => {
  try {
    const { plex_id } = req.params;

    const watchers = await new Promise((resolve, reject) => {
      db.all(
        `SELECT u.username, wi.watched_at FROM watched_items wi
         JOIN users u ON wi.user_id = u.id
         WHERE wi.plex_id = ?
         ORDER BY wi.watched_at DESC`,
        [plex_id],
        (err, rows) => {
          if (err) reject(err);
          else resolve(rows || []);
        }
      );
    });

    res.json({ watchers });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get users
app.get('/api/users', async (req, res) => {
  try {
    const users = await new Promise((resolve, reject) => {
      db.all('SELECT id, username FROM users ORDER BY username', (err, rows) => {
        if (err) reject(err);
        else resolve(rows);
      });
    });

    res.json({ users });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`Plex Watch Tracker server running on port ${PORT}`);
});
