# PFAS News Digest — Automated Daily Email

Searches for the latest PFAS news across 5 topic areas and delivers a
formatted HTML digest via SendGrid every morning at 5:00 AM MT.

## Setup (10 minutes)

### 1. Create a GitHub repository
- Go to github.com → New repository → name it `pfas-digest` → Create
- Upload all files from this folder to the repo

### 2. Add API keys as GitHub Secrets
In your repo: **Settings → Secrets and variables → Actions → New repository secret**

Add these four secrets:

| Secret name        | Value                              |
|--------------------|------------------------------------|
| `ANTHROPIC_API_KEY`| Your key from console.anthropic.com|
| `SENDGRID_API_KEY` | Your SendGrid API key              |
| `FROM_EMAIL`       | andrew@remotevelocity.com          |
| `TO_EMAIL`         | andrew@remotevelocity.com          |

### 3. Get an Anthropic API key
- Go to **console.anthropic.com**
- Settings → API Keys → Create Key
- Copy and save it as the `ANTHROPIC_API_KEY` secret above

### 4. Regenerate your SendGrid API key
- The key shared in chat should be considered compromised
- SendGrid dashboard → Settings → API Keys → regenerate
- Save the new key as the `SENDGRID_API_KEY` secret

### 5. Test it manually
- In your GitHub repo go to **Actions → PFAS Daily Digest → Run workflow**
- Check your inbox — email should arrive within ~2 minutes

### Customisation
- **Topics / stories**: edit `TOPICS` and `MAX_STORIES` in `pfas_digest.py`
- **Send time**: edit the cron line in `.github/workflows/daily_digest.yml`
  - 5 AM MDT (summer) = `0 11 * * *`
  - 5 AM MST (winter) = `0 12 * * *`
- **Recipients**: change `TO_EMAIL` secret to any address

## Cost
- GitHub Actions: **free** (2,000 min/month on free tier; this uses ~2 min/day)
- Anthropic API: ~$0.01–0.05 per run depending on search results
- SendGrid: **free** up to 100 emails/day
