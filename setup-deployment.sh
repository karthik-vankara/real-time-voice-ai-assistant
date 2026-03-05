#!/bin/bash

# Deployment Setup Helper Script
# This script helps prepare the application for cloud deployment

set -e

echo "🚀 Voice Assistant - Cloud Deployment Setup"
echo "=============================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v git &> /dev/null; then
    echo -e "${RED}✗ Git not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Git found${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 found${NC}"

if ! command -v npm &> /dev/null; then
    echo -e "${RED}✗ npm not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ npm found${NC}"

echo ""
echo "📝 Configuration Check"
echo "====================="

# Check if configuration files exist
if [ -f "Dockerfile" ]; then
    echo -e "${GREEN}✓ Dockerfile exists${NC}"
else
    echo -e "${RED}✗ Dockerfile missing${NC}"
    exit 1
fi

if [ -f "railway.json" ]; then
    echo -e "${GREEN}✓ railway.json exists${NC}"
else
    echo -e "${RED}✗ railway.json missing${NC}"
    exit 1
fi

if [ -f "client/vercel.json" ]; then
    echo -e "${GREEN}✓ client/vercel.json exists${NC}"
else
    echo -e "${RED}✗ client/vercel.json missing${NC}"
    exit 1
fi

echo ""
echo "🔐 Environment Variables"
echo "======================="

# Check if .env exists and suggest creating .env.production
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠ No .env file found (this is OK for production)${NC}"
    echo "  → Environment variables should be set in:"
    echo "    - Vercel: Dashboard → Settings → Environment Variables"
    echo "    - Railway: Dashboard → Settings → Variables"
else
    echo -e "${GREEN}✓ .env file exists (keep this local only!)${NC}"
fi

# Check OpenAI API Key
if [ -n "$OPENAI_API_KEY" ]; then
    echo -e "${GREEN}✓ OPENAI_API_KEY is set in environment${NC}"
else
    echo -e "${YELLOW}⚠ OPENAI_API_KEY not found in environment${NC}"
    echo "  → This must be set in Railway production variables"
fi

echo ""
echo "🏗️  Build Verification"
echo "===================="

# Test frontend build
echo "Testing frontend build..."
cd client
if npm run build &> /dev/null; then
    echo -e "${GREEN}✓ Frontend builds successfully${NC}"
else
    echo -e "${RED}✗ Frontend build failed${NC}"
    exit 1
fi
cd ..

echo ""
echo "📦 Production Checklist"
echo "======================"

echo ""
echo "Before deploying to Vercel and Railway:"
echo ""
echo "Frontend (Vercel):"
echo "  [ ] Create Vercel account at vercel.com"
echo "  [ ] Connect GitHub repository"
echo "  [ ] Set root directory to 'client'"
echo "  [ ] Add VITE_API_BASE_URL environment variable"
echo "  [ ] Deploy"
echo ""
echo "Backend (Railway):"
echo "  [ ] Create Railway account at railway.app"
echo "  [ ] Connect GitHub repository"
echo "  [ ] Set OPENAI_API_KEY environment variable"
echo "  [ ] Set PROVIDER_MODE=real"
echo "  [ ] Deploy"
echo ""
echo "Integration:"
echo "  [ ] Get Railway backend URL"
echo "  [ ] Update Vercel VITE_API_BASE_URL with Railway URL"
echo "  [ ] Test end-to-end"
echo ""

echo "🔍 Testing Configuration"
echo "======================="

# Test if backend can start
echo "Testing backend startup..."
if timeout 10 uvicorn src.server:create_app --host 127.0.0.1 --port 8001 --factory 2>&1 | grep -q "Uvicorn running"; then
    echo -e "${GREEN}✓ Backend starts successfully${NC}"
    # Kill the server (it continues running in background)
    pkill -f "uvicorn" || true
else
    echo -e "${YELLOW}⚠ Could not verify backend startup${NC}"
fi

echo ""
echo "✅ Setup Complete!"
echo ""
echo "Next steps:"
echo "1. Read DEPLOYMENT_GUIDE.md for detailed instructions"
echo "2. Create accounts on Vercel and Railway"
echo "3. Follow the deployment steps for each platform"
echo "4. Set environment variables in each platform dashboard"
echo "5. Test end-to-end functionality"
echo ""
echo "For more help, see: DEPLOYMENT_GUIDE.md"
