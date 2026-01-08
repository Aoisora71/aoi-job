# 🚀 Crowdworks Monitor

An AI-powered job monitoring and automated bidding system for [Crowdworks.jp](https://crowdworks.jp), Japan's largest crowdsourcing platform. This application helps freelancers automatically discover, analyze, and bid on relevant projects using ChatGPT integration.

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-green.svg)
![Next.js](https://img.shields.io/badge/next.js-14.0.4-black.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)

## ✨ Features

### 🔍 Job Monitoring
- **Real-time Job Scraping**: Automatically monitors Crowdworks.jp for new job postings
- **Multi-Category Support**: Web Development, System Development, E-commerce, Mobile Apps, AI & ML
- **Keyword Filtering**: Filter jobs by specific keywords
- **Time-based Filtering**: Only show jobs posted within a specified time window
- **Server-Sent Events (SSE)**: Real-time job updates without page refresh

### 🤖 AI-Powered Features
- **Job Analysis**: AI-powered job suitability analysis using ChatGPT
- **Automated Bid Generation**: Generate professional bid proposals using AI
- **Custom Prompts**: Configure up to 3 custom prompts for different bidding strategies
- **Multiple Model Support**: Choose from various OpenAI models (GPT-4, GPT-4o-mini, etc.)
- **Suitability Scoring**: Automatic scoring of job matches based on your skills

### 👥 Client Management
- **Favorite Clients**: Save and track your favorite clients
- **Blocked Users**: Block specific clients to hide their jobs
- **Client Details**: View client evaluation rates, contract counts, and identity verification status
- **Client Activity Monitoring**: Track when favorite clients post new jobs

### 📊 Data Management
- **Job History**: View and manage all scraped jobs
- **Bid Management**: Track generated and submitted bids
- **Data Reset**: Clear bids and jobs tables from settings
- **Read/Unread Status**: Mark jobs as read for better organization

### 🔔 Notifications
- **Discord Integration**: Send notifications to Discord webhooks
- **Telegram Integration**: Send notifications via Telegram bot
- **Real-time Alerts**: Get notified when favorite clients post new jobs
- **Browser Notifications**: Native browser notifications for new jobs

### 🎨 Modern UI
- **Responsive Design**: Beautiful, modern interface built with Next.js and Tailwind CSS
- **Real-time Updates**: Live job feed with Server-Sent Events
- **Dark Mode Ready**: Clean, professional design
- **Mobile Friendly**: Responsive layout for all devices

## 🛠️ Tech Stack

### Backend
- **Python 3.12+**: Core backend language
- **SQLAlchemy**: ORM for database management
- **SQLite**: Lightweight database
- **BeautifulSoup4**: Web scraping
- **Selenium**: Web automation for auto-bidding
- **OpenAI API**: ChatGPT integration for bid generation
- **Server-Sent Events (SSE)**: Real-time updates
- **JWT Authentication**: Secure user authentication

### Frontend
- **Next.js 14**: React framework with App Router
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first CSS framework
- **Lucide React**: Modern icon library
- **Axios**: HTTP client for API calls
- **Socket.io Client**: Real-time communication

## 📋 Prerequisites

- **Python 3.12+**
- **Node.js 18+** and **npm** or **pnpm**
- **OpenAI API Key** ([Get one here](https://platform.openai.com/api-keys))
- **Chrome/Chromium** (for Selenium auto-bidding)
- **Git** (for version control)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone git@github.com:Aoisora71/aoi-job.git
cd aoi-job
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env and add your OpenAI API key
nano .env  # or use your preferred editor
```

**Required environment variables in `backend/.env`:**
```env
OPENAI_API_KEY=sk-proj-your-key-here
JWT_SECRET_KEY=your-secure-random-secret-key
PORT=8003
AUTO_BID_SIMULATION=true
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
# or
pnpm install

# Copy environment file
cp .env.example .env.local

# Edit .env.local and configure API URL
nano .env.local  # or use your preferred editor
```

**Required environment variables in `frontend/.env.local`:**
```env
NEXT_PUBLIC_API_URL=http://localhost:8003
```

### 4. Database Migration

```bash
cd backend
python migrate_db.py
```

This will:
- Add missing columns to existing tables
- Create the `blocked_users` table
- Set up the database schema

## 🎯 Usage

### Starting the Backend

```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
python main.py
```

The backend will start on `http://localhost:8003` (or the port specified in `.env`).

### Starting the Frontend

```bash
cd frontend
npm run dev
# or
pnpm dev
```

The frontend will start on `http://localhost:6002`.

### Accessing the Application

1. Open your browser and navigate to `http://localhost:6002`
2. Login with your credentials (default user is created on first run)
3. Configure your settings:
   - Select job categories
   - Set keywords
   - Configure scraping interval
   - Add your OpenAI API key
   - Set up notification services (optional)

### First Time Setup

1. **Configure Settings**: Go to Settings → Basic Settings
   - Select categories you want to monitor
   - Add keywords (optional)
   - Set scraping interval (default: 60 seconds)
   - Configure maximum jobs to display

2. **Set Up AI Features**: Go to Settings → ChatGPT Integration
   - Add your OpenAI API key
   - Select your preferred model
   - Configure custom prompts (optional)
   - Set minimum suitability score

3. **Start Monitoring**: Click the "Start" button in the header
   - The bot will begin scraping jobs
   - New jobs will appear in real-time
   - Use the heart icon to favorite clients
   - Use the ban icon to block clients

## 📁 Project Structure

```
crowdworks-monitor/
├── backend/
│   ├── main.py                 # Main API server
│   ├── bot_service.py          # Bot logic and job scraping
│   ├── real_crowdworks_scraper.py  # Web scraper
│   ├── chatgpt_service.py     # OpenAI integration
│   ├── auth_service.py         # Authentication
│   ├── models.py               # Database models
│   ├── db.py                   # Database configuration
│   ├── notification_service.py # Discord/Telegram notifications
│   ├── favorite_clients_service.py  # Favorite clients management
│   ├── migrate_db.py           # Database migration script
│   ├── requirements.txt        # Python dependencies
│   ├── .env.example            # Environment variables template
│   └── app.db                  # SQLite database (created automatically)
│
├── frontend/
│   ├── app/                    # Next.js app directory
│   │   ├── page.tsx           # Main page
│   │   ├── layout.tsx         # Root layout
│   │   └── globals.css        # Global styles
│   ├── components/             # React components
│   │   ├── JobCard.tsx        # Job display card
│   │   ├── Header.tsx         # Application header
│   │   ├── EnhancedSettingsModal.tsx  # Settings modal
│   │   ├── BlockedUsersModal.tsx      # Blocked users management
│   │   ├── FavoriteClientsModal.tsx   # Favorite clients management
│   │   └── ...
│   ├── hooks/                 # Custom React hooks
│   │   ├── useBot.ts          # Bot state management
│   │   └── useSocket.ts       # SSE connection
│   ├── lib/                   # Utilities
│   │   ├── api.ts             # API client
│   │   └── notifications.ts   # Browser notifications
│   ├── package.json           # Node.js dependencies
│   └── .env.example           # Environment variables template
│
├── .gitignore                 # Git ignore rules
├── README.md                  # This file
└── SSH_SETUP.md              # SSH key setup guide
```

## 🔌 API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `GET /api/auth/verify` - Verify authentication token

### Bot Control
- `GET /api/bot/status` - Get bot status
- `POST /api/bot/start` - Start the bot
- `POST /api/bot/pause` - Pause the bot
- `POST /api/bot/stop` - Stop the bot

### Jobs
- `GET /api/jobs` - Get all jobs (filtered by blocked users)
- `POST /api/jobs/:id/mark-read` - Mark job as read
- `GET /api/events` - Server-Sent Events stream for real-time updates

### Bidding
- `POST /api/bidding/generate/:job_id` - Generate bid using AI
- `POST /api/bidding/submit` - Submit bid
- `POST /api/auto-bid/submit` - Submit auto-bid

### Settings
- `GET /api/settings` - Get user settings
- `POST /api/settings` - Update user settings
- `GET /api/notifications/settings` - Get notification settings
- `POST /api/notifications/settings` - Update notification settings

### Favorite Clients
- `GET /api/favorites` - Get favorite clients list
- `POST /api/favorites` - Add client to favorites
- `DELETE /api/favorites/:id` - Remove client from favorites

### Blocked Users
- `GET /api/blocked` - Get blocked users list
- `POST /api/blocked` - Block a user
- `DELETE /api/blocked/:id` - Unblock a user

### Data Management
- `POST /api/data/clear-bids` - Clear all bids from database
- `POST /api/data/clear-jobs` - Clear all jobs from database

## ⚙️ Configuration

### Backend Configuration

Edit `backend/.env`:

```env
# Required
OPENAI_API_KEY=sk-proj-your-key-here
JWT_SECRET_KEY=your-secure-random-secret-key

# Optional
PORT=8003
AUTO_BID_SIMULATION=true
```

### Frontend Configuration

Edit `frontend/.env.local`:

```env
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8003
```

For production, update to your server's IP or domain:
```env
NEXT_PUBLIC_API_URL=http://your-server-ip:8003
```

## 🔒 Security

- **JWT Authentication**: Secure token-based authentication
- **Password Hashing**: Bcrypt for password storage
- **Environment Variables**: Sensitive data stored in `.env` files (not committed)
- **CORS Protection**: Configured CORS headers
- **Input Validation**: Server-side validation for all inputs

## 🧪 Development

### Running in Development Mode

**Backend:**
```bash
cd backend
source venv/bin/activate
python main.py
```

**Frontend:**
```bash
cd frontend
npm run dev
```

### Building for Production

**Frontend:**
```bash
cd frontend
npm run build
npm start
```

### Database Migrations

When adding new models or fields:
```bash
cd backend
python migrate_db.py
```

## 📝 Features in Detail

### Blocked Users
- Block clients by clicking the ban icon on any job card
- Blocked users' jobs are automatically filtered from all views
- Manage blocked users from the header menu
- Blocking works by `employer_id` or `client_username`

### Favorite Clients
- Add clients to favorites by clicking the heart icon
- Track favorite clients' activity and new job postings
- Get notifications when favorite clients post new jobs
- View favorite clients' status and contract information

### Auto-Bidding
- Configure custom prompts for different bidding strategies
- Set minimum suitability score threshold
- Enable/disable auto-bid mode
- Automatic bid generation and submission (requires Selenium)

### Data Management
- Clear all bids from the database
- Clear all jobs from the database
- Both operations available in Settings → Data Management

## 🐛 Troubleshooting

### Backend Issues

**Port already in use:**
```bash
# Change PORT in backend/.env or kill the process using the port
lsof -ti:8003 | xargs kill -9
```

**Database errors:**
```bash
# Run migration script
cd backend
python migrate_db.py
```

**OpenAI API errors:**
- Verify your API key is correct in `backend/.env`
- Check your OpenAI account has credits
- Ensure the API key has proper permissions

### Frontend Issues

**Connection errors:**
- Verify `NEXT_PUBLIC_API_URL` in `frontend/.env.local`
- Ensure backend is running
- Check firewall settings

**Build errors:**
```bash
# Clear Next.js cache
cd frontend
rm -rf .next
npm run build
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [Crowdworks.jp](https://crowdworks.jp) - Job platform
- [OpenAI](https://openai.com) - ChatGPT API
- [Next.js](https://nextjs.org) - React framework
- [Tailwind CSS](https://tailwindcss.com) - CSS framework

## 📞 Support

For issues, questions, or contributions, please open an issue on GitHub.

## 🔄 Changelog

### Version 1.0.0
- Initial release
- Job monitoring and scraping
- AI-powered bid generation
- Favorite clients management
- Blocked users feature
- Data management tools
- Discord and Telegram notifications
- Real-time updates via SSE

---

**Made with ❤️ for freelancers on Crowdworks.jp**
