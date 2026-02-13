# Amazon Connect Operational Review - SAM Deployment Guide

Complete serverless application for automated operational reviews of Amazon Connect instances with comprehensive analysis and actionable insights.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Deployment](#deployment)
- [Usage](#usage)
- [Report Features](#report-features)
- [Monitoring](#monitoring)
- [Customization](#customization)
- [Cleanup](#cleanup)
- [Troubleshooting](#troubleshooting)
- [Documentation Index](#documentation-index)

## Features

### Comprehensive Analysis

- **Instance Details & Configuration**
  - Instance alias, status, ARN, and service role
  - Identity management type (SAML, CONNECT_MANAGED, EXISTING_DIRECTORY)
  - Call configuration (inbound/outbound enabled)
  - Contact flow logs and Contact Lens settings
  - Instance access URL with console link
  - Replication configuration for disaster recovery
  - Robust validation and error handling

- **Resilience Analysis**
  - Multi-AZ architecture documentation
  - Amazon Connect Global Resiliency (ACGR) recommendations
  - Automatic recommendation when no replica is configured

- **Service Quota Analysis**
  - Color-coded usage percentages (green/orange/red)
  - Tracks 10+ resource types (Contact Flows, Users, Queues, Routing Profiles, Security Profiles, Hours of Operation, Prompts, Lex Bots V1/V2, Phone Numbers, Agent Statuses, Contact Flow Modules, Quick Connects)
  - Direct console links to request quota increases

- **Performance Metrics** (Last 14 days)
  - Concurrent calls analysis with peak detection
  - Missed calls tracking with daily breakdown
  - Throttled calls severity assessment
  - Queue size monitoring
  - Calls per interval analysis
  - Direct CloudWatch console links
  - Real-time and historical metrics dashboards in Connect console

- **Phone Number Analysis**
  - All phone number types (TOLL_FREE, DID, UIFN, SHORT_CODE, THIRD_PARTY_*)
  - Carrier diversity analysis with detailed tables
  - Cost optimization insights
  - International presence detection
  - SMS capability identification
  - Priority-based recommendations (high/medium/low)
  - Direct console link to manage phone numbers

- **Contact Flow Analysis**
  - Logging compliance checking
  - Identifies flows missing logging configuration
  - Shows both State and Status for each flow
  - Direct links to edit individual flows in console
  - Recommendations for enabling logging

- **CloudTrail API Throttling** (Account Level)
  - Detects throttled Amazon Connect API calls
  - Groups by event type with counts
  - Recommendations for exponential backoff and quota increases
  - Direct CloudTrail console link

- **CloudWatch Logs Analysis**
  - Contact flow error detection and categorization
  - Error types distribution
  - Top flows with errors
  - Sample recent errors
  - Pre-configured Logs Insights query link

### Console Integration

All sections include direct links to AWS Console:
- **Instance Overview** - Open instance in Connect console
- **Service Quotas** - Request quota increases
- **Contact Flows** - Edit specific flows
- **Phone Numbers** - Manage phone numbers
- **CloudWatch Metrics** - View detailed metrics
- **Connect Metrics Dashboards** - Real-time and historical metrics in Connect console
- **CloudWatch Logs** - Pre-configured error queries
- **CloudTrail** - View API call history

## Storage Backend Options

The application supports two storage backends for intermediate analysis results:

### S3 Storage (Default - Recommended)

**Best for:** Cost optimization, infrequent reviews, simple deployments

**Advantages:**
- 80% lower storage costs compared to DynamoDB
- Simple S3 lifecycle policies for automatic cleanup
- No capacity planning required
- Encrypted at rest (AES256)
- Ideal for write-once, read-once workflows

**How it works:**
- Results stored as JSON files: `s3://bucket/reviews/{reviewId}/{componentType}.json`
- Each analyzer writes its results independently
- Report generator reads all results from S3
- S3 lifecycle policies manage automatic deletion after 90 days

### DynamoDB Storage (Optional)

**Best for:** Frequent reviews, historical queries, faster retrieval

**Advantages:**
- Faster query performance (~500ms vs ~2s for S3)
- Built-in TTL for automatic expiration
- Query across multiple reviews
- On-demand pricing for flexibility

**How it works:**
- Results stored in DynamoDB table with composite key (reviewId, componentType)
- TTL automatically expires records after 90 days
- Supports historical data analysis

### Choosing a Backend

**Use S3 (default) if:**
- Running weekly or less frequent reviews
- Cost optimization is priority
- Don't need to query historical data
- Simple deployment preferred

**Use DynamoDB if:**
- Running daily or more frequent reviews
- Need to query across multiple reviews
- Faster retrieval is important
- Already using DynamoDB for other purposes

### Configuration

Set during deployment:

```bash
# S3 backend (default)
sam deploy --parameter-overrides StorageBackend=s3

# DynamoDB backend
sam deploy --parameter-overrides StorageBackend=dynamodb
```

Or in `samconfig.toml`:

```toml
[default.deploy.parameters]
parameter_overrides = "StorageBackend=s3"
```

## Prerequisites

- AWS CLI configured with appropriate credentials
- AWS SAM CLI installed ([Installation Guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html))
- Python 3.13 or later
- Amazon Connect instance

### Install SAM CLI

```bash
# macOS
brew install aws-sam-cli

# Linux
pip install aws-sam-cli

# Verify installation
sam --version
```

## Installation

### Quick Start

The easiest way to get started is using the deployment script:

```bash
./deploy.sh
```

The script handles all installation and deployment steps automatically.

### Manual Installation

<details>
<summary>Click to expand manual installation steps</summary>

#### 1. Clone or Download

Ensure you have all project files in your working directory.

#### 2. Build the Application

```bash
sam build
```

This command:
- Packages all Lambda functions
- Installs dependencies from requirements.txt
- Prepares deployment artifacts

</details>

## Deployment

### Quick Start (Recommended)

Use the interactive deployment script for the easiest experience:

```bash
./deploy.sh
```

The script will:
- Validate prerequisites (AWS CLI, SAM CLI)
- Build the application
- Guide you through configuration
- Deploy the stack
- Provide next steps and testing commands

### Manual Deployment (Advanced)

<details>
<summary>Click to expand manual deployment steps</summary>

#### First-Time Deployment (Guided)

```bash
sam build
sam deploy --guided
```

You'll be prompted for:
- **Stack name**: e.g., `amazon-connect-ops-review`
- **AWS Region**: e.g., `us-east-1`
- **AmazonConnectInstanceARN**: Your Connect instance ARN
- **AmazonConnectCloudWatchLogGroup**: Your Connect log group
- **CreateS3Bucket**: Yes (creates bucket) or No (use existing)
- **AmazonS3ForReports**: Bucket name or leave default for auto-generated
- **ReviewSchedule**: Cron expression (default: weekly Monday 9 AM UTC)
- **StorageBackend**: s3 (default, lower cost) or dynamodb (faster queries)
- Confirm changeset
- Allow SAM to create IAM roles

See **[STORAGE-BACKEND-GUIDE.md](STORAGE-BACKEND-GUIDE.md)** for detailed comparison of storage options.

#### Subsequent Deployments

```bash
sam build
sam deploy
```

Uses saved configuration from `samconfig.toml`.

#### Verify Deployment

```bash
# List stack resources
aws cloudformation describe-stack-resources \
  --stack-name amazon-connect-ops-review

# Get orchestrator function ARN
aws cloudformation describe-stacks \
  --stack-name amazon-connect-ops-review \
  --query 'Stacks[0].Outputs[?OutputKey==`OrchestratorFunctionArn`].OutputValue' \
  --output text
```

</details>

## Usage

### Scheduled Execution

The application automatically runs based on the `ReviewSchedule` parameter (default: weekly on Monday at 9 AM UTC).

To modify the schedule, redeploy with:

```bash
./deploy.sh
# Or manually:
sam deploy --parameter-overrides ReviewSchedule="cron(0 9 ? * MON *)"
```

### Ad-Hoc Execution (On-Demand)

**Recommended: Use the interactive script**

```bash
./scripts/run-review.sh
```

The script provides an interactive menu to:
- Run quick test (1 day)
- Run standard review (7 days)
- Run full review (30 days)
- Run custom date range
- View recent reports

**Alternative Methods**

<details>
<summary>Click to expand alternative execution methods</summary>

See **[AD-HOC-EXECUTION.md](AD-HOC-EXECUTION.md)** for complete guide.

1. **AWS CLI:**
```bash
aws lambda invoke \
  --function-name amazon-connect-ops-review-orchestrator \
  --cli-binary-format raw-in-base64-out \
  --payload '{"daysBack": 7}' \
  response.json
```

2. **Python script:**
```bash
python3 scripts/run-review.py --days 7
```

3. **AWS Console:**
   - Navigate to Lambda console
   - Find `amazon-connect-ops-review-orchestrator`
   - Click "Test" and use event: `{"daysBack": 7}`

</details>

### View Results

1. Check CloudWatch Logs for execution details
2. Access the HTML report from S3:
   - Bucket: Your specified S3 bucket
   - Key: `connect-ops-review-YYYYMMDD-HHMMSS.html`

## Report Features

### Interactive HTML Report

The generated report includes:

1. **Instance Information Summary**
   - Instance ID, Region, Account ID
   - Generation timestamp

2. **Instance Details & Configuration**
   - Complete instance configuration
   - Console link to manage instance
   - Replication settings

3. **Resilience**
   - Multi-AZ architecture explanation
   - ACGR recommendation (if no replica configured)

4. **Operational Excellence - Capacity Analysis**
   - Color-coded quota usage
   - Direct link to Service Quotas console

5. **Performance Metrics**
   - Concurrent calls, missed calls, throttled calls
   - CloudWatch console links
   - Real-time and historical metrics dashboards in Connect console

6. **CloudTrail API Throttling**
   - Account-level API throttling detection
   - CloudTrail console link

7. **Cost Considerations - Phone Number Analysis**
   - Carrier diversity table
   - Cost optimization insights
   - Phone management console link

8. **Contact Flow Analysis**
   - Flows missing logging
   - Direct links to edit flows
   - State and Status columns

9. **Contact Flow Error Analysis**
   - Error categorization
   - Logs Insights console link with pre-configured query

### Console Links

All sections include actionable console links (marked with »):
- Open resources directly in AWS Console
- Pre-configured queries for CloudWatch Logs Insights
- One-click access to management pages

## Monitoring

### CloudWatch Logs

Each function has its own log group:
- `/aws/lambda/amazon-connect-ops-review-orchestrator`
- `/aws/lambda/amazon-connect-ops-review-quota-analyzer`
- `/aws/lambda/amazon-connect-ops-review-metrics-analyzer`
- `/aws/lambda/amazon-connect-ops-review-phone-analyzer`
- `/aws/lambda/amazon-connect-ops-review-flow-analyzer`
- `/aws/lambda/amazon-connect-ops-review-cloudtrail-analyzer`
- `/aws/lambda/amazon-connect-ops-review-log-analyzer`
- `/aws/lambda/amazon-connect-ops-review-report-generator`

### View Logs

```bash
# Tail orchestrator logs
sam logs --name OrchestratorFunction --tail

# View specific time range
sam logs --name OrchestratorFunction \
  --start-time '10min ago' \
  --end_time '1min ago'
```

### DynamoDB Table

Results are stored in DynamoDB with 90-day TTL:

```bash
# Query results
aws dynamodb query \
  --table-name amazon-connect-ops-review-results \
  --key-condition-expression "reviewId = :rid" \
  --expression-attribute-values '{":rid":{"S":"20240210-120000"}}'
```

## Customization

### Add New Analyzer

1. Create new function directory:
```bash
mkdir -p functions/new_analyzer
```

2. Create `app.py` and `requirements.txt`

3. Add to `template.yaml`:
```yaml
NewAnalyzerFunction:
  Type: AWS::Serverless::Function
  Properties:
    FunctionName: !Sub '${AWS::StackName}-new-analyzer'
    CodeUri: functions/new_analyzer/
    Handler: app.lambda_handler
    Role: !GetAtt AnalyzerFunctionRole.Arn
```

4. Update orchestrator to invoke new analyzer

5. Rebuild and deploy:
```bash
sam build && sam deploy
```

### Modify Analysis Logic

Edit the respective analyzer function in `functions/<analyzer>/app.py`, then:

```bash
sam build
sam deploy
```

### Change Report Format

Modify `functions/report_generator/app.py` to customize HTML output.

## Cost Optimization

### Estimated Costs (Monthly)

For weekly reviews of a typical Connect instance:

**With S3 Backend (Default)**:
- Lambda: ~$0.75 (8 functions × 4 executions × ~30-60s each)
- S3 (intermediate storage): ~$0.02 (7-day retention)
- S3 (reports): ~$0.01 (90-day retention)
- CloudWatch Logs: ~$0.50 (log storage and ingestion)
- **Total: ~$1.28/month**

**With DynamoDB Backend (Optional)**:
- Lambda: ~$0.75 (8 functions × 4 executions × ~30-60s each)
- DynamoDB: ~$0.25 (on-demand pricing with 90-day TTL)
- S3 (reports): ~$0.01 (90-day retention)
- CloudWatch Logs: ~$0.50 (log storage and ingestion)
- **Total: ~$1.51/month**

See **[STORAGE-BACKEND-GUIDE.md](STORAGE-BACKEND-GUIDE.md)** for detailed cost comparison.

### Optimization Tips

1. Adjust `ReviewSchedule` to reduce frequency
2. Set shorter DynamoDB TTL to reduce storage
3. Enable S3 lifecycle policies to archive old reports
4. Reduce Lambda memory if functions don't need 512MB

## Cleanup

### Local Cleanup

Remove build artifacts after testing:

```bash
# Quick cleanup
rm -rf .aws-sam response.json

# Or use the cleanup script
./cleanup.sh

# Full cleanup including Python cache
rm -rf .aws-sam response.json && \
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null && \
find . -type f -name "*.pyc" -delete
```

### Remove Deployed Stack

Remove all resources:

```bash
sam delete
```

Or manually:

```bash
aws cloudformation delete-stack \
  --stack-name amazon-connect-ops-review
```

### Remove S3 Bucket

The S3 bucket is retained by default. To delete it:

```bash
# Get bucket name
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name amazon-connect-ops-review \
  --query 'Stacks[0].Outputs[?OutputKey==`ReportBucket`].OutputValue' \
  --output text)

# Empty and delete
aws s3 rb s3://$BUCKET --force
```

See **[CLEANUP-GUIDE.md](CLEANUP-GUIDE.md)** for complete cleanup instructions.

## Troubleshooting

### Common Issues

See **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** for detailed solutions.

**Quick fixes:**

1. **Build fails**: `sam build --use-container --clean`
2. **Permission errors**: Check IAM role has required permissions
3. **Function timeouts**: Increase timeout in template.yaml
4. **Empty reports**: Check CloudWatch logs for errors

### Instance Details Not Showing

If instance details section is empty:

1. Check CloudWatch logs for `/aws/lambda/amazon-connect-ops-review-report-generator`
2. Verify IAM permissions include:
   - `connect:DescribeInstance`
   - `ds:DescribeDirectories` (required for directory service integration)
3. Verify instance ID is valid UUID format
4. Check instance exists in the specified region

## Documentation Index

### Primary Documentation
- **[README.md](README.md)** - Main SAM documentation (this file)
- **[STORAGE-BACKEND-GUIDE.md](STORAGE-BACKEND-GUIDE.md)** - Storage backend comparison (S3 vs DynamoDB)
- **[AD-HOC-EXECUTION.md](AD-HOC-EXECUTION.md)** - All execution methods
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions
- **[QUICK-REFERENCE.md](QUICK-REFERENCE.md)** - Quick command reference
- **[DOCUMENTATION.md](DOCUMENTATION.md)** - Documentation index

### Original CloudFormation
- **[README-ORIG.md](README-ORIG.md)** - Original CFT documentation
- **[CFT-AmazonConnectOperationsReview.yml](CFT-AmazonConnectOperationsReview.yml)** - Original template

## Architecture

### Lambda Functions

1. **Orchestrator** - Coordinates all analyzers and report generation
2. **Quota Analyzer** - Analyzes service quotas and usage
3. **Metrics Analyzer** - Retrieves CloudWatch metrics
4. **Phone Analyzer** - Analyzes phone numbers and carrier diversity
5. **Flow Analyzer** - Checks contact flow logging compliance
6. **CloudTrail Analyzer** - Detects API throttling
7. **Log Analyzer** - Analyzes contact flow errors
8. **Report Generator** - Generates HTML report with console links

### Data Flow

```
EventBridge Schedule → Orchestrator → Parallel Analyzers → Storage Backend
                                                              (S3 or DynamoDB)
                                                                    ↓
                                                            Report Generator → S3
```

## IAM Permissions

### Analyzer Functions
- Amazon Connect: Read-only access
- CloudWatch: Read metrics and logs
- CloudTrail: Read events
- Service Quotas: Read quotas
- Pinpoint: Phone number validation
- DynamoDB: Write results

### Report Generator
- Connect: `connect:DescribeInstance`
- Directory Service: `ds:DescribeDirectories`
- DynamoDB: Read results
- S3: Write reports

## Support

For issues or questions:
- Check CloudWatch Logs for error details
- Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Check AWS SAM documentation: https://docs.aws.amazon.com/serverless-application-model/

## License

This project is licensed under the MIT License.

## Recent Enhancements

### February 2026

#### Dual Storage Backend Support
- Added flexible storage backend selection (S3 or DynamoDB)
- S3 is now the default backend for 80% cost reduction
- DynamoDB remains available for faster queries and historical data
- Configurable via `STORAGE_BACKEND` parameter during deployment
- New `storage_helper.py` provides unified interface for both backends
- Backward compatible with existing deployments

#### Previous Enhancements
- Added Connect console links for real-time and historical metrics dashboards
- Added UTF-8 charset declaration for proper HTML rendering
- Replaced emoji icons with styled text links (» symbol)
- Added comprehensive AWS Console deep links throughout report
- Added ACGR recommendation when no replica is configured
- Added Identity Management Type to instance details
- Added Instance ARN and Access URL to instance details
- Added Contact Flow State column (in addition to Status)
- Fixed IAM permissions to include `ds:DescribeDirectories`
- Enhanced error handling and validation
- Improved carrier diversity analysis display


## Authors

- [@ganejaya](https://www.github.com/ganejaya)
- [@rmdaley](https://www.github.com/rmdaley)
