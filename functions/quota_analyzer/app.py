"""
Quota Analyzer Lambda Function
Analyzes Amazon Connect service quotas and current usage
"""
import os
import json
import boto3
import logging
from typing import Dict, Any, List
from collections import defaultdict
from decimal import Decimal

from utils import get_color_by_percentage
from storage_helper import store_result

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global clients - will be initialized with correct region in lambda_handler
connect_client = None
service_quotas_client = None


def get_connect_service_quotas() -> List[Dict[str, Any]]:
    """Retrieve all Amazon Connect service quotas"""
    try:
        quotas = []
        paginator = service_quotas_client.get_paginator('list_service_quotas')
        
        for page in paginator.paginate(ServiceCode='connect'):
            quotas.extend(page['Quotas'])
        
        logger.info(f"Retrieved {len(quotas)} service quotas")
        return quotas
        
    except Exception as e:
        logger.error(f"Error retrieving service quotas: {e}")
        return []


def get_current_usage(instance_id: str, metric_name: str) -> int:
    """
    Get current utilization for a specific Amazon Connect resource
    
    Args:
        instance_id: Connect instance ID
        metric_name: Type of resource to count
        
    Returns:
        int: Current count of resources
    """
    try:
        if metric_name == "ContactFlows":
            response = connect_client.list_contact_flows(InstanceId=instance_id)
            return len(response['ContactFlowSummaryList'])
            
        elif metric_name == "Users":
            response = connect_client.list_users(InstanceId=instance_id)
            return len(response['UserSummaryList'])
            
        elif metric_name == "Queues":
            response = connect_client.list_queues(InstanceId=instance_id)
            return len(response['QueueSummaryList'])
            
        elif metric_name == "RoutingProfiles":
            response = connect_client.list_routing_profiles(InstanceId=instance_id)
            return len(response['RoutingProfileSummaryList'])
            
        elif metric_name == "SecurityProfiles":
            response = connect_client.list_security_profiles(InstanceId=instance_id)
            return len(response['SecurityProfileSummaryList'])
            
        elif metric_name == "HoursOfOperation":
            response = connect_client.list_hours_of_operations(InstanceId=instance_id)
            return len(response['HoursOfOperationSummaryList'])
            
        elif metric_name == "Prompts":
            response = connect_client.list_prompts(InstanceId=instance_id)
            return len(response['PromptSummaryList'])
            
        elif metric_name == "LexBotsV1":
            response = connect_client.list_bots(InstanceId=instance_id, LexVersion='V1')
            return len(response['LexBots'])
            
        elif metric_name == "LexBotsV2":
            response = connect_client.list_bots(InstanceId=instance_id, LexVersion='V2')
            return len(response['LexBots'])
            
        elif metric_name == "PhoneNumbers":
            response = connect_client.list_phone_numbers(InstanceId=instance_id)
            return len(response['PhoneNumberSummaryList'])
            
        elif metric_name == "AgentStatuses":
            response = connect_client.list_agent_statuses(InstanceId=instance_id)
            return len(response['AgentStatusSummaryList'])
            
        elif metric_name == "ContactFlowModules":
            response = connect_client.list_contact_flow_modules(InstanceId=instance_id)
            return len(response['ContactFlowModulesSummaryList'])
            
        elif metric_name == "QuickConnects":
            response = connect_client.list_quick_connects(InstanceId=instance_id)
            return len(response['QuickConnectSummaryList'])
            
        else:
            logger.warning(f"Unknown metric name: {metric_name}")
            return 0
            
    except Exception as e:
        logger.error(f"Error getting usage for {metric_name}: {e}")
        return 0


def analyze_quotas(instance_id: str) -> Dict[str, Any]:
    """
    Analyze all quotas and current usage
    
    Args:
        instance_id: Connect instance ID
        
    Returns:
        dict: Analysis results with quotas, usage, and percentages
    """
    # Mapping of quota names to metric names
    quota_mapping = {
        "Contact flows per instance": "ContactFlows",
        "Routing profiles per instance": "RoutingProfiles",
        "Queues per instance": "Queues",
        "Security profiles per instance": "SecurityProfiles",
        "Users per instance": "Users",
        "Amazon Lex bots per instance": "LexBotsV1",
        "Amazon Lex V2 bot aliases per instance": "LexBotsV2",
        "Phone numbers per instance": "PhoneNumbers",
        "Quick connects per instance": "QuickConnects",
        "Hours of operation per instance": "HoursOfOperation"
    }
    
    quotas = get_connect_service_quotas()
    analysis = {
        'quotas': [],
        'summary': {
            'total_analyzed': 0,
            'critical': 0,  # >= 98%
            'warning': 0,   # >= 80%
            'normal': 0     # < 80%
        }
    }
    
    for quota in quotas:
        quota_name = quota['QuotaName']
        
        if quota_name in quota_mapping:
            metric_name = quota_mapping[quota_name]
            limit = int(quota['Value'])
            current = get_current_usage(instance_id, metric_name)
            percentage = (current / limit * 100) if limit > 0 else 0
            
            quota_info = {
                'name': quota_name,
                'limit': limit,
                'current': current,
                'percentage': round(percentage, 2),
                'color': get_color_by_percentage(percentage),
                'status': 'critical' if percentage >= 98 else 'warning' if percentage >= 80 else 'normal'
            }
            
            analysis['quotas'].append(quota_info)
            analysis['summary']['total_analyzed'] += 1
            
            if percentage >= 98:
                analysis['summary']['critical'] += 1
            elif percentage >= 80:
                analysis['summary']['warning'] += 1
            else:
                analysis['summary']['normal'] += 1
            
            logger.info(f"{quota_name}: {current}/{limit} ({percentage:.1f}%)")
    
    return analysis


def lambda_handler(event, context):
    """
    Main handler for quota analysis
    
    Expected event structure:
    {
        "reviewId": "20240210-120000",
        "instanceId": "xxxxx-xxxx-xxxx",
        "awsRegion": "us-west-2",
        "ttl": 1234567890
    }
    """
    try:
        logger.info("Starting quota analysis")
        
        review_id = event['reviewId']
        instance_id = event['instanceId']
        aws_region = event['awsRegion']
        ttl = event['ttl']
        
        # Create clients with correct region
        global connect_client, service_quotas_client
        connect_client = boto3.client('connect', region_name=aws_region)
        service_quotas_client = boto3.client('service-quotas', region_name=aws_region)
        
        # Perform analysis
        analysis_result = analyze_quotas(instance_id)
        
        # Convert float percentages to Decimal for DynamoDB
        for quota in analysis_result['quotas']:
            quota['percentage'] = Decimal(str(quota['percentage']))
        
        # Store results in DynamoDB
        store_result(review_id, 'quota', analysis_result, ttl)
        
        logger.info(f"Quota analysis completed: {analysis_result['summary']}")
        
        return {
            'statusCode': 200,
            'componentType': 'quota',
            'summary': analysis_result['summary']
        }
        
    except Exception as e:
        logger.error(f"Quota analyzer error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'error': str(e)
        }
