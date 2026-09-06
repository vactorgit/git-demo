# 🎬 Plex Watch Tracker

A collaborative web app to track watched movies and TV shows on your shared Plex server. When everyone has watched something, it's ready to delete!

## Features

- **Multi-user tracking**: You, Jeff, Brad, and anyone else can log in and mark items as watched
- **Shared Plex library**: Automatically syncs with your Plex server
- **Watch status visibility**: See who's watched what and when
- **Ready-to-delete indicator**: Items show a "Ready to Delete" badge when all users have marked them as watched
- **Filter by type**: View all items, just movies, just shows, or items you've watched
- **Responsive design**: Works on desktop and mobile devices

## Setup Instructions

### Prerequisites
- Node.js (v14 or higher)
- A Plex Media Server
- Your Plex server URL and API token

### 1. Get Your Plex API Token

1. Go to https://www.plex.tv/api/v2/user
2. Log in with your Plex account
3. Look for the `authToken` value in the JSON response
4. Also note your server URL (e.g., `http://192.168.1.100:32400`)

### 2. Install Dependencies

```bash
# Install backend dependencies
cd server
npm install

# Install frontend dependencies
cd ../client
npm install
```

### 3. Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your Plex server details
nano .env
```

Add:
```
PLEX_URL=http://your-plex-server-ip:32400
PLEX_TOKEN=your-plex-token-here
PORT=5000
SESSION_SECRET=your-secret-key
```

### 4. Run the Application

In one terminal, start the backend server:
```bash
cd server
npm run dev
```

In another terminal, start the frontend:
```bash
cd client
npm start
```

The app will open at `http://localhost:3000`

## How to Use

1. **Login**: Enter your name (e.g., "You", "Jeff", "Brad")
2. **Browse**: See all movies and shows in your Plex library
3. **Mark Watched**: Click "Mark Watched" on any item after you've finished it
4. **View Status**: Click on the "X/3 watched" button to see who's watched it and when
5. **Delete Ready**: When all users have marked an item as watched, it shows "✓ Ready to Delete!" - then you can remove it from Plex

## Plex Library Configuration

The app looks for:
- Movies in library section ID 1
- Shows in library section ID 2

If your Plex library has different IDs, update the URLs in `server/index.js`:
```javascript
// Line ~110-111
const moviesRes = await axios.get(`${plexUrl}/library/sections/1/all?X-Plex-Token=${plexToken}`);
const showsRes = await axios.get(`${plexUrl}/library/sections/2/all?X-Plex-Token=${plexToken}`);
```

To find your section IDs, visit: `http://your-plex-server:32400/library/sections?X-Plex-Token=YOUR_TOKEN`

## Architecture

- **Backend**: Node.js + Express + SQLite
- **Frontend**: React
- **Database**: SQLite (stored in `server/plex_tracker.db`)

## Features to Consider Adding Later

- Episode-level tracking for TV shows
- Integration with Plex's delete API for one-click removal
- User avatars and profiles
- Watch history timeline
- Notifications when everyone has watched something
- Docker compose for easy deployment

## Troubleshooting

**"Plex server not configured" error**
- Make sure PLEX_URL and PLEX_TOKEN are set in your .env file
- Verify your Plex server is running and accessible

**Library appears empty**
- Check that your library section IDs are correct
- Visit `http://your-plex-server:32400/library/sections?X-Plex-Token=YOUR_TOKEN` to verify
- Click "🔄 Sync Library" button in the app to refresh

**Session issues**
- Clear your browser cookies and log in again
- Restart the server

## License

MIT
