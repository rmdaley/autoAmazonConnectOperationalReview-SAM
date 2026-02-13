# Documentation Guide

## Available Documentation

### Primary Documentation

1. **[README.md](README.md)** - SAM Serverless Application (RECOMMENDED)
   - Complete deployment guide
   - All features and enhancements
   - Configuration options
   - Usage instructions
   - Monitoring and troubleshooting
   - Cost optimization
   - Recent enhancements (February 2026)

2. **[README-ORIG.md](README-ORIG.md)** - Original CloudFormation Template
   - Original CFT documentation
   - Uses pre-built Lambda code from S3
   - Single Lambda function deployment
   - Legacy reference

### Usage Guides

3. **[AD-HOC-EXECUTION.md](AD-HOC-EXECUTION.md)**
   - 7 different methods to run reviews on-demand
   - AWS CLI commands
   - Interactive scripts (bash and Python)
   - AWS Console usage
   - Monitoring execution
   - Retrieving reports

4. **[STORAGE-BACKEND-GUIDE.md](STORAGE-BACKEND-GUIDE.md)**
   - Storage backend options (S3 vs DynamoDB)
   - Configuration and deployment
   - Cost comparison and optimization
   - Migration between backends
   - Troubleshooting storage issues
   - Best practices

5. **[QUICK-REFERENCE.md](QUICK-REFERENCE.md)**
   - One-line commands
   - Quick copy-paste snippets
   - Common operations cheat sheet

### Maintenance Guides

6. **[CLEANUP-GUIDE.md](CLEANUP-GUIDE.md)**
   - Local cleanup after testing
   - AWS resource cleanup
   - Cleanup scripts
   - Best practices

7. **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**
   - Common deployment issues
   - Runtime errors
   - Solutions and fixes
   - Debugging tips

## Quick Navigation

### For New Users (SAM Deployment - Recommended)
1. Read [README.md](README.md) for overview and prerequisites
2. Follow deployment instructions in README.md
3. Use [AD-HOC-EXECUTION.md](AD-HOC-EXECUTION.md) to run reviews on-demand

### For Original CloudFormation Users
1. Read [README-ORIG.md](README-ORIG.md) for CloudFormation template details
2. Deploy using AWS Console or CLI with the CFT template

### Daily Use
- [QUICK-REFERENCE.md](QUICK-REFERENCE.md) - Quick commands
- [AD-HOC-EXECUTION.md](AD-HOC-EXECUTION.md) - Run reviews

### Maintenance
- [CLEANUP-GUIDE.md](CLEANUP-GUIDE.md) - Clean up artifacts
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Fix issues

## Documentation Structure

```
├── README.md                    # SAM deployment guide (PRIMARY)
├── template.yaml                # SAM template
├── samconfig.toml               # SAM configuration
│
├── README-ORIG.md               # Original CloudFormation docs
├── CFT-AmazonConnectOperationalReview.yml      # Original CFT
├── CFT-AmazonConnectOperationsReview.yml       # CFT with inline code
│
├── AD-HOC-EXECUTION.md          # Execution methods (SAM)
├── STORAGE-BACKEND-GUIDE.md     # Storage backend comparison (S3 vs DynamoDB)
├── QUICK-REFERENCE.md           # Command cheat sheet (SAM)
├── CLEANUP-GUIDE.md             # Cleanup instructions (SAM)
├── TROUBLESHOOTING.md           # Common issues (SAM)
└── DOCUMENTATION.md             # This file
```

## Key Features (SAM Version)

### Analysis Capabilities
- **Instance Details** - Complete configuration with console links
- **Resilience** - Multi-AZ architecture and ACGR recommendations
- **Service Quotas** - Color-coded usage with direct console links
- **Performance Metrics** - 14-day analysis with CloudWatch links
- **Phone Numbers** - Carrier diversity and cost optimization
- **Contact Flows** - Logging compliance with edit links
- **API Throttling** - CloudTrail analysis with console links
- **Error Analysis** - CloudWatch Logs Insights with pre-configured queries

### Console Integration
All report sections include direct AWS Console links:
- Instance management
- Service quota requests
- Contact flow editing
- Phone number management
- CloudWatch metrics and logs
- CloudTrail event history

### Recent Enhancements (February 2026)
- **Dual Storage Backend Support** - Choose between S3 (default, 80% cost savings) or DynamoDB (faster queries)
- UTF-8 charset for proper HTML rendering
- Styled console links (replaced emoji with » symbol)
- ACGR recommendations when no replica configured
- Identity Management Type display
- Instance ARN and Access URL
- Contact Flow State and Status columns
- Enhanced IAM permissions (`ds:DescribeDirectories`)
- Improved error handling and validation

## Additional Resources

### Scripts
- `scripts/run-review.sh` - Interactive bash script
- `scripts/run-review.py` - Cross-platform Python script
- `cleanup.sh` - Cleanup script
- `deploy.sh` - Deployment helper

### Test Events
- `events/test-event.json` - Standard 7-day review
- `events/quick-test.json` - Quick 24-hour test
- `events/full-review.json` - Full 30-day review

### Configuration
- `template.yaml` - SAM template (infrastructure as code)
- `samconfig.toml` - Deployment configuration
- `.gitignore` - Git ignore rules

## Architecture Overview

### Lambda Functions (SAM Version)
1. **Orchestrator** - Coordinates all analyzers
2. **Quota Analyzer** - Service quotas and usage
3. **Metrics Analyzer** - CloudWatch metrics
4. **Phone Analyzer** - Phone numbers and carrier diversity
5. **Flow Analyzer** - Contact flow logging compliance
6. **CloudTrail Analyzer** - API throttling detection
7. **Log Analyzer** - Contact flow error analysis
8. **Report Generator** - HTML report with console links

### Data Flow
```
EventBridge Schedule → Orchestrator → Parallel Analyzers → Storage Backend
                                                              (S3 or DynamoDB)
                                                                    ↓
                                                            Report Generator → S3
```

## Getting Help

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
2. Review [QUICK-REFERENCE.md](QUICK-REFERENCE.md) for quick commands
3. Check CloudWatch Logs for runtime errors
4. Review AWS SAM documentation: https://docs.aws.amazon.com/serverless-application-model/

## Version Comparison

### SAM Version (Recommended)
- ✅ Modular architecture with 8 Lambda functions
- ✅ Parallel execution for faster analysis
- ✅ Full source code included
- ✅ Easy customization and extension
- ✅ Comprehensive console integration
- ✅ Enhanced error handling
- ✅ Recent enhancements (Feb 2026)

### CloudFormation Version (Legacy)
- Single Lambda function
- Pre-built code from S3
- Limited customization
- Original implementation

## Support

For issues or questions:
- Check CloudWatch Logs for error details
- Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Check AWS SAM documentation
- Review [README.md](README.md) for detailed information
