# Quick Reference Card

## Deployment

### Quick Start (Recommended)

```bash
# Interactive deployment script
./deploy.sh
```

The script handles validation, build, and guided deployment.

<details>
<summary>Manual deployment commands</summary>

```bash
# Build and deploy
sam build && sam deploy

# First time
sam build && sam deploy --guided

# Update code only
sam build && sam deploy --no-confirm-changeset
```

</details>

## Running Reviews

### Interactive Script (Recommended)

```bash
# Interactive menu with options
./scripts/run-review.sh
```

Provides menu for:
- Quick test (1 day)
- Standard review (7 days)
- Full review (30 days)
- Custom date range
- View recent reports

### Python CLI

```bash
# Standard review
python3 scripts/run-review.py --days 7

# Custom range
python3 scripts/run-review.py --days 30
```

<details>
<summary>Direct AWS CLI commands</summary>

### One-Line Commands

```bash
# Quick test (24 hours)
aws lambda invoke --function-name amazon-connect-ops-review-orchestrator --cli-binary-format raw-in-base64-out --payload '{"daysBack":1}' response.json

# Standard (7 days)
aws lambda invoke --function-name amazon-connect-ops-review-orchestrator --cli-binary-format raw-in-base64-out --payload '{"daysBack":7}' response.json

# Full (30 days)
aws lambda invoke --function-name amazon-connect-ops-review-orchestrator --cli-binary-format raw-in-base64-out --payload '{"daysBack":30}' response.json
```

### Event Files

```bash
# Quick test
aws lambda invoke --function-name amazon-connect-ops-review-orchestrator --payload file://events/quick-test.json response.json

# Standard test
aws lambda invoke --function-name amazon-connect-ops-review-orchestrator --payload file://events/test-event.json response.json

# Full review
aws lambda invoke --function-name amazon-connect-ops-review-orchestrator --payload file://events/full-review.json response.json
```

</details>

## Viewing Results

### Logs

```bash
# Tail logs
sam logs --name OrchestratorFunction --tail

# Last 100 lines
sam logs --name OrchestratorFunction --tail -n 100
```

### Reports

```bash
# List reports
BUCKET=$(aws cloudformation describe-stacks --stack-name amazon-connect-ops-review --query 'Stacks[0].Outputs[?OutputKey==`ReportBucket`].OutputValue' --output text) && aws s3 ls s3://$BUCKET/

# Download and open latest
BUCKET=$(aws cloudformation describe-stacks --stack-name amazon-connect-ops-review --query 'Stacks[0].Outputs[?OutputKey==`ReportBucket`].OutputValue' --output text) && LATEST=$(aws s3 ls s3://$BUCKET/ | sort | tail -1 | awk '{print $4}') && aws s3 cp s3://$BUCKET/$LATEST ./report.html && open report.html
```

## Monitoring

```bash
# Check function status
aws lambda get-function --function-name amazon-connect-ops-review-orchestrator --query 'Configuration.{State:State,LastModified:LastModified}'

# View metrics
aws cloudwatch get-metric-statistics --namespace AWS/Lambda --metric-name Invocations --dimensions Name=FunctionName,Value=amazon-connect-ops-review-orchestrator --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) --end-time $(date -u +%Y-%m-%dT%H:%M:%S) --period 3600 --statistics Sum
```

## Troubleshooting

```bash
# Validate template
sam validate

# Check stack status
aws cloudformation describe-stacks --stack-name amazon-connect-ops-review --query 'Stacks[0].StackStatus'

# View stack events
aws cloudformation describe-stack-events --stack-name amazon-connect-ops-review --max-items 10

# Search logs for errors
aws logs filter-log-events --log-group-name /aws/lambda/amazon-connect-ops-review-orchestrator --filter-pattern "ERROR"
```

## Cleanup

### Quick Cleanup Script

```bash
# Clean local artifacts
./cleanup.sh
```

<details>
<summary>Manual cleanup commands</summary>

```bash
# Clean local artifacts
rm -rf .aws-sam response.json

# Delete AWS stack
sam delete

# Or manually
aws cloudformation delete-stack --stack-name amazon-connect-ops-review

# Delete S3 bucket (optional)
BUCKET=$(aws cloudformation describe-stacks --stack-name amazon-connect-ops-review --query 'Stacks[0].Outputs[?OutputKey==`ReportBucket`].OutputValue' --output text) && aws s3 rb s3://$BUCKET --force
```

</details>

See **[CLEANUP-GUIDE.md](CLEANUP-GUIDE.md)** for detailed cleanup instructions.

## Documentation

- **[README.md](README.md)** - Complete SAM deployment and usage guide
- **[README-ORIG.md](README-ORIG.md)** - Original CloudFormation template documentation
- **[DOCUMENTATION.md](DOCUMENTATION.md)** - Complete documentation guide
- **[AD-HOC-EXECUTION.md](AD-HOC-EXECUTION.md)** - All execution methods
- **[QUICK-REFERENCE.md](QUICK-REFERENCE.md)** - This file
- **[CLEANUP-GUIDE.md](CLEANUP-GUIDE.md)** - Cleanup instructions
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions
