#!/bin/bash
# TeaAsia Docker rebuild & restart helper
# Usage: ./rebuild.sh [--no-cache]

set -e
cd "$(dirname "$0")"

echo "🔨 Building teaasia-app..."
if [ "$1" = "--no-cache" ]; then
    docker-compose build --no-cache teaasia-app
else
    docker-compose build teaasia-app
fi

echo "🔄 Restarting container..."
docker-compose up -d teaasia-app

echo ""
echo "✅ Done! Container status:"
docker-compose ps
