# Environment Variables Analysis

## Actual Environment Variables Used in Code

Based on code analysis, here are the **REAL** environment variables this project uses:

### ✅ Required Variables

#### 1. `OPENAI_API_KEY`
- **Used in**: `chatgpt_service.py`, `bot_service.py`
- **Purpose**: OpenAI API key for ChatGPT bid generation
- **Required**: Yes (for AI features)
- **Default**: None (will show warning if missing)
- **Where to get**: https://platform.openai.com/api-keys

#### 2. `JWT_SECRET_KEY`
- **Used in**: `auth_service.py`
- **Purpose**: Secret key for signing JWT authentication tokens
- **Required**: Yes (for authentication)
- **Default**: `'your-secret-key-change-in-production'` (shows warning)
- **Security**: Must be changed in production!

### ✅ Optional Variables

#### 3. `PORT`
- **Used in**: `main.py` (line 725)
- **Purpose**: Backend server port number
- **Required**: No
- **Default**: `8003`
- **Example**: `PORT=8003`

#### 4. `AUTO_BID_SIMULATION`
- **Used in**: `main.py` (lines 248, 259, 839)
- **Purpose**: Enable/disable simulation mode for auto-bidding
- **Required**: No
- **Default**: `'true'`
- **Values**: `'true'` or `'false'`
- **Note**: Set to `'false'` only if you have proper Crowdworks login credentials

## Variables NOT Used (Can be Removed)

The following variables are in your current `.env` file but are **NOT actually used** by the code:

- ❌ `DATABASE_URL` - Database path is hardcoded in `db.py`
- ❌ `REDIS_URL` - Redis is not used in this project
- ❌ `DEBUG` - No debug mode implementation
- ❌ `SECRET_KEY` - Not used (we use `JWT_SECRET_KEY` instead)
- ❌ `API_HOST` - Server binds to all interfaces by default
- ❌ `API_PORT` - Not used (we use `PORT` instead)
- ❌ `CORS_ORIGINS` - CORS is set to `*` (all origins) in code

## Recommended .env File

Based on actual code usage, your `.env` file should contain:

```env
# Required: OpenAI API Key for ChatGPT bid generation
OPENAI_API_KEY=sk-proj-your-actual-key-here

# Required: JWT Secret Key for authentication (change in production!)
JWT_SECRET_KEY=your-secure-random-secret-key-here

# Optional: Server Port (default: 8003)
PORT=8003

# Optional: Auto-Bid Simulation Mode (default: true)
# Set to 'false' to enable real bid submission (requires Crowdworks login)
AUTO_BID_SIMULATION=true
```

## Current .env File Issues

Your current `.env` file contains:
- ✅ `OPENAI_API_KEY` - **USED** ✓
- ❌ `DATABASE_URL` - **NOT USED** (can remove)
- ❌ `REDIS_URL` - **NOT USED** (can remove)
- ❌ `DEBUG` - **NOT USED** (can remove)
- ❌ `SECRET_KEY` - **NOT USED** (should use `JWT_SECRET_KEY` instead)
- ❌ `API_HOST` - **NOT USED** (can remove)
- ❌ `API_PORT` - **NOT USED** (should use `PORT` instead)
- ❌ `CORS_ORIGINS` - **NOT USED** (can remove)

**Missing:**
- ❌ `JWT_SECRET_KEY` - **REQUIRED** but missing!

## Action Items

1. **Add missing variable**: Add `JWT_SECRET_KEY` to your `.env` file
2. **Remove unused variables**: Clean up variables that aren't used
3. **Update .env.example**: Make sure it matches what's actually needed

## Updated .env.example Template

```env
# OpenAI API Configuration
# Get your API key from https://platform.openai.com/api-keys
OPENAI_API_KEY=your_openai_api_key_here

# JWT Secret Key for Authentication
# Generate a secure random string for production (e.g., use: openssl rand -hex 32)
JWT_SECRET_KEY=your-secret-key-change-in-production

# Server Configuration
PORT=8003

# Auto-Bid Configuration
# Set to 'false' to enable real bid submission (requires proper Crowdworks login)
AUTO_BID_SIMULATION=true
```

