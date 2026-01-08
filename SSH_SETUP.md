# SSH Key Setup Guide

This guide will help you set up SSH keys for Git operations.

## Step 1: Generate a New SSH Key

```bash
# Generate a new SSH key (replace email with your GitHub/GitLab email)
ssh-keygen -t ed25519 -C "your_email@example.com" -f ~/.ssh/id_ed25519

# Or if you want to name it "harry" (as you tried):
ssh-keygen -t ed25519 -C "your_email@example.com" -f ~/.ssh/harry
```

**Note:** When prompted:
- Press Enter to accept default location (or specify custom path)
- Enter a passphrase (recommended) or press Enter for no passphrase

## Step 2: Start SSH Agent and Add Your Key

```bash
# Start the ssh-agent
eval "$(ssh-agent -s)"

# Add your SSH key to the ssh-agent
ssh-add ~/.ssh/id_ed25519

# Or if you named it "harry":
ssh-add ~/.ssh/harry
```

## Step 3: Add SSH Key to Your Git Hosting Service

### For GitHub:
1. Copy your public key:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   # Or if you named it "harry":
   cat ~/.ssh/harry.pub
   ```

2. Go to GitHub → Settings → SSH and GPG keys → New SSH key
3. Paste your public key and save

### For GitLab:
1. Copy your public key (same as above)
2. Go to GitLab → Preferences → SSH Keys
3. Paste your public key and save

## Step 4: Configure Git to Use SSH

```bash
# Configure git to use SSH for GitHub
git config --global url."git@github.com:".insteadOf "https://github.com/"

# Or for GitLab:
git config --global url."git@gitlab.com:".insteadOf "https://gitlab.com/"
```

## Step 5: Test Your SSH Connection

```bash
# Test GitHub connection
ssh -T git@github.com

# Or test GitLab connection
ssh -T git@gitlab.com
```

You should see a success message.

## Step 6: Make SSH Key Persistent (Optional)

To automatically add your key to ssh-agent on login, add this to `~/.ssh/config`:

```bash
# Create or edit ~/.ssh/config
nano ~/.ssh/config
```

Add:
```
Host *
  AddKeysToAgent yes
  UseKeychain yes
  IdentityFile ~/.ssh/id_ed25519
```

## Quick Commands Summary

```bash
# 1. Generate key
ssh-keygen -t ed25519 -C "your_email@example.com" -f ~/.ssh/id_ed25519

# 2. Start agent and add key
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

# 3. Display public key (copy this to GitHub/GitLab)
cat ~/.ssh/id_ed25519.pub

# 4. Test connection
ssh -T git@github.com
```

## Troubleshooting

- **"Permission denied (publickey)"**: Make sure you've added the public key to your Git hosting service
- **"Could not open a connection to your authentication agent"**: Run `eval "$(ssh-agent -s)"` first
- **Key not found**: Check the path with `ls -la ~/.ssh/`
