#!/bin/bash

# OralEvidenceDB Auto-Commit Script
# Automatically commits and pushes changes to GitHub after edits

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🦷 OralEvidenceDB Auto-Commit${NC}"
echo "================================="

# Get current timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Check if there are changes
if [[ -z $(git status -s) ]]; then
    echo -e "${YELLOW}ℹ️  No changes to commit${NC}"
    exit 0
fi

# Show changes
echo -e "${BLUE}📄 Changes detected:${NC}"
git status --short

# Add all changes
echo -e "${BLUE}📦 Adding changes...${NC}"
git add -A

# Create commit message
if [ -z "$1" ]; then
    # Default commit message
    COMMIT_MSG="chore: Auto-commit changes - $TIMESTAMP"
else
    # Use provided commit message
    COMMIT_MSG="$1"
fi

# Commit changes
echo -e "${BLUE}💾 Committing changes...${NC}"
git commit -m "$COMMIT_MSG"

# Push to GitHub
echo -e "${BLUE}🚀 Pushing to GitHub...${NC}"
git push origin main

echo -e "${GREEN}✅ Successfully committed and pushed to GitHub!${NC}"
echo -e "${GREEN}🔗 Repository: https://github.com/choxos/OralEvidenceDB${NC}"
echo ""
echo -e "${YELLOW}💡 Usage examples:${NC}"
echo "   ./auto-commit.sh                           # Auto-commit with timestamp"
echo "   ./auto-commit.sh \"feat: Add new feature\"   # Custom commit message"
echo ""
