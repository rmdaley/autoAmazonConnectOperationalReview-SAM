"""
Log Analyzer Lambda Function
Analyzes CloudWatch Logs Insights for contact flow errors
"""
import os
import json
import boto3
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import defaultdict

from storage_helper import store_result

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global clients - will be initialized with correct region in lambda_handler
logs_client = None
connect_client = None


def run_log_insights_query(log_group: str, query: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
    """
    Run CloudWatch Logs Insights query
    
    Args:
        log_group: CloudWatch log group name
        query: Logs Insights query string
        start_time: Query start time
        end_time: Query end time
        
    Returns:
        List of query results
    """
    try:
        # Start the query
        response = logs_client.start_query(
            logGroupName=log_group,
            startTime=int(start_time.timestamp()),
            endTime=int(end_time.timestamp()),
            queryString=query
        )
        
        query_id = response['queryId']
        logger.info(f"Started Log Insights query: {query_id}")
        
        # Poll for query completion
        max_attempts = 30
        attempt = 0
        
        while attempt < max_attempts:
            time.sleep(2)  # Wait 2 seconds between polls
            
            result = logs_client.get_query_results(queryId=query_id)
            status = result['status']
            
            if status == 'Complete':
                logger.info(f"Query completed with {len(result.get('results', []))} results")
                return result.get('results', [])
            elif status == 'Failed':
                logger.error(f"Query failed: {result.get('statistics', {})}")
                return []
            elif status == 'Cancelled':
                logger.warning("Query was cancelled")
                return []
            
            attempt += 1
        
        logger.warning(f"Query timed out after {max_attempts} attempts")
        return []
        
    except Exception as e:
        logger.error(f"Error running Log Insights query: {e}")
        return []


def get_contact_flows(instance_id: str) -> Dict[str, str]:
    """
    Get all contact flows for the instance
    
    Returns:
        Dictionary mapping flow IDs to flow names
    """
    flows = {}
    
    try:
        paginator = connect_client.get_paginator('list_contact_flows')
        
        for page in paginator.paginate(InstanceId=instance_id):
            for flow in page['ContactFlowSummaryList']:
                flows[flow['Id']] = flow['Name']
        
        logger.info(f"Retrieved {len(flows)} contact flows")
        return flows
        
    except Exception as e:
        logger.error(f"Error getting contact flows: {e}")
        return {}


def analyze_contact_flow_errors(instance_id: str, log_group: str, days_back: int) -> Dict[str, Any]:
    """
    Analyze contact flow errors from CloudWatch Logs
    
    Args:
        instance_id: Connect instance ID
        log_group: CloudWatch log group name
        days_back: Number of days to analyze
        
    Returns:
        Analysis results with error counts and details
    """
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days_back)
        
        logger.info(f"Analyzing contact flow errors from {start_time} to {end_time}")
        
        # Get contact flows
        contact_flows = get_contact_flows(instance_id)
        
        # Query for error summary
        error_summary_query = """
        fields @timestamp, @message
        | filter @message like /ERROR/
        | stats count() as error_count by ContactFlowId
        | sort error_count desc
        | limit 20
        """
        
        error_results = run_log_insights_query(logs_client, log_group, error_summary_query, start_time, end_time)
        
        # Query for detailed errors
        detailed_error_query = """
        fields @timestamp, ContactFlowId, @message
        | filter @message like /ERROR/
        | sort @timestamp desc
        | limit 100
        """
        
        detailed_errors = run_log_insights_query(logs_client, log_group, detailed_error_query, start_time, end_time)
        
        # Process results
        error_summary = []
        total_errors = 0
        
        for result in error_results:
            # Parse result fields
            flow_id = None
            error_count = 0
            
            for field in result:
                if field['field'] == 'ContactFlowId':
                    flow_id = field['value']
                elif field['field'] == 'error_count':
                    error_count = int(field['value'])
            
            if flow_id:
                flow_name = contact_flows.get(flow_id, 'Unknown Flow')
                error_summary.append({
                    'flow_id': flow_id,
                    'flow_name': flow_name,
                    'error_count': error_count
                })
                total_errors += error_count
        
        # Process detailed errors
        error_details = []
        error_types = defaultdict(int)
        
        for result in detailed_errors:
            timestamp = None
            flow_id = None
            message = None
            
            for field in result:
                if field['field'] == '@timestamp':
                    timestamp = field['value']
                elif field['field'] == 'ContactFlowId':
                    flow_id = field['value']
                elif field['field'] == '@message':
                    message = field['value']
            
            if message:
                # Categorize error type
                if 'timeout' in message.lower():
                    error_types['Timeout'] += 1
                elif 'invalid' in message.lower():
                    error_types['Invalid Input'] += 1
                elif 'not found' in message.lower():
                    error_types['Not Found'] += 1
                else:
                    error_types['Other'] += 1
                
                error_details.append({
                    'timestamp': timestamp,
                    'flow_id': flow_id,
                    'flow_name': contact_flows.get(flow_id, 'Unknown') if flow_id else 'Unknown',
                    'message': message[:200]  # Truncate long messages
                })
        
        # Generate recommendations
        recommendations = []
        if total_errors > 0:
            recommendations = [
                'Review error logs for affected contact flows',
                'Enable detailed logging for troubleshooting',
                'Check for timeout issues in external integrations',
                'Validate input parameters and error handling',
                'Monitor error trends over time'
            ]
        
        return {
            'total_errors': total_errors,
            'flows_with_errors': len(error_summary),
            'error_summary': error_summary[:10],  # Top 10 flows with errors
            'error_types': dict(error_types),
            'sample_errors': error_details[:20],  # Sample of recent errors
            'recommendations': recommendations,
            'log_group': log_group,
            'days_analyzed': days_back
        }
        
    except Exception as e:
        logger.error(f"Error analyzing contact flow errors: {e}")
        return {'error': str(e)}


def lambda_handler(event, context):
    """
    Main handler for log analysis
    
    Expected event structure:
    {
        "reviewId": "20240210-120000",
        "instanceId": "xxxxx-xxxx-xxxx",
        "logGroup": "/aws/connect/instance-name",
        "awsRegion": "us-west-2",
        "daysBack": 14,
        "ttl": 1234567890
    }
    """
    try:
        logger.info("Starting log analysis")
        
        review_id = event['reviewId']
        instance_id = event['instanceId']
        log_group = event['logGroup']
        aws_region = event['awsRegion']
        days_back = event.get('daysBack', 14)
        ttl = event['ttl']
        
        # Create clients with correct region
        global logs_client, connect_client
        logs_client = boto3.client('logs', region_name=aws_region)
        connect_client = boto3.client('connect', region_name=aws_region)
        
        # Perform analysis
        analysis_result = analyze_contact_flow_errors(instance_id, log_group, days_back)
        
        # Store results in DynamoDB
        store_result(review_id, 'logs', analysis_result, ttl)
        
        logger.info(f"Log analysis completed: {analysis_result.get('total_errors', 0)} errors found")
        
        return {
            'statusCode': 200,
            'componentType': 'logs'
        }
        
    except Exception as e:
        logger.error(f"Log analyzer error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'error': str(e)
        }
