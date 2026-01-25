#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOMAIN="cooperapp.prodiversa.eu"
NGINX_CONF="/etc/nginx/sites-available/cooperapp.conf"
NGINX_ENABLED="/etc/nginx/sites-enabled/cooperapp.conf"

cd "$PROJECT_DIR"

echo "=== CooperApp Deployment Script ==="

# 1. Find free port
echo "Finding free port in range 8000-8999..."
APP_PORT=$("$SCRIPT_DIR/find-free-port.sh")
echo "Selected port: $APP_PORT"

# 2. Generate .env.production
echo "Generating .env.production..."
cat > .env.production <<EOF
APP_PORT=$APP_PORT
APP_NAME=CooperApp
DATABASE_URL=sqlite:////app/data/cooperapp.db
DEBUG=false
ACME_EMAIL=admin@prodiversa.eu
EOF

# 3. Migrate existing data if present
if [ -f "cooperapp.db" ]; then
    echo "Migrating existing database..."
    mkdir -p data
    cp cooperapp.db data/cooperapp.db
fi

if [ -d "uploads" ] && [ "$(ls -A uploads 2>/dev/null)" ]; then
    echo "Migrating uploads..."
    mkdir -p data/uploads
    cp -r uploads/* data/uploads/
fi

if [ -d "exports" ] && [ "$(ls -A exports 2>/dev/null)" ]; then
    echo "Migrating exports..."
    mkdir -p data/exports
    cp -r exports/* data/exports/
fi

# 4. Build and start container
echo "Building and starting Docker container..."
APP_PORT=$APP_PORT docker compose --env-file .env.production up -d --build

# Wait for container to be healthy
echo "Waiting for container to be healthy..."
for i in {1..30}; do
    if docker compose ps | grep -q "healthy"; then
        echo "Container is healthy!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Container health check timeout"
    fi
    sleep 2
done

# 5. Configure Nginx
echo "Configuring Nginx..."
mkdir -p /var/www/certbot

# Copy and configure nginx conf with actual port
sed "s/APP_PORT_PLACEHOLDER/$APP_PORT/g" "$PROJECT_DIR/nginx/cooperapp.conf" > "$NGINX_CONF"

# Enable site
ln -sf "$NGINX_CONF" "$NGINX_ENABLED"

# Test nginx configuration
nginx -t

# 6. Check if SSL certificate exists
if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    echo "Obtaining SSL certificate with Certbot..."

    # Create temporary nginx config without SSL for initial certificate
    cat > "$NGINX_CONF" <<NGINX_TEMP
server {
    listen 80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX_TEMP

    systemctl reload nginx

    # Get certificate
    certbot certonly --webroot -w /var/www/certbot \
        -d "$DOMAIN" \
        --email admin@prodiversa.eu \
        --agree-tos \
        --non-interactive

    # Restore full nginx config with SSL
    sed "s/APP_PORT_PLACEHOLDER/$APP_PORT/g" "$PROJECT_DIR/nginx/cooperapp.conf" > "$NGINX_CONF"
fi

# 7. Restart Nginx
echo "Restarting Nginx..."
systemctl reload nginx

echo ""
echo "=== Deployment Complete ==="
echo "Application running on port: $APP_PORT"
echo "Domain: https://$DOMAIN"
echo ""
echo "Verification commands:"
echo "  curl https://$DOMAIN/health"
echo "  docker compose logs -f cooperapp"
echo "  systemctl status nginx"
