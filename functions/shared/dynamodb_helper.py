"""
DynamoDB helper functions for storing and retrieving review results
"""
import os
import json
import boto3
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal

logger = logging.getLogger()
dynamodb = boto3.resource('dynamodb')


class DecimalEncoder(json.JSONEncoder):
    """Helper class to convert DynamoDB Decimal types to JSON"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def get_table():
    """Get DynamoDB table reference"""
    table_name = os.environ.get('RESULTS_TABLE')
    if not table_name:
        raise ValueError("RESULTS_TABLE environment variable not set")
    return dynamodb.Table(table_name)


def store_result(review_id: str, component_type: str, data: Dict[str, Any], ttl: int) -> bool:
    """
    Store analysis result in DynamoDB
    
    Args:
        review_id: Unique review identifier
        component_type: Type of component (quota, metrics, phone, flow)
        data: Analysis data to store
        ttl: Time-to-live timestamp
        
    Returns:
        bool: True if successful
    """
    try:
        table = get_table()
        
        item = {
            'reviewId': review_id,
            'componentType': component_type,
            'data': data,
            'ttl': ttl,
            'timestamp': int(boto3.client('sts').get_caller_identity()['Account'])
        }
        
        table.put_item(Item=item)
        logger.info(f"Stored result for {component_type} in review {review_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error storing result: {e}")
        return False


def get_result(review_id: str, component_type: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve analysis result from DynamoDB
    
    Args:
        review_id: Unique review identifier
        component_type: Type of component
        
    Returns:
        dict: Analysis data or None if not found
    """
    try:
        table = get_table()
        
        response = table.get_item(
            Key={
                'reviewId': review_id,
                'componentType': component_type
            }
        )
        
        if 'Item' in response:
            return response['Item'].get('data')
        return None
        
    except Exception as e:
        logger.error(f"Error retrieving result: {e}")
        return None


def get_all_results(review_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all analysis results for a review
    
    Args:
        review_id: Unique review identifier
        
    Returns:
        list: All analysis results
    """
    try:
        table = get_table()
        
        response = table.query(
            KeyConditionExpression='reviewId = :rid',
            ExpressionAttributeValues={
                ':rid': review_id
            }
        )
        
        results = []
        for item in response.get('Items', []):
            results.append({
                'componentType': item['componentType'],
                'data': item.get('data', {})
            })
        
        logger.info(f"Retrieved {len(results)} results for review {review_id}")
        return results
        
    except Exception as e:
        logger.error(f"Error retrieving all results: {e}")
        return []


def update_review_status(review_id: str, status: str, message: str = "") -> bool:
    """
    Update the status of a review
    
    Args:
        review_id: Unique review identifier
        status: Status (in_progress, completed, failed)
        message: Optional status message
        
    Returns:
        bool: True if successful
    """
    try:
        table = get_table()
        
        table.update_item(
            Key={
                'reviewId': review_id,
                'componentType': 'STATUS'
            },
            UpdateExpression='SET #status = :status, #message = :message, #updated = :updated',
            ExpressionAttributeNames={
                '#status': 'status',
                '#message': 'message',
                '#updated': 'updatedAt'
            },
            ExpressionAttributeValues={
                ':status': status,
                ':message': message,
                ':updated': int(boto3.client('sts').get_caller_identity()['Account'])
            }
        )
        
        logger.info(f"Updated review {review_id} status to {status}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating review status: {e}")
        return False
