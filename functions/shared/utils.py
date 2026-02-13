"""
Shared utilities for Amazon Connect Operational Review
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger()
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logger.setLevel(getattr(logging, log_level))


def parse_connect_instance_arn(instance_arn: str) -> Dict[str, str]:
    """
    Parse instance_id and aws_region from Amazon Connect instance ARN
    
    ARN format: arn:aws:connect:region:account-id:instance/instance-id
    
    Args:
        instance_arn: Amazon Connect instance ARN
        
    Returns:
        dict: Contains instance_id, aws_region, account_id, and other components
    """
    if not instance_arn or not isinstance(instance_arn, str):
        raise ValueError("Invalid ARN provided")
    
    arn_parts = instance_arn.split(':')
    
    if len(arn_parts) < 6 or arn_parts[0] != 'arn' or arn_parts[2] != 'connect':
        raise ValueError(f"Invalid Connect instance ARN format: {instance_arn}")
    
    aws_region = arn_parts[3]
    account_id = arn_parts[4]
    resource_part = arn_parts[5]
    
    if not resource_part.startswith('instance/'):
        raise ValueError(f"Invalid resource type in ARN: {resource_part}")
    
    instance_id = resource_part.split('/', 1)[1]
    
    return {
        'instance_id': instance_id,
        'aws_region': aws_region,
        'account_id': account_id,
        'service': arn_parts[2],
        'partition': arn_parts[1],
        'resource_type': 'instance',
        'full_arn': instance_arn
    }


def get_time_range(days_back: int = 14) -> tuple:
    """
    Get start and end time for analysis
    
    Args:
        days_back: Number of days to look back
        
    Returns:
        tuple: (start_time, end_time) as datetime objects
    """
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days_back)
    return start_time, end_time


def get_color_by_percentage(percentage: float) -> str:
    """
    Return color code based on percentage value for HTML reports
    
    Args:
        percentage: Usage percentage
        
    Returns:
        str: HTML color code
    """
    if percentage >= 98:
        return "#FF0000"  # Red - Critical
    elif percentage >= 80:
        return "#FFA500"  # Orange - Warning
    else:
        return "#00FF00"  # Green - Normal


def generate_review_id() -> str:
    """
    Generate a unique review ID based on timestamp
    
    Returns:
        str: Review ID in format YYYYMMDD-HHMMSS
    """
    return datetime.utcnow().strftime("%Y%m%d-%H%M%S")


def get_ttl(days: int = 90) -> int:
    """
    Calculate TTL timestamp for DynamoDB
    
    Args:
        days: Number of days until expiration
        
    Returns:
        int: Unix timestamp
    """
    expiration = datetime.utcnow() + timedelta(days=days)
    return int(expiration.timestamp())
