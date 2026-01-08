# Environment Variables Setup

This application uses environment variables for sensitive configuration. You need to create a `.env` file in the `backend` directory.

## Quick Setup

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your actual values:
   ```bash
   # Required: OpenAI API Key
   OPENAI_API_KEY=sk-proj-your-actual-key-here
   
   # Required: JWT Secret Key (generate a secure random string)
   JWT_SECRET_KEY=your-secure-random-secret-key-here
   
   # Optional: Server Port (default: 8003)
   PORT=8003
   
   # Optional: Auto-Bid Simulation Mode (default: true)
   AUTO_BID_SIMULATION=true
   ```

## Required Variables

### OPENAI_API_KEY
- **Required**: Yes
- **Description**: Your OpenAI API key for ChatGPT bid generation
- **How to get**: 
  1. Go to https://platform.openai.com/api-keys
  2. Sign in or create an account
  3. Navigate to API Keys section
  4. Create a new secret key
  5. Copy and paste it into your `.env` file

### JWT_SECRET_KEY
- **Required**: Yes (for production)
- **Description**: Secret key used to sign JWT authentication tokens
- **How to generate**: 
  ```bash
  # On Linux/Mac:
  openssl rand -hex 32
  
  # On Windows PowerShell:
  -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | % {[char]$_})
  
  # Or use an online generator:
  # https://www.random.org/strings/
  ```
- **Security**: Use a long, random string (at least 32 characters)

## Optional Variables

### PORT
- **Default**: 8003
- **Description**: Port number for the backend server
- **Example**: `PORT=8003`

### AUTO_BID_SIMULATION
- **Default**: true
- **Description**: Set to `false` to enable real bid submission (requires Crowdworks login)
- **Values**: `true` or `false`
- **Warning**: Only set to `false` if you have proper Crowdworks credentials configured

## Security Notes

1. **Never commit `.env` file to version control**
   - The `.env` file is already in `.gitignore`
   - Only commit `.env.example` as a template

2. **Keep your API keys secret**
   - Don't share your `.env` file
   - Don't paste API keys in code or chat
   - Rotate keys if they're exposed

3. **Use different keys for development and production**
   - Create separate `.env` files for different environments
   - Use environment-specific keys

## File Structure

```
backend/
├── .env              # Your actual environment variables (not in git)
├── .env.example      # Template file (safe to commit)
└── ...
```

## Troubleshooting

### "OpenAI API key not provided" warning
- Make sure `.env` file exists in the `backend` directory
- Check that `OPENAI_API_KEY` is set in the file
- Verify there are no extra spaces or quotes around the value
- Restart the server after creating/editing `.env`

### "Using default JWT_SECRET_KEY" warning
- Set `JWT_SECRET_KEY` in your `.env` file
- Generate a secure random string (see above)
- Restart the server after updating

### Environment variables not loading
- Make sure `python-dotenv` is installed: `pip install python-dotenv`
- Verify `.env` file is in the `backend` directory (same as `main.py`)
- Check file permissions (should be readable)

