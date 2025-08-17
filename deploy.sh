#!/bin/bash

# OralEvidenceDB VPS Deployment Script
# Automates deployment to VPS server with PostgreSQL and Nginx

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🦷 OralEvidenceDB VPS Deployment${NC}"
echo "================================================="

# Configuration
VPS_IP="91.99.161.136"
VPS_USER="xeradb"
DOMAIN="oral.xeradb.com"
PROJECT_DIR="/var/www/oral"
BRANCH="main"

# Check if we're running this script from the project root
if [ ! -f "manage.py" ]; then
    echo -e "${RED}❌ Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Function to run commands on VPS
run_remote() {
    ssh $VPS_USER@$VPS_IP "$1"
}

# Function to copy files to VPS
copy_to_vps() {
    scp -r "$1" $VPS_USER@$VPS_IP:"$2"
}

echo -e "${GREEN}🚀 Starting deployment to VPS...${NC}"

# Step 1: Update local repository
echo -e "${BLUE}📝 Updating local repository...${NC}"
git add -A
git commit -m "Deploy: $(date '+%Y-%m-%d %H:%M:%S')" || echo "No changes to commit"
git push origin $BRANCH

# Step 2: Create project directory on VPS
echo -e "${BLUE}📁 Creating project directory on VPS...${NC}"
run_remote "sudo mkdir -p $PROJECT_DIR"
run_remote "sudo chown xeradb:www-data $PROJECT_DIR"

# Step 3: Install system dependencies on VPS
echo -e "${BLUE}📦 Installing system dependencies...${NC}"
run_remote "sudo apt update && sudo apt install -y python3-pip python3-venv nginx postgresql postgresql-contrib supervisor git redis-server"

# Step 4: Setup PostgreSQL and Redis
echo -e "${BLUE}🗄️ Setting up PostgreSQL and Redis...${NC}"
run_remote "sudo -u postgres psql -c \"CREATE USER oral_user WITH PASSWORD 'Choxos10203040';\" || true"
run_remote "sudo -u postgres psql -c \"CREATE DATABASE oral_production OWNER oral_user;\" || true"
run_remote "sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE oral_production TO oral_user;\" || true"
run_remote "sudo systemctl start redis-server"
run_remote "sudo systemctl enable redis-server"

# Step 5: Clone/Update repository on VPS
echo -e "${BLUE}📥 Cloning/updating repository on VPS...${NC}"
run_remote "cd $PROJECT_DIR && (git clone https://github.com/choxos/OralEvidenceDB.git . || (git fetch --all && git reset --hard origin/$BRANCH))"

# Step 6: Setup Python virtual environment
echo -e "${BLUE}🐍 Setting up Python environment...${NC}"
run_remote "cd $PROJECT_DIR && python3 -m venv venv"
run_remote "cd $PROJECT_DIR && source venv/bin/activate && pip install --upgrade pip"
run_remote "cd $PROJECT_DIR && source venv/bin/activate && pip install -r requirements.txt"

# Step 7: Setup environment variables
echo -e "${BLUE}⚙️ Setting up environment variables...${NC}"
cat > .env.production << EOF
SECRET_KEY=your-super-secret-key-change-this-in-production
DEBUG=False
DATABASE_NAME=oral_production
DATABASE_USER=oral_user
DATABASE_PASSWORD=Choxos10203040
DATABASE_HOST=localhost
DATABASE_PORT=5432
ALLOWED_HOSTS=91.99.161.136,oral.xeradb.com
PUBMED_SEARCH_QUERY=(Stomatognathic Diseases[MeSH Major Topic]) OR (Dentistry[MeSH Major Topic]) OR (Oral Health[MeSH Major Topic])
OPENAI_API_KEY=your-openai-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here
GOOGLE_AI_API_KEY=your-google-ai-key-here
PUBMED_EMAIL=your-email@example.com
PUBMED_API_KEY=your-pubmed-api-key
REDIS_URL=redis://localhost:6379/0
EOF

copy_to_vps ".env.production" "$PROJECT_DIR/.env"
rm .env.production

# Step 8: Run Django migrations and collect static files
echo -e "${BLUE}🔄 Running Django setup...${NC}"
run_remote "cd $PROJECT_DIR && source venv/bin/activate && python manage.py makemigrations"
run_remote "cd $PROJECT_DIR && source venv/bin/activate && python manage.py migrate"
run_remote "cd $PROJECT_DIR && source venv/bin/activate && python manage.py collectstatic --noinput"

# Step 9: Create Django superuser (if needed)
echo -e "${BLUE}👤 Creating Django superuser...${NC}"
run_remote "cd $PROJECT_DIR && source venv/bin/activate && echo \"from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@oral.xeradb.com', 'admin123')\" | python manage.py shell" || true

# Step 10: Setup Gunicorn service
echo -e "${BLUE}🔧 Setting up Gunicorn service...${NC}"
cat > gunicorn.conf << EOF
[program:oraldb_gunicorn]
command=$PROJECT_DIR/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8020 oral_evidence_db.wsgi:application
directory=$PROJECT_DIR
user=xeradb
group=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$PROJECT_DIR/logs/gunicorn.log
stderr_logfile=$PROJECT_DIR/logs/gunicorn_error.log
environment=PATH="$PROJECT_DIR/venv/bin"
EOF

copy_to_vps "gunicorn.conf" "/tmp/oraldb_gunicorn.conf"
run_remote "sudo mv /tmp/oraldb_gunicorn.conf /etc/supervisor/conf.d/oraldb_gunicorn.conf"
rm gunicorn.conf

# Step 10b: Setup Celery worker service
echo -e "${BLUE}🔧 Setting up Celery worker service...${NC}"
cat > celery.conf << EOF
[program:oraldb_celery]
command=$PROJECT_DIR/venv/bin/celery -A oral_evidence_db worker -l info
directory=$PROJECT_DIR
user=xeradb
group=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$PROJECT_DIR/logs/celery.log
stderr_logfile=$PROJECT_DIR/logs/celery_error.log
environment=PATH="$PROJECT_DIR/venv/bin"
stopwaitsecs=600
killasgroup=true
startsecs=10
EOF

copy_to_vps "celery.conf" "/tmp/oraldb_celery.conf"
run_remote "sudo mv /tmp/oraldb_celery.conf /etc/supervisor/conf.d/oraldb_celery.conf"
rm celery.conf

# Step 11: Setup Nginx configuration
echo -e "${BLUE}🌐 Setting up Nginx...${NC}"
cat > nginx.conf << EOF
server {
    listen 80;
    server_name $DOMAIN $VPS_IP;

    client_max_body_size 100M;

    location /static/ {
        alias $PROJECT_DIR/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias $PROJECT_DIR/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8020;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 300s;
        proxy_read_timeout 300s;
    }

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
}
EOF

copy_to_vps "nginx.conf" "/tmp/oraldb_nginx.conf"
run_remote "sudo mv /tmp/oraldb_nginx.conf /etc/nginx/sites-available/oraldb"
rm nginx.conf

# Step 12: Enable Nginx site and restart services
echo -e "${BLUE}🔄 Enabling services...${NC}"
run_remote "sudo ln -sf /etc/nginx/sites-available/oraldb /etc/nginx/sites-enabled/" || true
run_remote "sudo rm -f /etc/nginx/sites-enabled/default" || true
run_remote "sudo nginx -t"
run_remote "mkdir -p $PROJECT_DIR/logs"
run_remote "sudo chown -R xeradb:www-data $PROJECT_DIR"
run_remote "sudo chmod -R 755 $PROJECT_DIR"
run_remote "sudo chmod -R 775 $PROJECT_DIR/logs"
run_remote "sudo supervisorctl reread && sudo supervisorctl update"
run_remote "sudo supervisorctl restart oraldb_gunicorn"
run_remote "sudo supervisorctl restart oraldb_celery"
run_remote "sudo systemctl restart nginx"
run_remote "sudo systemctl enable nginx"
run_remote "sudo systemctl enable supervisor"
run_remote "sudo systemctl enable redis-server"

# Step 13: Setup SSL certificate (optional but recommended)
echo -e "${YELLOW}🔐 SSL setup not automated. To enable HTTPS, install certbot:${NC}"
echo "ssh $VPS_USER@$VPS_IP"
echo "sudo apt install certbot python3-certbot-nginx"
echo "sudo certbot --nginx -d $DOMAIN"

echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo ""
echo -e "${BLUE}🌐 Your OralEvidenceDB is now available at:${NC}"
echo "   - HTTP: http://$DOMAIN"
echo "   - HTTP: http://$VPS_IP"
echo "   - Admin: http://$DOMAIN/admin/ (admin/admin123)"
echo ""
echo -e "${BLUE}📊 To monitor the application:${NC}"
echo "   - Logs: ssh $VPS_USER@$VPS_IP 'tail -f $PROJECT_DIR/logs/gunicorn.log'"
echo "   - Status: ssh $VPS_USER@$VPS_IP 'sudo supervisorctl status'"
echo "   - Nginx: ssh $VPS_USER@$VPS_IP 'sudo systemctl status nginx'"
echo ""
echo -e "${YELLOW}⚠️ Don't forget to:${NC}"
echo "   1. Update the .env file with your real API keys"
echo "   2. Change the default admin password"
echo "   3. Setup SSL certificate with certbot"
echo "   4. Configure firewall (ufw) if needed"
echo "   5. Ensure xeradb user has proper sudo permissions"
echo ""
echo -e "${GREEN}🎉 Happy researching with OralEvidenceDB!${NC}"
