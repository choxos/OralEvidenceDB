# OralEvidenceDB VPS Deployment Guide

This guide provides step-by-step instructions for deploying OralEvidenceDB on your VPS server (91.99.161.136) with domain oral.xeradb.com.

## 🛠 Server Requirements

- **VPS IP**: 91.99.161.136
- **Domain**: oral.xeradb.com
- **OS**: Ubuntu 20.04 LTS or newer
- **RAM**: Minimum 2GB (4GB recommended)
- **Storage**: At least 20GB free space
- **Port**: 8020 (internal), 80/443 (external)

## 📋 Prerequisites

1. Access to xeradb user with sudo privileges on your VPS
2. Domain DNS pointing to your VPS IP
3. SSH key access configured for xeradb user
4. Git repository access

## 🚀 Automated Deployment

The easiest way to deploy is using the provided deployment script:

```bash
# Make the script executable
chmod +x deploy.sh

# Run the deployment
./deploy.sh
```

## 📖 Manual Deployment Steps

If you prefer manual deployment or need to troubleshoot:

### Step 1: Server Preparation

```bash
# Connect to your VPS
ssh xeradb@91.99.161.136

# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv nginx postgresql postgresql-contrib supervisor git redis-server
```

### Step 2: PostgreSQL Setup

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE USER oral_user WITH PASSWORD 'Choxos10203040';
CREATE DATABASE oral_production OWNER oral_user;
GRANT ALL PRIVILEGES ON DATABASE oral_production TO oral_user;
\q

# Configure Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### Step 3: Project Setup

```bash
# Create project directory
sudo mkdir -p /var/www/oral
sudo chown xeradb:www-data /var/www/oral
cd /var/www/oral

# Clone the repository
git clone https://github.com/choxos/OralEvidenceDB.git .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Environment Configuration

```bash
# Create environment file
nano /var/www/oral/.env
```

Add the following content:

```env
SECRET_KEY=fhsdfh89ru348u3rnt3b674nc3mhxhi7487cx4m8
DEBUG=False
DATABASE_NAME=oral_production
DATABASE_USER=oral_user
DATABASE_PASSWORD=Choxos10203040
DATABASE_HOST=localhost
DATABASE_PORT=5432
ALLOWED_HOSTS=91.99.161.136,oral.xeradb.com
PUBMED_SEARCH_QUERY=(Stomatognathic Diseases[MeSH Major Topic]) OR (Dentistry[MeSH Major Topic]) OR (Oral Health[MeSH Major Topic])

# API Keys (get these from respective providers)
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here
GOOGLE_AI_API_KEY=your-google-ai-api-key-here

# PubMed API (optional but recommended)
PUBMED_EMAIL=your-email@example.com
PUBMED_API_KEY=your-pubmed-api-key-here
REDIS_URL=redis://localhost:6379/0
```

### Step 5: Django Setup

```bash
cd /var/www/oral
source venv/bin/activate

# Run database migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Test the application
python manage.py check
```

### Step 6: Gunicorn & Celery Configuration

Create supervisor configuration for Gunicorn:

```bash
sudo nano /etc/supervisor/conf.d/oraldb_gunicorn.conf
```

Add:

```ini
[program:oraldb_gunicorn]
command=/var/www/oral/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8020 oral_evidence_db.wsgi:application
directory=/var/www/oral
user=xeradb
group=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/www/oral/logs/gunicorn.log
stderr_logfile=/var/www/oral/logs/gunicorn_error.log
environment=PATH="/var/www/oral/venv/bin"
```

Create supervisor configuration for Celery worker:

```bash
sudo nano /etc/supervisor/conf.d/oraldb_celery.conf
```

Add:

```ini
[program:oraldb_celery]
command=/var/www/oral/venv/bin/celery -A oral_evidence_db worker -l info
directory=/var/www/oral
user=xeradb
group=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/www/oral/logs/celery.log
stderr_logfile=/var/www/oral/logs/celery_error.log
environment=PATH="/var/www/oral/venv/bin"
stopwaitsecs=600
killasgroup=true
startsecs=10
```

### Step 7: Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/oraldb
```

Add:

```nginx
server {
    listen 80;
    server_name oral.xeradb.com 91.99.161.136;

    client_max_body_size 100M;

    location /static/ {
        alias /var/www/oral/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /var/www/oral/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8020;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 300s;
        proxy_read_timeout 300s;
    }

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
}
```

### Step 8: Enable and Start Services

```bash
# Create logs directory
mkdir -p /var/www/oral/logs

# Set permissions
sudo chown -R xeradb:www-data /var/www/oral
sudo chmod -R 755 /var/www/oral
sudo chmod -R 775 /var/www/oral/logs

# Enable Nginx site
sudo ln -s /etc/nginx/sites-available/oraldb /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Restart services
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start oraldb_gunicorn
sudo supervisorctl start oraldb_celery
sudo systemctl restart nginx
sudo systemctl enable nginx
sudo systemctl enable supervisor
sudo systemctl enable redis-server
```

## 🔒 SSL Certificate Setup (Recommended)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d oral.xeradb.com

# Test automatic renewal
sudo certbot renew --dry-run
```

## 🔧 Post-Deployment Configuration

### Update API Keys

Edit `/var/www/oral/.env` and add your real API keys:

```bash
nano /var/www/oral/.env
```

Restart the application after updating:

```bash
supervisorctl restart oraldb_gunicorn
```

### Import Initial Data

```bash
cd /var/www/oral
source venv/bin/activate

# Import PubMed data (example for recent oral health papers)
python manage.py shell

# In the Django shell:
from papers.pubmed_fetcher import PubMedFetcher
fetcher = PubMedFetcher()
fetcher.fetch_papers_by_search("(Stomatognathic Diseases[MeSH Major Topic]) AND 2024[PDAT]", max_papers=100)
```

## 📊 Monitoring and Maintenance

### Check Application Status

```bash
# Check all processes
sudo supervisorctl status

# Check specific services
sudo supervisorctl status oraldb_gunicorn
sudo supervisorctl status oraldb_celery
sudo systemctl status nginx
sudo systemctl status redis-server

# Check application logs
tail -f /var/www/oral/logs/gunicorn.log
tail -f /var/www/oral/logs/celery.log

# Check system logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Database Backup

```bash
# Create backup script
nano /var/www/oral/backup.sh
```

Add:

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/oraldb"
sudo mkdir -p $BACKUP_DIR
sudo chown xeradb:www-data $BACKUP_DIR
PGPASSWORD=Choxos10203040 pg_dump -h localhost -U oral_user -d oral_production > $BACKUP_DIR/oraldb_$(date +%Y%m%d_%H%M%S).sql
# Keep only last 7 days of backups
find $BACKUP_DIR -name "oraldb_*.sql" -mtime +7 -delete
```

Make executable and add to cron:

```bash
chmod +x /var/www/oral/backup.sh
crontab -e
# Add line: 0 2 * * * /var/www/oral/backup.sh
```

### Updates and Maintenance

```bash
# Update application
cd /var/www/oral
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo supervisorctl restart oraldb_gunicorn
```

## 🔥 Firewall Configuration

```bash
# Enable UFW firewall
sudo ufw enable

# Allow SSH
sudo ufw allow ssh

# Allow HTTP and HTTPS
sudo ufw allow 'Nginx Full'

# Check status
sudo ufw status
```

## 🌍 DNS Configuration

Make sure your domain DNS records point to your VPS:

```
Type: A
Name: oral (or @)
Value: 91.99.161.136
TTL: 3600
```

## 🐛 Troubleshooting

### Common Issues

1. **502 Bad Gateway**
   - Check Gunicorn is running: `sudo supervisorctl status oraldb_gunicorn`
   - Check logs: `tail -f /var/www/oral/logs/gunicorn.log`

2. **Static files not loading**
   - Run: `python manage.py collectstatic --noinput`
   - Check Nginx configuration

3. **Database connection errors**
   - Verify PostgreSQL is running: `sudo systemctl status postgresql`
   - Check database credentials in `.env`

4. **Permission denied errors**
   - Fix permissions: `sudo chown -R xeradb:www-data /var/www/oral`
   - Set proper permissions: `sudo chmod -R 755 /var/www/oral`

### Useful Commands

```bash
# Restart all services
sudo supervisorctl restart oraldb_gunicorn
sudo systemctl restart nginx

# View detailed logs
sudo journalctl -u nginx -f
sudo supervisorctl tail -f oraldb_gunicorn

# Django shell
cd /var/www/oral && source venv/bin/activate && python manage.py shell

# Check database connectivity
cd /var/www/oral && source venv/bin/activate && python manage.py dbshell
```

## 📞 Support

After deployment, your OralEvidenceDB will be available at:

- **Main site**: https://oral.xeradb.com
- **Admin interface**: https://oral.xeradb.com/admin/
- **API documentation**: https://oral.xeradb.com/api/

For issues or questions:
1. Check the troubleshooting section above
2. Review application logs
3. Ensure all environment variables are set correctly
4. Verify all services are running

## 🎉 Congratulations!

Your OralEvidenceDB is now deployed and ready to support oral health research worldwide! The application includes:

- ✅ AI-powered PICO extraction
- ✅ Comprehensive paper search
- ✅ REST API
- ✅ Admin interface
- ✅ Retraction tracking
- ✅ XeraDB theme integration
