#!/bin/bash

# Cleanup script for SAM project
# Removes build artifacts and cache files

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🧹 Cleaning up SAM build artifacts...${NC}\n"

# Remove SAM build directory
if [ -d ".aws-sam" ]; then
    SIZE=$(du -sh .aws-sam 2>/dev/null | cut -f1)
    rm -rf .aws-sam
    echo -e "${GREEN}✅ Removed .aws-sam/ (${SIZE})${NC}"
else
    echo -e "${YELLOW}ℹ️  .aws-sam/ not found${NC}"
fi

# Remove Python cache
echo -e "\n${BLUE}🧹 Cleaning Python cache...${NC}"
PYCACHE_COUNT=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l | tr -d ' ')
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
echo -e "${GREEN}✅ Removed ${PYCACHE_COUNT} __pycache__ directories${NC}"

# Remove test response files
if [ -f "response.json" ]; then
    rm -f response.json
    echo -e "${GREEN}✅ Removed response.json${NC}"
fi

# Remove macOS metadata
if [ "$(uname)" == "Darwin" ]; then
    DS_COUNT=$(find . -name ".DS_Store" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$DS_COUNT" -gt 0 ]; then
        find . -name ".DS_Store" -delete 2>/dev/null
        echo -e "${GREEN}✅ Removed ${DS_COUNT} .DS_Store files${NC}"
    fi
fi

echo -e "\n${GREEN}✨ Cleanup complete!${NC}\n"
echo -e "${BLUE}Kept:${NC}"
echo -e "  ${GREEN}✅${NC} samconfig.toml (deployment config)"
echo -e "  ${GREEN}✅${NC} template.yaml (SAM template)"
echo -e "  ${GREEN}✅${NC} functions/ (Lambda code)"
echo -e "  ${GREEN}✅${NC} scripts/ (helper scripts)"
echo -e "  ${GREEN}✅${NC} events/ (test events)"
echo -e "  ${GREEN}✅${NC} All documentation\n"
