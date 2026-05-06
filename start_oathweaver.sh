#!/usr/bin/env bash
# Quick start/restart script for Oathweaver and the forage stack.
# Run this any time you want to manually restart everything.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_CMD="docker"
! $DOCKER_CMD info &>/dev/null 2>&1 && DOCKER_CMD="sudo docker"

echo "Starting Ollama..."
sudo systemctl start ollama

echo "Starting forage stack (SearXNG + Crawl4AI)..."
$DOCKER_CMD start searxng crawl4ai 2>/dev/null || true

echo "Restarting Oathweaver..."
sudo systemctl restart oathweaver
sleep 2
sudo systemctl status oathweaver --no-pager -n 8

LOCAL_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "  Open from this machine: http://127.0.0.1:5050"
echo "  Open from LAN:          http://$LOCAL_IP:5050"
