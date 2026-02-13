"""
CloudTrail Analyzer Lambda Function
Analyzes CloudTrail events for Amazon Connect API throttling
"""
import os
import json
import boto3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import defaultdict

from storage_helper import store_result

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global client - will be initialized with correct region in lambda_handler
cloudtrail_client = None


def lookup_connect_cloudtrail_events(account_id: str, days_back: int, aws_region: str) -> List[Dict[str, Any]]:
    """
    Lookup CloudTrail events for Amazon Connect
    
    Args:
        account_id: AWS account ID
        days_back: Number of days to look back
        aws_region: AWS region
        
    Returns:
        List of parsed Connect CloudTrail events
    """
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days_back)
    
    logger.info(f"Looking up CloudTrail events from {start_time} to {end_time}")
    
    connect_events = []
    
    try:
        # Lookup attributes for Connect events
        lookup_attributes = [
            {
                'AttributeKey': 'EventSource',
                'AttributeValue': 'connect.amazonaws.com'
            }
        ]
        
        # Lookup events using paginator
        paginator = cloudtrail_client.get_paginator('lookup_events')
        
        for page in paginator.paginate(
            LookupAttributes=lookup_attributes,
            StartTime=start_time,
            EndTime=end_time
        ):
            for event in page['Events']:
                # Parse and enrich event data
                event_data = parse_connect_event(event, aws_region)
                if event_data:
                    connect_events.append(event_data)
        
        logger.info(f"Found {len(connect_events)} Connect CloudTrail events")
        return connect_events
        
    except Exception as e:
        logger.error(f"Error looking up CloudTrail events: {e}")
        return []


def parse_connect_event(event: Dict[str, Any], target_region: str) -> Dict[str, Any]:
    """
    Parse and enrich Connect CloudTrail event
    
    Args:
        event: Raw CloudTrail event
        target_region: Target AWS region to filter by
        
    Returns:
        Parsed event data or None if parsing fails
    """
    try:
        cloud_trail_event = json.loads(event.get('CloudTrailEvent', '{}'))
        
        # Extract key information
        event_data = {
            'eventId': event.get('EventId'),
            'eventName': event.get('EventName'),
            'eventTime': event.get('EventTime').isoformat() if event.get('EventTime') else None,
            'username': event.get('Username'),
            'eventSource': cloud_trail_event.get('eventSource'),
            'awsRegion': cloud_trail_event.get('awsRegion'),
            'sourceIPAddress': cloud_trail_event.get('sourceIPAddress'),
            'userAgent': cloud_trail_event.get('userAgent'),
            'requestId': cloud_trail_event.get('requestID'),
            'errorCode': cloud_trail_event.get('errorCode'),
            'errorMessage': cloud_trail_event.get('errorMessage')
        }
        
        return event_data
        
    except Exception as e:
        logger.error(f"Error parsing event: {e}")
        return None


def analyze_api_throttles(instance_id: str, account_id: str, days_back: int, aws_region: str) -> Dict[str, Any]:
    """
    Analyze Amazon Connect API throttling from CloudTrail
    
    Args:
        instance_id: Connect instance ID
        account_id: AWS account ID
        days_back: Number of days to analyze
        aws_region: AWS region
        
    Returns:
        Analysis results with throttle counts by API
    """
    try:
        # Get CloudTrail events
        events = lookup_connect_cloudtrail_events(account_id, days_back, aws_region)
        
        logger.info(f"Analyzing {len(events)} Amazon Connect events for throttling")
        
        # Count throttled events by API
        throttle_counts = defaultdict(int)
        total_throttled = 0
        
        for event in events:
            # Check for throttling error in the target region
            if (event.get('errorCode') == 'TooManyRequestsException' and 
                event.get('awsRegion') == aws_region):
                
                event_name = event.get('eventName', 'Unknown')
                throttle_counts[event_name] += 1
                total_throttled += 1
                
                logger.debug(f"Found throttled event: {event_name}")
        
        # Convert to list for JSON serialization
        throttle_list = [
            {'event_name': event_name, 'count': count}
            for event_name, count in sorted(throttle_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
        # Generate recommendations
        recommendations = []
        if total_throttled > 0:
            recommendations = [
                'Review current service quotas for your AWS Account',
                'Consider exponential backoff and retry logic',
                'Consider requesting quota increases via AWS Support',
                'Learn more: https://docs.aws.amazon.com/connect/latest/APIReference/best-practices-connect-apis.html'
            ]
        
        return {
            'total_events_analyzed': len(events),
            'total_throttled': total_throttled,
            'throttled_by_api': throttle_list,
            'account_id': account_id,
            'region': aws_region,
            'recommendations': recommendations
        }
        
    except Exception as e:
        logger.error(f"Error analyzing API throttles: {e}")
        return {'error': str(e)}


def lambda_handler(event, context):
    """
    Main handler for CloudTrail analysis
    
    Expected event structure:
    {
        "reviewId": "20240210-120000",
        "instanceId": "xxxxx-xxxx-xxxx",
        "accountId": "123456789012",
        "awsRegion": "us-west-2",
        "daysBack": 14,
        "ttl": 1234567890
    }
    """
    try:
        logger.info("Starting CloudTrail analysis")
        
        review_id = event['reviewId']
        instance_id = event['instanceId']
        account_id = event['accountId']
        aws_region = event['awsRegion']
        days_back = event.get('daysBack', 14)
        ttl = event['ttl']
        
        # Create client with correct region
        global cloudtrail_client
        cloudtrail_client = boto3.client('cloudtrail', region_name=aws_region)
        
        # Perform analysis
        analysis_result = analyze_api_throttles(instance_id, account_id, days_back, aws_region)
        
        # Store results in DynamoDB
        store_result(review_id, 'cloudtrail', analysis_result, ttl)
        
        logger.info(f"CloudTrail analysis completed: {analysis_result.get('total_throttled', 0)} throttled events found")
        
        return {
            'statusCode': 200,
            'componentType': 'cloudtrail'
        }
        
    except Exception as e:
        logger.error(f"CloudTrail analyzer error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'error': str(e)
        }
