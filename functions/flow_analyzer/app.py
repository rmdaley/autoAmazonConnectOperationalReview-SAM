"""
Flow Analyzer Lambda Function
Analyzes contact flows and identifies issues
"""
import os
import json
import boto3
import logging
from typing import Dict, Any, List
from decimal import Decimal

from storage_helper import store_result

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global client - will be initialized with correct region in lambda_handler
connect_client = None


def check_logging_enabled(flow_content: Dict[str, Any]) -> bool:
    """Check if logging is enabled in the flow"""
    actions = flow_content.get('Actions', [])
    
    for action in actions:
        if action.get('Type') == 'UpdateFlowLoggingBehavior':
            parameters = action.get('Parameters', {})
            if parameters.get('FlowLoggingBehavior') == 'Enabled':
                return True
    
    return False


def analyze_contact_flows(instance_id: str, aws_region: str) -> Dict[str, Any]:
    """Analyze all contact flows for the instance"""
    try:
        flows_without_logging = []
        total_flows = 0
        flows_by_type = {}
        
        paginator = connect_client.get_paginator('list_contact_flows')
        
        for page in paginator.paginate(InstanceId=instance_id):
            for flow_summary in page['ContactFlowSummaryList']:
                total_flows += 1
                flow_type = flow_summary['ContactFlowType']
                flows_by_type[flow_type] = flows_by_type.get(flow_type, 0) + 1
                
                try:
                    # Get detailed flow information
                    flow_details = connect_client.describe_contact_flow(
                        InstanceId=instance_id,
                        ContactFlowId=flow_summary['Id']
                    )
                    
                    flow_content = json.loads(flow_details['ContactFlow']['Content'])
                    
                    if not check_logging_enabled(flow_content):
                        flows_without_logging.append({
                            'id': flow_summary['Id'],
                            'arn': flow_summary['Arn'],
                            'name': flow_summary['Name'],
                            'type': flow_type,
                            'state': flow_summary.get('ContactFlowState', 'UNKNOWN'),
                            'status': flow_summary.get('ContactFlowStatus', 'UNKNOWN')
                        })
                        
                except Exception as e:
                    logger.error(f"Error analyzing flow {flow_summary['Name']}: {e}")
        
        return {
            'total_flows': total_flows,
            'flows_by_type': flows_by_type,
            'flows_without_logging': flows_without_logging,
            'flows_without_logging_count': len(flows_without_logging),
            'logging_compliance_percentage': Decimal(str(((total_flows - len(flows_without_logging)) / total_flows * 100) if total_flows > 0 else 0)),
            'instance_id': instance_id,
            'aws_region': aws_region
        }
        
    except Exception as e:
        logger.error(f"Error analyzing contact flows: {e}")
        return {'error': str(e)}


def lambda_handler(event, context):
    """Main handler for flow analysis"""
    try:
        logger.info("Starting flow analysis")
        
        review_id = event['reviewId']
        instance_id = event['instanceId']
        aws_region = event['awsRegion']
        ttl = event['ttl']
        
        # Create client with correct region
        global connect_client
        connect_client = boto3.client('connect', region_name=aws_region)
        
        # Perform analysis
        analysis_result = analyze_contact_flows(instance_id, aws_region)
        
        # Store results
        store_result(review_id, 'flow', analysis_result, ttl)
        
        logger.info(f"Flow analysis completed: {analysis_result.get('total_flows', 0)} flows analyzed")
        
        return {
            'statusCode': 200,
            'componentType': 'flow'
        }
        
    except Exception as e:
        logger.error(f"Flow analyzer error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'error': str(e)
        }
