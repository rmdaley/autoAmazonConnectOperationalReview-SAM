# Cleanup Guide

## AWS Resources Cleanup

### After Testing Deployment

If you deployed to AWS for testing and want to remove everything:

#### Option 1: SAM Delete (Recommended)

```bash
# Delete the entire stack
sam delete

# Or with specific stack name
sam delete --stack-name amazon-connect-ops-review

# Non-interactive (no prompts)
sam delete --no-prompts
```

**What gets deleted:**
- ✅ All Lambda functions
- ✅ IAM roles
- ✅ DynamoDB table
- ✅ EventBridge rule
- ✅ CloudWatch Log Groups
- ⚠️ S3 bucket (retained by default to prevent data loss)

#### Option 2: CloudFormation Delete

```bash
# Delete via CloudFormation
aws cloudformation delete-stack \
  --stack-name amazon-connect-ops-review

# Wait for deletion to complete
aws cloudformation wait stack-delete-complete \
  --stack-name amazon-connect-ops-review
```

#### Option 3: Manual S3 Bucket Cleanup

The S3 bucket is retained by default. To delete it:

```bash
# Get bucket name
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name amazon-connect-ops-review \
  --query 'Stacks[0].Outputs[?OutputKey==`ReportBucket`].OutputValue' \
  --output text)

# Empty the bucket
aws s3 rm s3://$BUCKET --recursive

# Delete the bucket
aws s3 rb s3://$BUCKET

# Or force delete (empties and deletes)
aws s3 rb s3://$BUCKET --force
```

---

## Cleanup Scenarios

### Scenario 1: Just Built, Haven't Deployed

**What to clean:**
```bash
rm -rf .aws-sam
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete
```

**What to keep:**
- Everything else (no AWS resources created)

### Scenario 2: Deployed for Testing, Want to Remove

**Clean local artifacts:**
```bash
rm -rf .aws-sam response.json
```

**Delete AWS resources:**
```bash
sam delete
```

**Optional - Delete S3 bucket:**
```bash
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name amazon-connect-ops-review \
  --query 'Stacks[0].Outputs[?OutputKey==`ReportBucket`].OutputValue' \
  --output text)
aws s3 rb s3://$BUCKET --force
```

### Scenario 3: Want Fresh Build

**Clean and rebuild:**
```bash
# Clean
rm -rf .aws-sam

# Rebuild
sam build

# Deploy
sam deploy
```

### Scenario 4: Want Fresh Deployment Config

**Reset configuration:**
```bash
# Backup current config (optional)
cp samconfig.toml samconfig.toml.backup

# Remove config
rm samconfig.toml

# Deploy with guided setup
sam deploy --guided
```

### Scenario 5: Complete Reset

**Remove everything:**
```bash
# Local cleanup
rm -rf .aws-sam
rm -f response.json samconfig.toml
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete

# AWS cleanup
sam delete --no-prompts

# S3 cleanup
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name amazon-connect-ops-review \
  --query 'Stacks[0].Outputs[?OutputKey==`ReportBucket`].OutputValue' \
  --output text 2>/dev/null)
if [ ! -z "$BUCKET" ]; then
  aws s3 rb s3://$BUCKET --force
fi
```

---

## .gitignore Recommendations

Add these to your `.gitignore`:

```gitignore
# SAM build artifacts
.aws-sam/
samconfig.toml

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Testing
response.json
*.log

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Environment
.env
.env.local
```

---

## Disk Space Check

### Before Cleanup

```bash
# Check .aws-sam size
du -sh .aws-sam

# Check all Python cache
find . -type d -name "__pycache__" -exec du -sh {} \; 2>/dev/null | awk '{sum+=$1} END {print sum " total"}'
```

### After Cleanup

```bash
# Verify cleanup
ls -la .aws-sam 2>/dev/null || echo "✅ .aws-sam removed"
find . -type d -name "__pycache__" 2>/dev/null | wc -l
```

---

## Best Practices

### During Development

1. **Clean before major changes:**
   ```bash
   rm -rf .aws-sam && sam build
   ```

2. **Keep samconfig.toml in version control** (if not sensitive)
   - Or add to `.gitignore` and document parameters

3. **Regular cleanup:**
   ```bash
   # Weekly cleanup
   rm -rf .aws-sam
   find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
   ```

### Before Committing

```bash
# Clean before git commit
rm -rf .aws-sam response.json
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete
```

### Before Deployment

```bash
# Fresh build before production deployment
rm -rf .aws-sam
sam build --use-container
sam deploy
```

---

## Quick Reference

### Essential Cleanup Commands

```bash
# Quick local cleanup
rm -rf .aws-sam response.json

# Full local cleanup
rm -rf .aws-sam response.json && \
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null && \
find . -type f -name "*.pyc" -delete

# Delete AWS stack
sam delete

# Delete S3 bucket
aws s3 rb s3://$(aws cloudformation describe-stacks \
  --stack-name amazon-connect-ops-review \
  --query 'Stacks[0].Outputs[?OutputKey==`ReportBucket`].OutputValue' \
  --output text) --force

# Complete reset
rm -rf .aws-sam response.json && sam delete && \
aws s3 rb s3://your-bucket-name --force
```

---

## Summary

**After `sam build` and testing:**

1. **Local cleanup (always safe):**
   ```bash
   rm -rf .aws-sam response.json
   ```

2. **AWS cleanup (if you want to remove test deployment):**
   ```bash
   sam delete
   ```

3. **S3 cleanup (optional - bucket is retained by default):**
   ```bash
   aws s3 rb s3://your-bucket-name --force
   ```

**Keep these files:**
- ✅ `samconfig.toml` (unless you want to reconfigure)
- ✅ `template.yaml`
- ✅ `functions/`
- ✅ All documentation

**Safe to delete:**
- 🗑️ `.aws-sam/`
- 🗑️ `__pycache__/`
- 🗑️ `*.pyc`
- 🗑️ `response.json`
