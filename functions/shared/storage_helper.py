"""
Storage helper functions for storing and retrieving review results
Supports both S3 (default) and DynamoDB backends
"""
import os
import json
import boto3
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from decimal import Decimal

logger = logging.getLogger()

# Initialize clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')


class DecimalEncoder(json.JSONEncoder):
    """Helper class to convert DynamoDB Decimal types to JSON"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def get_storage_backend() -> str:
    """
    Get configured storage backend
    
    Returns:
        str: 's3' or 'dynamodb'
    """
    return os.environ.get('STORAGE_BACKEND', 's3').lower()


def get_s3_bucket() -> str:
    """Get S3 bucket for intermediate storage"""
    bucket = os.environ.get('S3_REPORTING_BUCKET')
    if not bucket:
        raise ValueError("S3_REPORTING_BUCKET environment variable not set")
    return bucket


def get_dynamodb_table():
    """Get DynamoDB table reference"""
    table_name = os.environ.get('RESULTS_TABLE')
    if not table_name:
        raise ValueError("RESULTS_TABLE environment variable not set")
    return dynamodb.Table(table_name)


# ============================================================================
# S3 Storage Backend (Default)
# ============================================================================

def store_result_s3(review_id: str, component_type: str, data: Dict[str, Any], ttl: int) -> bool:
    """
    Store analysis result in S3
    
    Args:
        review_id: Unique review identifier
        component_type: Type of component (quota, metrics, phone, flow, etc.)
        data: Analysis data to store
        ttl: Time-to-live timestamp (for metadata only, S3 lifecycle manages deletion)
        
    Returns:
        bool: True if successful
    """
    try:
        bucket = get_s3_bucket()
        key = f'reviews/{review_id}/{component_type}.json'
        
        # Add metadata
        result = {
            'reviewId': review_id,
            'componentType': component_type,
            'data': data,
            'ttl': ttl
        }
        
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(result, cls=DecimalEncoder),
            ContentType='application/json',
            ServerSideEncryption='AES256'
        )
        
        logger.info(f"Stored result for {component_type} in S3: s3://{bucket}/{key}")
        return True
        
    except Exception as e:
        logger.error(f"Error storing result in S3: {e}")
        return False


def get_result_s3(review_id: str, component_type: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve analysis result from S3
    
    Args:
        review_id: Unique review identifier
        component_type: Type of component
        
    Returns:
        dict: Analysis data or None if not found
    """
    try:
        bucket = get_s3_bucket()
        key = f'reviews/{review_id}/{component_type}.json'
        
        response = s3_client.get_object(Bucket=bucket, Key=key)
        result = json.loads(response['Body'].read())
        
        return result.get('data')
        
    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"Result not found in S3: {component_type} for review {review_id}")
        return None
    except Exception as e:
        logger.error(f"Error retrieving result from S3: {e}")
        return None


def get_all_results_s3(review_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all analysis results for a review from S3
    
    Args:
        review_id: Unique review identifier
        
    Returns:
        list: All analysis results
    """
    try:
        bucket = get_s3_bucket()
        prefix = f'reviews/{review_id}/'
        
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        
        results = []
        for obj in response.get('Contents', []):
            key = obj['Key']
            
            # Skip non-JSON files
            if not key.endswith('.json'):
                continue
            
            # Get the object
            obj_response = s3_client.get_object(Bucket=bucket, Key=key)
            result = json.loads(obj_response['Body'].read())
            
            results.append({
                'componentType': result['componentType'],
                'data': result.get('data', {})
            })
        
        logger.info(f"Retrieved {len(results)} results from S3 for review {review_id}")
        return results
        
    except Exception as e:
        logger.error(f"Error retrieving all results from S3: {e}")
        return []


# ============================================================================
# DynamoDB Storage Backend (Optional)
# ============================================================================

def store_result_dynamodb(review_id: str, component_type: str, data: Dict[str, Any], ttl: int) -> bool:
    """
    Store analysis result in DynamoDB
    
    Args:
        review_id: Unique review identifier
        component_type: Type of component
        data: Analysis data to store
        ttl: Time-to-live timestamp
        
    Returns:
        bool: True if successful
    """
    try:
        table = get_dynamodb_table()
        
        item = {
            'reviewId': review_id,
            'componentType': component_type,
            'data': data,
            'ttl': ttl
        }
        
        table.put_item(Item=item)
        logger.info(f"Stored result for {component_type} in DynamoDB review {review_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error storing result in DynamoDB: {e}")
        return False


def get_result_dynamodb(review_id: str, component_type: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve analysis result from DynamoDB
    
    Args:
        review_id: Unique review identifier
        component_type: Type of component
        
    Returns:
        dict: Analysis data or None if not found
    """
    try:
        table = get_dynamodb_table()
        
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
        logger.error(f"Error retrieving result from DynamoDB: {e}")
        return None


def get_all_results_dynamodb(review_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all analysis results for a review from DynamoDB
    
    Args:
        review_id: Unique review identifier
        
    Returns:
        list: All analysis results
    """
    try:
        table = get_dynamodb_table()
        
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
        
        logger.info(f"Retrieved {len(results)} results from DynamoDB for review {review_id}")
        return results
        
    except Exception as e:
        logger.error(f"Error retrieving all results from DynamoDB: {e}")
        return []


# ============================================================================
# Unified Interface (Auto-selects backend)
# ============================================================================

def store_result(review_id: str, component_type: str, data: Dict[str, Any], ttl: int) -> bool:
    """
    Store analysis result using configured backend
    
    Args:
        review_id: Unique review identifier
        component_type: Type of component
        data: Analysis data to store
        ttl: Time-to-live timestamp
        
    Returns:
        bool: True if successful
    """
    backend = get_storage_backend()
    
    if backend == 'dynamodb':
        return store_result_dynamodb(review_id, component_type, data, ttl)
    else:  # Default to S3
        return store_result_s3(review_id, component_type, data, ttl)


def get_result(review_id: str, component_type: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve analysis result using configured backend
    
    Args:
        review_id: Unique review identifier
        component_type: Type of component
        
    Returns:
        dict: Analysis data or None if not found
    """
    backend = get_storage_backend()
    
    if backend == 'dynamodb':
        return get_result_dynamodb(review_id, component_type)
    else:  # Default to S3
        return get_result_s3(review_id, component_type)


def get_all_results(review_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all analysis results for a review using configured backend
    
    Args:
        review_id: Unique review identifier
        
    Returns:
        list: All analysis results
    """
    backend = get_storage_backend()
    
    if backend == 'dynamodb':
        return get_all_results_dynamodb(review_id)
    else:  # Default to S3
        return get_all_results_s3(review_id)


# ============================================================================
# Status Management (Optional - for tracking review progress)
# ============================================================================

def update_review_status_s3(review_id: str, status: str, message: str = "") -> bool:
    """
    Update the status of a review in S3
    
    Args:
        review_id: Unique review identifier
        status: Status (in_progress, completed, failed)
        message: Optional status message
        
    Returns:
        bool: True if successful
    """
    try:
        bucket = get_s3_bucket()
        key = f'reviews/{review_id}/STATUS.json'
        
        status_data = {
            'reviewId': review_id,
            'status': status,
            'message': message,
            'updatedAt': datetime.now().isoformat()
        }
        
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(status_data),
            ContentType='application/json',
            ServerSideEncryption='AES256'
        )
        
        logger.info(f"Updated review {review_id} status to {status}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating review status in S3: {e}")
        return False


def update_review_status_dynamodb(review_id: str, status: str, message: str = "") -> bool:
    """
    Update the status of a review in DynamoDB
    
    Args:
        review_id: Unique review identifier
        status: Status (in_progress, completed, failed)
        message: Optional status message
        
    Returns:
        bool: True if successful
    """
    try:
        table = get_dynamodb_table()
        
        from datetime import datetime
        
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
                ':updated': datetime.now().isoformat()
            }
        )
        
        logger.info(f"Updated review {review_id} status to {status}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating review status in DynamoDB: {e}")
        return False


def update_review_status(review_id: str, status: str, message: str = "") -> bool:
    """
    Update the status of a review using configured backend
    
    Args:
        review_id: Unique review identifier
        status: Status (in_progress, completed, failed)
        message: Optional status message
        
    Returns:
        bool: True if successful
    """
    backend = get_storage_backend()
    
    if backend == 'dynamodb':
        return update_review_status_dynamodb(review_id, status, message)
    else:  # Default to S3
        return update_review_status_s3(review_id, status, message)
