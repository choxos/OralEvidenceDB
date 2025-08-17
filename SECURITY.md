# 🔒 OralEvidenceDB Security Guide

## Environment Variables & Secrets

### ⚠️ **CRITICAL: Never commit sensitive data!**

The following files contain sensitive information and should **NEVER** be committed to git:

- `.env` - Contains API keys, database passwords, secret keys
- `local_settings.py` - Local Django overrides
- `*.log` - May contain sensitive data in logs
- `*.sqlite3` - Database files with user data

### 🔧 **Setting up Environment Variables**

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```

2. **Fill in your actual values:**
   ```bash
   nano .env
   ```

3. **Verify .env is ignored:**
   ```bash
   git status  # .env should NOT appear
   ```

## API Keys & Credentials

### 🤖 **LLM API Keys (Required for PICO extraction)**

1. **OpenAI API Key:**
   - Get from: https://platform.openai.com/api-keys
   - Add to `.env`: `OPENAI_API_KEY=sk-...`

2. **Anthropic API Key:**
   - Get from: https://console.anthropic.com/
   - Add to `.env`: `ANTHROPIC_API_KEY=sk-ant-...`

3. **Google AI API Key:**
   - Get from: https://aistudio.google.com/app/apikey
   - Add to `.env`: `GOOGLE_AI_API_KEY=...`

### 📊 **PubMed API**
- Email is required: `PUBMED_EMAIL=your-email@example.com`
- API key is optional but recommended: `PUBMED_API_KEY=...`
- Get API key from: https://www.ncbi.nlm.nih.gov/account/settings/

### 🗄️ **Database Security**
- Use strong passwords for PostgreSQL
- Change default credentials immediately
- Restrict database access to localhost

## Deployment Security

### 🛡️ **VPS Security Checklist**

- [ ] **Firewall**: Enable UFW, allow only SSH, HTTP, HTTPS
- [ ] **SSL Certificate**: Install Let's Encrypt certificate
- [ ] **User Permissions**: Use `xeradb` user, not root
- [ ] **File Permissions**: Proper ownership (`xeradb:www-data`)
- [ ] **Secret Rotation**: Change all default passwords
- [ ] **Updates**: Keep system packages updated

### 🔐 **Django Security Settings**

```python
# In production (.env):
DEBUG=False
SECRET_KEY=your-unique-secret-key
ALLOWED_HOSTS=oral.xeradb.com,91.99.161.136
```

### 🚨 **Security Headers**
Already configured in Nginx:
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`

## Data Protection

### 📁 **File Security**
- Media files are served through Django (access controlled)
- Static files are served directly by Nginx (public)
- Log files have restricted permissions (775)

### 🔄 **Backup Security**
- Database backups in `/var/backups/oraldb/`
- Automatic cleanup (7 days retention)
- Use environment variables for backup credentials

## Monitoring & Incident Response

### 📊 **Security Monitoring**
- Check logs regularly: `tail -f /var/www/oral/logs/gunicorn.log`
- Monitor failed login attempts in Django admin
- Set up Sentry for error tracking (optional)

### 🚨 **If Compromised**
1. **Immediate Actions:**
   - Change all passwords and API keys
   - Rotate Django SECRET_KEY
   - Check access logs for unauthorized access
   - Update all dependencies

2. **Recovery:**
   - Deploy new keys using `.env` file
   - Restart all services: `sudo supervisorctl restart all`
   - Monitor for unusual activity

## Contact

For security concerns related to OralEvidenceDB:
- Create a private issue on GitHub
- Contact the research team through McMaster University channels

## Security Updates

This project includes automatic security updates through:
- Requirements.txt with pinned versions
- Regular dependency updates
- Django security patches

**Last Updated:** December 2024
