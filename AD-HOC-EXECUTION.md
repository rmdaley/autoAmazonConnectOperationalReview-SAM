# Ad-Hoc Execution Guide

Once deployed with the default EventBridge schedule, you have multiple ways to run reviews on-demand.

## Quick Reference

| Method | Best For | Command |
|--------|----------|---------|
| AWS CLI | Quick one-off runs | `aws lambda invoke ...` |
| Bash Script | Interactive menu | `./scripts/run-review.sh` |
| Python Script | Cross-platform | `./scripts/run-review.py` |
| AWS Console | Visual interface | Click "Test" in Lambda console |
| SAM CLI | Local testing | `sam local invoke` |

---

## Method 1: AWS CLI (Simplest)

### Basic Invocation

```bash
# Get the function name
FUNCTION_NAME=$(aws cloudformation describe-stacks \
  --stack-name amazon-connect-ops-review \
  --query 'Stacks[0].Outputs[?OutputKey==`OrchestratorFunctionArn`].OutputValue' \
  --output text | awk -F: '{print $NF}')

# Run review for last 7 days
aws lambda invoke \
  --function-name $FUNCTION_NAME \
  --cli-binary-format raw-in-base64-out \
  --payload '{"daysBack": 7}' \
  response.json

# View response
cat response.json | jq '.'
```

### Quick Commands

**Last 24 hours (quick test):**
```bash
aws lambda invoke \
  --function-name amazon-connect-ops-review-orchestrator \
  --cli-binary-format raw-in-base64-out \
  --payload '{"daysBack": 1}' \
  response.json && cat response.json | jq '.'
```

**Last 7 days (standard):**
```bash
aws lambda invoke \
  --function-name amazon-connect-ops-review-orchestrator \
  --cli-binary-format raw-in-base64-out \
  --payload '{"daysBack": 7}' \
  response.json && cat response.json | jq '.'
```

**Last 30 days (full review):**
```bash
aws lambda invoke \
  --function-name amazon-connect-ops-review-orchestrator \
  --cli-binary-format raw-in-base64-out \
  --payload '{"daysBack": 30}' \
  response.json && cat response.json | jq '.'
```

### Using Event Files

```bash
# Quick test (1 day)
aws lambda invoke \
  --function-name amazon-connect-ops-review-orchestrator \
  --payload file://events/quick-test.json \
  response.json

# Standard test (7 days)
aws lambda invoke \
  --function-name amazon-connect-ops-review-orchestrator \
  --payload file://events/test-event.json \
  response.json

# Full review (30 days)
aws lambda invoke \
  --function-name amazon-connect-ops-review-orchestrator \
  --payload file://events/full-review.json \
  response.json
```

---

## Method 2: Bash Script (Interactive)

### Installation

```bash
chmod +x scripts/run-review.sh
```

### Interactive Menu

```bash
./scripts/run-review.sh
```

**Menu Options:**
1. Quick test (last 24 hours)
2. Standard review (last 7 days)
3. Full review (last 30 days)
4. Custom days back
5. View logs
6. Check function status
7. List recent reports
8. Exit

### Command Line Usage

```bash
# Run with specific days
./scripts/run-review.sh -d 14

# Use custom stack name
./scripts/run-review.sh -d 7 -s my-custom-stack

# Show help
./scripts/run-review.sh -h
```

### Examples

```bash
# Quick 24-hour test
./scripts/run-review.sh -d 1

# Weekly review
./scripts/run-review.sh -d 7

# Monthly review
./scripts/run-review.sh -d 30

# Custom 14-day review
./scripts/run-review.sh -d 14
```

---

## Method 3: Python Script (Cross-Platform)

### Installation

```bash
chmod +x scripts/run-review.py
pip install boto3  # If not already installed
```

### Interactive Menu

```bash
python3 scripts/run-review.py
```

### Command Line Usage

```bash
# Run with specific days
python3 scripts/run-review.py --days 7

# Quick test
python3 scripts/run-review.py --quick

# Full review
python3 scripts/run-review.py --full

# List recent reports
python3 scripts/run-review.py --list-reports

# Check function status
python3 scripts/run-review.py --status

# Custom stack name
python3 scripts/run-review.py --days 14 --stack my-custom-stack
```

### Examples

```bash
# Standard 7-day review
python3 scripts/run-review.py --days 7

# Quick 24-hour test
python3 scripts/run-review.py --quick

# Full 30-day review
python3 scripts/run-review.py --full

# Custom 14-day review
python3 scripts/run-review.py --days 14

# List last 10 reports
python3 scripts/run-review.py --list-reports

# Check if function is healthy
python3 scripts/run-review.py --status
```

---

## Method 4: AWS Console

### Steps

1. **Navigate to Lambda Console**
   - Go to: https://console.aws.amazon.com/lambda/
   - Search for: `amazon-connect-ops-review-orchestrator`

2. **Create Test Event**
   - Click "Test" tab
   - Click "Create new event"
   - Event name: `QuickTest`
   - Event JSON:
     ```json
     {
       "daysBack": 7
     }
     ```
   - Click "Save"

3. **Run Test**
   - Select your test event
   - Click "Test" button
   - View results in "Execution results" tab

### Pre-configured Test Events

**Quick Test (24 hours):**
```json
{
  "daysBack": 1,
  "comment": "Quick 24-hour test"
}
```

**Standard Review (7 days):**
```json
{
  "daysBack": 7,
  "comment": "Standard weekly review"
}
```

**Full Review (30 days):**
```json
{
  "daysBack": 30,
  "comment": "Full monthly review"
}
```

---

## Method 5: SAM CLI (Local Testing)

### Test Locally

```bash
# Test with default event
sam local invoke OrchestratorFunction \
  --event events/test-event.json

# Test with quick event
sam local invoke OrchestratorFunction \
  --event events/quick-test.json

# Test with full review
sam local invoke OrchestratorFunction \
  --event events/full-review.json
```

### Test Against Deployed Stack

```bash
# Invoke deployed function using SAM
sam remote invoke OrchestratorFunction \
  --stack-name amazon-connect-ops-review \
  --event-file events/test-event.json
```

---

## Method 6: EventBridge Manual Trigger

### Trigger Scheduled Rule Manually

```bash
# Get the rule name
RULE_NAME=$(aws events list-rules \
  --query 'Rules[?contains(Name, `amazon-connect-ops-review`)].Name' \
  --output text)

# Trigger the rule manually
aws events put-events \
  --entries "[{\"Source\":\"manual.trigger\",\"DetailType\":\"Manual Trigger\",\"Detail\":\"{}\"}]"
```

---

## Method 7: Step Functions (Future Enhancement)

If you migrate to Step Functions, you can trigger via:

```bash
# Start execution
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:123456789012:stateMachine:ConnectOpsReview \
  --input '{"daysBack": 7}'
```

---

## Monitoring Execution

### View Logs in Real-Time

```bash
# Tail orchestrator logs
sam logs --name OrchestratorFunction --tail

# Or using AWS CLI
aws logs tail /aws/lambda/amazon-connect-ops-review-orchestrator --follow
```

### Check Execution Status

```bash
# Get recent invocations
aws lambda list-invocations \
  --function-name amazon-connect-ops-review-orchestrator \
  --max-items 5
```

### View CloudWatch Metrics

```bash
# Get invocation count
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=amazon-connect-ops-review-orchestrator \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

---

## Retrieving Reports

### List Recent Reports

```bash
# Get bucket name
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name amazon-connect-ops-review \
  --query 'Stacks[0].Outputs[?OutputKey==`ReportBucket`].OutputValue' \
  --output text)

# List reports
aws s3 ls s3://$BUCKET/ --recursive | grep "\.html$"
```

### Download Latest Report

```bash
# Get latest report
LATEST=$(aws s3 ls s3://$BUCKET/ --recursive | grep "\.html$" | sort | tail -1 | awk '{print $4}')

# Download
aws s3 cp s3://$BUCKET/$LATEST ./latest-report.html

# Open in browser
open latest-report.html  # macOS
xdg-open latest-report.html  # Linux
start latest-report.html  # Windows
```

### Generate Pre-Signed URL

```bash
# Create shareable link (valid for 1 hour)
aws s3 presign s3://$BUCKET/$LATEST --expires-in 3600
```

---

## Automation Examples

### Cron Job (Linux/macOS)

```bash
# Edit crontab
crontab -e

# Add daily review at 2 AM
0 2 * * * /path/to/scripts/run-review.sh -d 7 >> /var/log/connect-review.log 2>&1
```

### Scheduled Task (Windows)

```powershell
# Create scheduled task
$action = New-ScheduledTaskAction -Execute "python" -Argument "C:\path\to\scripts\run-review.py --days 7"
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "ConnectOpsReview"
```

### GitHub Actions

```yaml
name: Weekly Connect Review
on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM
  workflow_dispatch:  # Manual trigger

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Run Review
        run: python3 scripts/run-review.py --days 7
```

---

## Best Practices

### 1. Test with Short Periods First

```bash
# Start with 1 day to verify everything works
./scripts/run-review.sh -d 1

# Then try 7 days
./scripts/run-review.sh -d 7

# Finally full 30 days
./scripts/run-review.sh -d 30
```

### 2. Monitor Execution Time

```bash
# Time the execution
time aws lambda invoke \
  --function-name amazon-connect-ops-review-orchestrator \
  --cli-binary-format raw-in-base64-out \
  --payload '{"daysBack": 7}' \
  response.json
```

### 3. Check Costs

```bash
# View Lambda costs
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --filter file://lambda-filter.json
```

### 4. Set Up Alerts

```bash
# Create CloudWatch alarm for errors
aws cloudwatch put-metric-alarm \
  --alarm-name connect-review-errors \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=amazon-connect-ops-review-orchestrator
```

---

## Troubleshooting

### Function Not Found

```bash
# Verify stack exists
aws cloudformation describe-stacks --stack-name amazon-connect-ops-review

# List all Lambda functions
aws lambda list-functions --query 'Functions[?contains(FunctionName, `connect`)].FunctionName'
```

### Timeout Issues

```bash
# Check function timeout setting
aws lambda get-function-configuration \
  --function-name amazon-connect-ops-review-orchestrator \
  --query 'Timeout'

# View execution duration in logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/amazon-connect-ops-review-orchestrator \
  --filter-pattern "Duration"
```

### Permission Errors

```bash
# Check function role
aws lambda get-function \
  --function-name amazon-connect-ops-review-orchestrator \
  --query 'Configuration.Role'

# View role policies
aws iam list-attached-role-policies --role-name <role-name>
```

---

## Summary

**Recommended for most users:**
```bash
# Interactive menu
./scripts/run-review.sh
```

**For automation:**
```bash
# Python script with specific days
python3 scripts/run-review.py --days 7
```

**For quick tests:**
```bash
# AWS CLI one-liner
aws lambda invoke \
  --function-name amazon-connect-ops-review-orchestrator \
  --cli-binary-format raw-in-base64-out \
  --payload '{"daysBack": 1}' \
  response.json
```

All methods produce the same result - a comprehensive HTML report in your S3 bucket! 🚀
