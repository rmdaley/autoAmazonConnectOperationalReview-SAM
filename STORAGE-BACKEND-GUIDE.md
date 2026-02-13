# Storage Backend Guide

## Overview

The Amazon Connect Operational Review application supports two storage backends for intermediate analysis results:

1. **S3 Storage** (Default) - Cost-optimized, simple
2. **DynamoDB Storage** (Optional) - Faster queries, historical data

## Quick Comparison

| Feature | S3 (Default) | DynamoDB |
|---------|--------------|----------|
| **Cost** | ~$0.05/month | ~$0.25/month |
| **Performance** | ~2s retrieval | ~500ms retrieval |
| **Use Case** | Weekly reviews | Daily+ reviews |
| **Historical Queries** | Limited | Full support |
| **Setup Complexity** | Simple | Simple |
| **Cleanup** | Lifecycle policies | TTL automatic |

## S3 Storage Backend (Default)

### When to Use

- Running weekly or less frequent reviews
- Cost optimization is a priority
- Don't need to query historical review data
- Prefer simple deployment

### How It Works

1. **Storage Structure:**
   ```
   s3://your-bucket/reviews/{reviewId}/{componentType}.json
   ```

2. **Example:**
   ```
   s3://my-bucket/reviews/20240213-120000/quota.json
   s3://my-bucket/reviews/20240213-120000/metrics.json
   s3://my-bucket/reviews/20240213-120000/phone.json
   ```

3. **Encryption:** AES256 server-side encryption

4. **Cleanup:** S3 lifecycle policies (90-day expiration)

### Configuration

**During deployment:**
```bash
sam deploy --parameter-overrides StorageBackend=s3
```

**In samconfig.toml:**
```toml
[default.deploy.parameters]
parameter_overrides = "StorageBackend=s3"
```

### Accessing Results

```bash
# Get bucket name
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name amazon-connect-ops-review \
  --query 'Stacks[0].Outputs[?OutputKey==`ReportBucket`].OutputValue' \
  --output text)

# List all reviews
aws s3 ls s3://$BUCKET/reviews/

# List results for specific review
aws s3 ls s3://$BUCKET/reviews/20240213-120000/

# Download specific result
aws s3 cp s3://$BUCKET/reviews/20240213-120000/quota.json - | jq '.'
```

### Cost Breakdown

For weekly reviews:
- Storage: ~$0.05/month (intermediate results + reports)
- API calls: Included in Lambda costs
- Data transfer: Minimal (same region)

**Total storage cost: ~$0.05/month**

---

## DynamoDB Storage Backend

### When to Use

- Running daily or more frequent reviews
- Need to query across multiple reviews
- Faster retrieval is important
- Already using DynamoDB for other purposes

### How It Works

1. **Table Structure:**
   - Partition Key: `reviewId` (String)
   - Sort Key: `componentType` (String)
   - TTL: Automatic expiration after 90 days

2. **Example Items:**
   ```json
   {
     "reviewId": "20240213-120000",
     "componentType": "quota",
     "data": { ... },
     "ttl": 1234567890
   }
   ```

3. **Pricing:** On-demand (pay per request)

### Configuration

**During deployment:**
```bash
sam deploy --parameter-overrides StorageBackend=dynamodb
```

**In samconfig.toml:**
```toml
[default.deploy.parameters]
parameter_overrides = "StorageBackend=dynamodb"
```

### Accessing Results

```bash
# Query specific review
aws dynamodb query \
  --table-name amazon-connect-ops-review-results \
  --key-condition-expression "reviewId = :rid" \
  --expression-attribute-values '{":rid":{"S":"20240213-120000"}}'

# Get specific component
aws dynamodb get-item \
  --table-name amazon-connect-ops-review-results \
  --key '{"reviewId":{"S":"20240213-120000"},"componentType":{"S":"quota"}}'

# Scan all reviews (expensive!)
aws dynamodb scan \
  --table-name amazon-connect-ops-review-results \
  --projection-expression "reviewId,componentType"
```

### Cost Breakdown

For weekly reviews:
- Storage: ~$0.25/month (on-demand pricing)
- Read/Write requests: Included in estimate
- TTL: Free

**Total storage cost: ~$0.25/month**

---

## Switching Backends

### From DynamoDB to S3

**Why switch:**
- Reduce costs by 80%
- Simplify infrastructure
- Don't need historical queries

**Steps:**

1. **Update deployment:**
   ```bash
   sam deploy --parameter-overrides StorageBackend=s3
   ```

2. **Verify new reviews use S3:**
   ```bash
   # Run a test review
   aws lambda invoke \
     --function-name amazon-connect-ops-review-orchestrator \
     --cli-binary-format raw-in-base64-out \
     --payload '{"daysBack": 1}' \
     response.json
   
   # Check S3 for results
   aws s3 ls s3://$BUCKET/reviews/ --recursive
   ```

3. **Optional - Export old DynamoDB data:**
   ```bash
   # Export to S3 for archival
   aws dynamodb export-table-to-point-in-time \
     --table-arn arn:aws:dynamodb:region:account:table/amazon-connect-ops-review-results \
     --s3-bucket your-archive-bucket \
     --s3-prefix dynamodb-exports/
   ```

4. **DynamoDB table remains** (for backward compatibility)

### From S3 to DynamoDB

**Why switch:**
- Need faster queries
- Want historical data analysis
- Running frequent reviews

**Steps:**

1. **Update deployment:**
   ```bash
   sam deploy --parameter-overrides StorageBackend=dynamodb
   ```

2. **Verify new reviews use DynamoDB:**
   ```bash
   # Run a test review
   aws lambda invoke \
     --function-name amazon-connect-ops-review-orchestrator \
     --cli-binary-format raw-in-base64-out \
     --payload '{"daysBack": 1}' \
     response.json
   
   # Check DynamoDB for results
   aws dynamodb scan \
     --table-name amazon-connect-ops-review-results \
     --limit 5
   ```

3. **S3 intermediate results** will no longer be created (reports still in S3)

---

## Migration Considerations

### Data Migration

**Important:** Switching backends does NOT migrate existing data.

- Old DynamoDB data remains in DynamoDB
- Old S3 data remains in S3
- New reviews use the configured backend

**To access old data:**
- Query the original storage location
- Or export/archive before switching

### No Downtime

Switching backends requires redeployment but:
- No data loss
- No service interruption
- Scheduled reviews continue working
- Old data remains accessible

---

## Troubleshooting

### S3 Backend Issues

**Problem:** Results not appearing in S3

**Solution:**
```bash
# Check Lambda logs
sam logs --name OrchestratorFunction --tail

# Verify S3 bucket exists
aws s3 ls s3://$BUCKET/

# Check IAM permissions
aws lambda get-function \
  --function-name amazon-connect-ops-review-orchestrator \
  --query 'Configuration.Role'
```

**Problem:** Access denied errors

**Solution:**
- Verify Lambda role has `s3:PutObject` permission
- Check bucket policy allows Lambda access
- Ensure bucket is in same region

### DynamoDB Backend Issues

**Problem:** Results not appearing in DynamoDB

**Solution:**
```bash
# Check table exists
aws dynamodb describe-table \
  --table-name amazon-connect-ops-review-results

# Check Lambda logs
sam logs --name OrchestratorFunction --tail

# Verify IAM permissions
aws iam list-attached-role-policies \
  --role-name <lambda-role-name>
```

**Problem:** Throttling errors

**Solution:**
- DynamoDB uses on-demand pricing (auto-scales)
- Check CloudWatch metrics for throttling
- Verify table is in on-demand mode

### Backend Configuration Issues

**Problem:** Not sure which backend is active

**Solution:**
```bash
# Check Lambda environment variable
aws lambda get-function-configuration \
  --function-name amazon-connect-ops-review-orchestrator \
  --query 'Environment.Variables.STORAGE_BACKEND'

# Check stack parameters
aws cloudformation describe-stacks \
  --stack-name amazon-connect-ops-review \
  --query 'Stacks[0].Parameters[?ParameterKey==`StorageBackend`]'
```

---

## Best Practices

### For S3 Backend

1. **Enable lifecycle policies:**
   ```bash
   aws s3api put-bucket-lifecycle-configuration \
     --bucket $BUCKET \
     --lifecycle-configuration file://lifecycle.json
   ```

2. **Monitor storage costs:**
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/S3 \
     --metric-name BucketSizeBytes \
     --dimensions Name=BucketName,Value=$BUCKET \
     --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 86400 \
     --statistics Average
   ```

3. **Use versioning for important data:**
   ```bash
   aws s3api put-bucket-versioning \
     --bucket $BUCKET \
     --versioning-configuration Status=Enabled
   ```

### For DynamoDB Backend

1. **Monitor capacity:**
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/DynamoDB \
     --metric-name ConsumedReadCapacityUnits \
     --dimensions Name=TableName,Value=amazon-connect-ops-review-results \
     --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 300 \
     --statistics Sum
   ```

2. **Enable point-in-time recovery:**
   ```bash
   aws dynamodb update-continuous-backups \
     --table-name amazon-connect-ops-review-results \
     --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true
   ```

3. **Set up CloudWatch alarms:**
   ```bash
   aws cloudwatch put-metric-alarm \
     --alarm-name dynamodb-throttles \
     --alarm-description "Alert on DynamoDB throttling" \
     --metric-name UserErrors \
     --namespace AWS/DynamoDB \
     --statistic Sum \
     --period 300 \
     --threshold 10 \
     --comparison-operator GreaterThanThreshold
   ```

---

## FAQ

**Q: Can I use both backends simultaneously?**  
A: No, you must choose one backend per deployment.

**Q: Will switching backends delete my old data?**  
A: No, old data remains in the original storage location.

**Q: Can I query S3 data like DynamoDB?**  
A: Limited. Use AWS Athena for SQL queries on S3 data.

**Q: Which backend is faster?**  
A: DynamoDB (~500ms) is faster than S3 (~2s) for retrieval.

**Q: Which backend is cheaper?**  
A: S3 is ~80% cheaper for typical usage patterns.

**Q: Do I need both S3 and DynamoDB resources?**  
A: S3 bucket is always needed (for final reports). DynamoDB table is optional.

**Q: Can I migrate data between backends?**  
A: Not automatically. You can export/import manually if needed.

**Q: What happens to scheduled reviews when I switch?**  
A: They continue working with the new backend immediately.

---

## Support

For issues or questions:
- Check CloudWatch Logs for detailed errors
- Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Verify IAM permissions for chosen backend
- Check AWS service quotas

## Related Documentation

- [README.md](README.md) - Main documentation
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues
- [CLEANUP-GUIDE.md](CLEANUP-GUIDE.md) - Cleanup procedures
- [AD-HOC-EXECUTION.md](AD-HOC-EXECUTION.md) - Running reviews
