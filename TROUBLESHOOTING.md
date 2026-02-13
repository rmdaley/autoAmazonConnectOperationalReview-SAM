# Troubleshooting Guide

## Common Deployment Issues

### Error: Bucket already exists

**Full Error:**
```
CREATE_FAILED: ReportsBucket (AWS::S3::Bucket)
Bucket name already exists
```

**Cause:**
The bucket name you chose (or auto-generated) is already taken globally.

**Solution 1:** Use existing bucket
```bash
sam deploy --parameter-overrides \
  CreateS3Bucket=No \
  AmazonS3ForReports=your-existing-bucket-name
```

**Solution 2:** Choose different name
```bash
sam deploy --parameter-overrides \
  CreateS3Bucket=Yes \
  AmazonS3ForReports=my-unique-bucket-name
```

**Solution 3:** Let SAM auto-generate with account ID
```bash
sam deploy --parameter-overrides \
  CreateS3Bucket=Yes \
  AmazonS3ForReports=auto-generated
```
This creates: `<stack-name>-reports-<account-id>` which is globally unique.

---

### Error: SAM CLI not found

**Error:**
```
zsh: command not found: sam
```

**Solution:**

**macOS:**
```bash
brew install aws-sam-cli
sam --version
```

**Linux:**
```bash
pip install aws-sam-cli
sam --version
```

**Windows:**
```bash
pip install aws-sam-cli
sam --version
```

---

### Error: AWS credentials not configured

**Error:**
```
Unable to locate credentials
```

**Solution:**
```bash
aws configure

# Enter:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region (e.g., us-east-1)
# - Default output format (json)

# Verify:
aws sts get-caller-identity
```

---

### Error: Build failed

**Error:**
```
Build Failed
Error: PythonPipBuilder:ResolveDependencies - ...
```

**Solution 1:** Clean build
```bash
sam build --use-container --clean
```

**Solution 2:** Use container build (if Docker installed)
```bash
sam build --use-container
```

**Solution 3:** Check Python version
```bash
python3 --version
# Should be 3.13 or compatible
```

---

### Error: Stack already exists

**Error:**
```
Stack amazon-connect-ops-review already exists
```

**Solution 1:** Update existing stack
```bash
sam deploy  # Without --guided
```

**Solution 2:** Use different stack name
```bash
sam deploy --guided --stack-name amazon-connect-ops-review-v2
```

**Solution 3:** Delete and recreate
```bash
sam delete
sam deploy --guided
```

---

### Error: Insufficient permissions

**Error:**
```
User: arn:aws:iam::123456789012:user/myuser is not authorized to perform: cloudformation:CreateStack
```

**Solution:**
Ensure your IAM user/role has these permissions:
- `cloudformation:*`
- `lambda:*`
- `iam:CreateRole`
- `iam:AttachRolePolicy`
- `s3:CreateBucket`
- `dynamodb:CreateTable`

**Quick fix:** Attach `PowerUserAccess` policy (for development):
```bash
aws iam attach-user-policy \
  --user-name myuser \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess
```

---

### Error: Template validation failed

**Error:**
```
Template format error: ...
```

**Solution:**
```bash
# Validate template
sam validate

# Check for syntax errors
cat template.yaml | grep -A 5 -B 5 "error_line"

# Ensure proper YAML indentation
```

---

### Error: Function timeout

**Error:**
```
Task timed out after 300.00 seconds
```

**Solution:**
The function is taking longer than expected. Check:

1. **CloudWatch Logs:**
```bash
sam logs --name OrchestratorFunction --tail
```

2. **Increase timeout** (if needed):
Edit `template.yaml`:
```yaml
Globals:
  Function:
    Timeout: 600  # Increase from 300 to 600 seconds
```

3. **Check Connect instance size:**
Large instances with many resources take longer to analyze.

---

### Error: DynamoDB throttling

**Error:**
```
ProvisionedThroughputExceededException
```

**Solution:**
The DynamoDB table is using on-demand billing, so this shouldn't happen. If it does:

```bash
# Check table status
aws dynamodb describe-table \
  --table-name amazon-connect-ops-review-results

# Verify billing mode is PAY_PER_REQUEST
```

---

### Error: S3 access denied

**Error:**
```
Access Denied when writing to S3
```

**Solution:**

1. **Check bucket policy:**
```bash
aws s3api get-bucket-policy --bucket <bucket-name>
```

2. **Verify IAM role permissions:**
```bash
aws cloudformation describe-stacks \
  --stack-name amazon-connect-ops-review \
  --query 'Stacks[0].Outputs[?OutputKey==`ReportGeneratorFunctionRole`]'
```

3. **Ensure bucket exists:**
```bash
aws s3 ls s3://<bucket-name>
```

---

### Error: Connect instance not found

**Error:**
```
ResourceNotFoundException: Instance not found
```

**Solution:**

1. **Verify instance ARN:**
```bash
aws connect list-instances

# Copy the correct ARN
```

2. **Check region:**
Ensure you're deploying in the same region as your Connect instance:
```bash
sam deploy --guided --region us-east-1
```

3. **Verify permissions:**
Ensure Lambda role has `connect:DescribeInstance` permission.

---

## Debugging Tips

### View CloudWatch Logs

```bash
# Tail logs in real-time
sam logs --name OrchestratorFunction --tail

# View specific time range
sam logs --name QuotaAnalyzerFunction \
  --start-time '1hour ago' \
  --end-time 'now'

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/amazon-connect-ops-review-orchestrator \
  --filter-pattern "ERROR"
```

### Check Stack Events

```bash
# View recent stack events
aws cloudformation describe-stack-events \
  --stack-name amazon-connect-ops-review \
  --max-items 20

# Watch stack creation
watch -n 5 'aws cloudformation describe-stacks \
  --stack-name amazon-connect-ops-review \
  --query "Stacks[0].StackStatus"'
```

### Test Locally

```bash
# Test orchestrator locally
sam local invoke OrchestratorFunction \
  --event events/test-event.json

# Start local API
sam local start-api

# Test with curl
curl -X POST http://localhost:3000/review \
  -d '{"daysBack": 7}'
```

### Verify Resources

```bash
# List all stack resources
aws cloudformation list-stack-resources \
  --stack-name amazon-connect-ops-review

# Check Lambda functions
aws lambda list-functions \
  --query 'Functions[?starts_with(FunctionName, `amazon-connect-ops-review`)]'

# Check DynamoDB table
aws dynamodb describe-table \
  --table-name amazon-connect-ops-review-results

# Check S3 bucket
aws s3 ls s3://<bucket-name>
```

---

## Getting More Help

### Enable Debug Mode

```bash
# Build with debug
sam build --debug

# Deploy with debug
sam deploy --debug

# Invoke with debug
sam local invoke --debug
```

### Check SAM Version

```bash
sam --version
# Ensure you have latest version

# Update SAM CLI
brew upgrade aws-sam-cli  # macOS
pip install --upgrade aws-sam-cli  # Linux/Windows
```

### Validate Template

```bash
# Validate SAM template
sam validate

# Validate CloudFormation
aws cloudformation validate-template \
  --template-body file://template.yaml
```

### Clean Start

```bash
# Remove build artifacts
rm -rf .aws-sam

# Clean build
sam build --use-container --clean

# Fresh deployment
sam deploy --guided
```

---

## Common Runtime Issues

### Error: Unable to import module 'app': No module named 'utils'

**Full Error:**
```
[ERROR] Runtime.ImportModuleError: Unable to import module 'app': No module named 'utils'
Traceback (most recent call last):
```

**Cause:**
The Lambda Layer containing shared utilities is not properly attached or the shared code structure is incorrect.

**Solution:**
Rebuild and redeploy the application to ensure the Lambda Layer is properly created:

```bash
# Clean previous build
rm -rf .aws-sam

# Rebuild with fresh layer
sam build

# Redeploy
sam deploy
```

**Verification:**
After deployment, check that the SharedLayer is attached to functions:
```bash
aws lambda get-function-configuration \
  --function-name amazon-connect-ops-review-orchestrator \
  --query 'Layers[*].Arn'
```

---

## Still Having Issues?

1. **Check CloudWatch Logs** - Most errors are logged there
2. **Review Stack Events** - Shows what failed during deployment
3. **Validate Template** - Ensures YAML is correct
4. **Test Locally** - Isolate the issue
5. **Check Permissions** - Verify IAM roles and policies

For specific errors not covered here, check:
- AWS SAM Documentation: https://docs.aws.amazon.com/serverless-application-model/
- AWS CloudFormation Docs: https://docs.aws.amazon.com/cloudformation/
- CloudWatch Logs for detailed error messages
