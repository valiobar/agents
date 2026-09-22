#!/bin/bash

# Server-side deploy script for Agents (Compose-on-VPS)
# Expects prebuilt images in GHCR; never builds on the server.
# Usage: IMAGE_TAG=<sha> bash deploy.sh   (or rely on IMAGE_TAG in .env)

set -e

echo "Starting deployment..."

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

COMPOSE_FILE="infrastructure/docker-compose.yml"
COMPOSE=(docker compose --env-file .env -f "$COMPOSE_FILE")

# Required variables in root .env (must be set; no insecure defaults)
REQUIRED_VARS=(
  JWT_SECRET
  NEXTAUTH_SECRET
  NEXTAUTH_URL
)

if [ ! -f .env ]; then
  echo -e "${RED}.env file not found!${NC}"
  echo "Copy the template and fill in values: cp .env.example .env"
  exit 1
fi

# shellcheck disable=SC1091
set -a
# shellcheck source=/dev/null
source .env
set +a

MISSING=()
for var in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var}" ]; then
    MISSING+=("$var")
  fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
  echo -e "${RED}.env is missing required variables:${NC}"
  for var in "${MISSING[@]}"; do
    echo "  - $var"
  done
  echo "See .env.example for the full contract."
  exit 1
fi

if [ "$JWT_SECRET" = "change-me-in-production-use-a-long-random-string" ] || [ "$JWT_SECRET" = "change-me-in-production" ] || [ "$JWT_SECRET" = "change-me-to-a-strong-random-value" ]; then
  echo -e "${RED}JWT_SECRET is still an insecure example value. Set a long random secret.${NC}"
  exit 1
fi

if [ "$NEXTAUTH_SECRET" = "change-me-in-development" ] || [ "$NEXTAUTH_SECRET" = "change-me-in-production" ]; then
  echo -e "${RED}NEXTAUTH_SECRET is still an insecure example value. Set a long random secret.${NC}"
  exit 1
fi

if ! command -v docker &> /dev/null; then
  echo -e "${RED}Docker is not installed!${NC}"
  exit 1
fi

if ! docker compose version &> /dev/null; then
  echo -e "${RED}Docker Compose plugin is not installed!${NC}"
  exit 1
fi

echo -e "${GREEN}Docker and Docker Compose are installed${NC}"
echo "IMAGE_TAG=${IMAGE_TAG:-latest}"

if [ -z "${OPENAI_API_KEY}" ]; then
  echo -e "${YELLOW}OPENAI_API_KEY is empty. The stack can start, but chat and embeddings will fail until it is set.${NC}"
fi

check_service_health() {
  local service=$1
  local url=$2
  local max_attempts=30
  local attempt=1

  echo -n "Waiting for $service to be healthy..."
  while [ $attempt -le $max_attempts ]; do
    if curl -f -s "$url" > /dev/null 2>&1; then
      echo -e " ${GREEN}ok${NC}"
      return 0
    fi
    echo -n "."
    sleep 2
    attempt=$((attempt + 1))
  done

  echo -e " ${RED}failed${NC}"
  echo -e "${RED}Service $service failed to become healthy${NC}"
  return 1
}

echo ""
echo -e "${YELLOW}Pulling images...${NC}"
"${COMPOSE[@]}" pull

echo ""
echo -e "${YELLOW}Starting services (no build)...${NC}"
"${COMPOSE[@]}" up -d

echo ""
echo -e "${GREEN}Services started${NC}"
echo "Waiting for services to be ready..."
sleep 10

echo ""
echo -e "${YELLOW}Checking service health...${NC}"
check_service_health "Gateway" "http://localhost:8010/health" || true
check_service_health "Frontend" "http://localhost:3010/login" || true

echo ""
echo -e "${GREEN}Running containers:${NC}"
"${COMPOSE[@]}" ps

echo ""
echo -e "${GREEN}Deployment complete${NC}"
echo ""
echo "Useful commands:"
echo "  View logs:     docker compose --env-file .env -f $COMPOSE_FILE logs -f"
echo "  Stop services: docker compose --env-file .env -f $COMPOSE_FILE down"
echo "  Restart:       docker compose --env-file .env -f $COMPOSE_FILE restart"
echo ""
echo "Service URLs on this host:"
echo "  Gateway:  http://localhost:8010/health"
echo "  Frontend: http://localhost:3010"
echo "Droplet (shared with Hint and vbar-viber-bot):"
echo "  Gateway:  http://159.89.26.67:8010/health"
echo "  Frontend: http://159.89.26.67:3010"
