#!/bin/bash
# Production deployment script for PropertyEngine Support Agent Backend

echo "🚀 PropertyEngine Support Agent - Production Deployment"
echo "======================================================="

# Check if running as root (for systemd service creation)
if [[ $EUID -eq 0 ]]; then
   echo "⚠️  This script should not be run as root. Run as your application user."
   exit 1
fi

# Set deployment directory
DEPLOY_DIR="/opt/propengine-agent"
SERVICE_NAME="propengine-agent"
CURRENT_DIR=$(pwd)

echo "📍 Current directory: $CURRENT_DIR"
echo "🎯 Target deployment directory: $DEPLOY_DIR"

# Confirm deployment
read -p "🤔 Do you want to deploy to production? (y/N): " confirm
if [[ $confirm != [yY] ]]; then
    echo "❌ Deployment cancelled"
    exit 0
fi

# Create deployment directory structure
echo "📁 Creating deployment directory structure..."
sudo mkdir -p $DEPLOY_DIR
sudo chown $USER:$USER $DEPLOY_DIR

# Copy application files
echo "📦 Copying application files..."
cp -r . $DEPLOY_DIR/
cd $DEPLOY_DIR

# Create virtual environment
echo "🐍 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create environment file from template
echo "⚙️  Setting up environment configuration..."
if [ ! -f .env ]; then
    cat > .env << EOL
# PropertyEngine Support Agent Configuration

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false
LOG_LEVEL=INFO

# AstraDB Configuration
ASTRA_DB_APPLICATION_TOKEN=your_astra_token_here
ASTRA_DB_API_ENDPOINT=https://your-db-id-region.apps.astra.datastax.com

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Security
SECRET_KEY=your-secret-key-here

# Monitoring (optional)
SENTRY_DSN=your_sentry_dsn_here

# Firebase Configuration (optional)
FIREBASE_PROJECT_ID=your_firebase_project
FIREBASE_CREDENTIALS_PATH=/path/to/firebase-credentials.json
EOL
    
    echo "📝 Created .env file template. Please update with your actual values:"
    echo "   nano $DEPLOY_DIR/.env"
fi

# Create systemd service file
echo "🔧 Creating systemd service..."
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << EOL
[Unit]
Description=PropertyEngine Support Agent Backend
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$DEPLOY_DIR
Environment=PATH=$DEPLOY_DIR/venv/bin
ExecStart=$DEPLOY_DIR/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOL

# Create nginx configuration
echo "🌐 Creating nginx configuration..."
sudo tee /etc/nginx/sites-available/$SERVICE_NAME > /dev/null << EOL
server {
    listen 80;
    server_name your-domain.com;  # Update this with your domain

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8000/api/chat/health;
        access_log off;
    }
}
EOL

# Enable nginx site
sudo ln -sf /etc/nginx/sites-available/$SERVICE_NAME /etc/nginx/sites-enabled/

# Create log directory
sudo mkdir -p /var/log/$SERVICE_NAME
sudo chown $USER:$USER /var/log/$SERVICE_NAME

# Reload systemd and enable service
echo "🔄 Configuring system services..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME

# Test nginx configuration
echo "🔍 Testing nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Nginx configuration is valid"
    sudo systemctl reload nginx
else
    echo "❌ Nginx configuration has errors. Please check and fix."
fi

echo ""
echo "🎉 Deployment Complete!"
echo "====================="
echo ""
echo "📋 Next Steps:"
echo "1. Update environment variables:"
echo "   sudo nano $DEPLOY_DIR/.env"
echo ""
echo "2. Start the service:"
echo "   sudo systemctl start $SERVICE_NAME"
echo ""
echo "3. Check service status:"
echo "   sudo systemctl status $SERVICE_NAME"
echo ""
echo "4. View logs:"
echo "   sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "5. Update nginx server_name:"
echo "   sudo nano /etc/nginx/sites-available/$SERVICE_NAME"
echo ""
echo "6. Test the API:"
echo "   curl http://your-domain.com/api/chat/health"
echo ""
echo "⚠️  Don't forget to:"
echo "   • Configure your firewall (ufw allow 80, ufw allow 443)"
echo "   • Set up SSL certificate (certbot)"
echo "   • Configure your AstraDB and OpenAI API keys"
echo "   • Update CORS origins for your frontend domain"
