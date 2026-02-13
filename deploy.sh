#!/bin/bash

# Amazon Connect Operational Review - SAM Deployment Script
# This script helps deploy the SAM application with proper validation

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Amazon Connect Ops Review - Deployment${NC}"
echo -e "${GREEN}========================================${NC}\n"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found. Please install it first.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ AWS CLI installed${NC}"

# Check SAM CLI
if ! command -v sam &> /dev/null; then
    echo -e "${RED}❌ SAM CLI not found. Please install it first.${NC}"
    echo -e "${YELLOW}Install with: brew install aws-sam-cli (macOS) or pip install aws-sam-cli${NC}"
    exit 1
fi
echo -e "${GREEN}✓ SAM CLI installed${NC}"

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS credentials not configured${NC}"
    exit 1
fi
echo -e "${GREEN}✓ AWS credentials configured${NC}"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}  Account ID: ${ACCOUNT_ID}${NC}\n"

# Validate template
echo -e "${YELLOW}Validating SAM template...${NC}"
if sam validate; then
    echo -e "${GREEN}✓ Template is valid${NC}\n"
else
    echo -e "${RED}❌ Template validation failed${NC}"
    exit 1
fi

# Build application
echo -e "${YELLOW}Building SAM application...${NC}"
if sam build; then
    echo -e "${GREEN}✓ Build successful${NC}\n"
else
    echo -e "${RED}❌ Build failed${NC}"
    exit 1
fi

# Deployment options
echo -e "${YELLOW}Deployment Options:${NC}"
echo "1. Guided deployment (first time or to change parameters)"
echo "2. Quick deployment (uses saved config)"
echo "3. Deploy to specific environment"
echo "4. Exit"
echo ""
read -p "Select option (1-4): " option

case $option in
    1)
        echo -e "\n${YELLOW}Starting guided deployment...${NC}"
        echo -e "${YELLOW}You will be prompted for:${NC}"
        echo "  - Stack name"
        echo "  - AWS Region"
        echo "  - Amazon Connect Instance ARN"
        echo "  - CloudWatch Log Group"
        echo "  - S3 Bucket for reports"
        echo "  - Review schedule (cron expression)"
        echo ""
        sam deploy --guided
        ;;
    2)
        echo -e "\n${YELLOW}Starting quick deployment...${NC}"
        sam deploy
        ;;
    3)
        echo -e "\n${YELLOW}Available environments:${NC}"
        echo "1. Development"
        echo "2. Staging"
        echo "3. Production"
        read -p "Select environment (1-3): " env_option
        
        case $env_option in
            1)
                ENV="dev"
                ;;
            2)
                ENV="staging"
                ;;
            3)
                ENV="production"
                ;;
            *)
                echo -e "${RED}Invalid option${NC}"
                exit 1
                ;;
        esac
        
        echo -e "\n${YELLOW}Deploying to ${ENV}...${NC}"
        sam deploy --config-env $ENV
        ;;
    4)
        echo -e "${YELLOW}Exiting...${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac

# Check deployment status
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ Deployment successful!${NC}"
    echo -e "${GREEN}========================================${NC}\n"
    
    # Get stack outputs
    echo -e "${YELLOW}Stack Outputs:${NC}"
    aws cloudformation describe-stacks \
        --stack-name amazon-connect-ops-review \
        --query 'Stacks[0].Outputs' \
        --output table
    
    echo -e "\n${YELLOW}Next Steps:${NC}"
    echo "1. Test the deployment:"
    echo -e "   ${GREEN}aws lambda invoke --function-name amazon-connect-ops-review-orchestrator --cli-binary-format raw-in-base64-out --payload '{\"daysBack\": 7}' response.json${NC}"
    echo ""
    echo "2. View logs:"
    echo -e "   ${GREEN}sam logs --name OrchestratorFunction --tail${NC}"
    echo ""
    echo "3. Check S3 for reports:"
    echo -e "   ${GREEN}aws s3 ls s3://<your-bucket>/connect-ops-review-${NC}"
    echo ""
else
    echo -e "\n${RED}========================================${NC}"
    echo -e "${RED}❌ Deployment failed${NC}"
    echo -e "${RED}========================================${NC}\n"
    echo -e "${YELLOW}Check the error messages above for details${NC}"
    exit 1
fi
