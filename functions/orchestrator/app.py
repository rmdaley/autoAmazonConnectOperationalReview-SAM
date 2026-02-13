"""
Orchestrator Lambda Function
Coordinates the execution of all analyzer functions and report generation
"""
import os
import json
import boto3
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

from utils import generate_review_id, get_ttl, parse_connect_instance_arn
from storage_helper import store_result, update_review_status

logger = logging.getLogger()
logger.setLevel(logging.INFO)

lambda_client = boto3.client('lambda')


def invoke_analyzer(function_arn: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Invoke an analyzer Lambda function
    
    Args:
        function_arn: ARN of the Lambda function to invoke
        payload: Payload to send to the function
        
    Returns:
        dict: Response from the function
    """
    try:
        logger.info(f"Invoking analyzer: {function_arn}")
        
        response = lambda_client.invoke(
            FunctionName=function_arn,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read())
        
        if response['StatusCode'] == 200:
            logger.info(f"Successfully invoked {function_arn}")
            return result
        else:
            logger.error(f"Error invoking {function_arn}: {result}")
            return {'error': result}
            
    except Exception as e:
        logger.error(f"Exception invoking {function_arn}: {e}")
        return {'error': str(e)}


def lambda_handler(event, context):
    """
    Main orchestrator handler
    
    Coordinates parallel execution of analyzer functions and report generation
    """
    try:
        logger.info("Starting Amazon Connect Operational Review")
        
        # Generate unique review ID
        review_id = generate_review_id()
        logger.info(f"Review ID: {review_id}")
        
        # Get environment variables
        instance_arn = os.environ.get('CONNECT_INSTANCE_ARN')
        log_group = os.environ.get('CONNECT_CW_LOG_GROUP')
        
        # Parse instance details
        instance_info = parse_connect_instance_arn(instance_arn)
        
        # Update status to in_progress
        update_review_status(review_id, 'in_progress', 'Starting analysis')
        
        # Prepare payload for analyzer functions
        base_payload = {
            'reviewId': review_id,
            'instanceArn': instance_arn,
            'instanceId': instance_info['instance_id'],
            'awsRegion': instance_info['aws_region'],
            'accountId': instance_info['account_id'],
            'logGroup': log_group,
            'daysBack': event.get('daysBack', 14),
            'ttl': get_ttl()
        }
        
        # Define analyzer functions to invoke
        analyzers = [
            {
                'name': 'quota',
                'arn': os.environ.get('QUOTA_ANALYZER_FUNCTION')
            },
            {
                'name': 'metrics',
                'arn': os.environ.get('METRICS_ANALYZER_FUNCTION')
            },
            {
                'name': 'phone',
                'arn': os.environ.get('PHONE_ANALYZER_FUNCTION')
            },
            {
                'name': 'flow',
                'arn': os.environ.get('FLOW_ANALYZER_FUNCTION')
            },
            {
                'name': 'cloudtrail',
                'arn': os.environ.get('CLOUDTRAIL_ANALYZER_FUNCTION')
            },
            {
                'name': 'logs',
                'arn': os.environ.get('LOG_ANALYZER_FUNCTION')
            }
        ]
        
        # Execute analyzers in parallel
        results = {}
        errors = []
        
        logger.info(f"Invoking {len(analyzers)} analyzer functions in parallel")
        
        with ThreadPoolExecutor(max_workers=len(analyzers)) as executor:
            # Submit all analyzer invocations
            future_to_analyzer = {
                executor.submit(invoke_analyzer, analyzer['arn'], base_payload): analyzer['name']
                for analyzer in analyzers
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_analyzer):
                analyzer_name = future_to_analyzer[future]
                try:
                    result = future.result()
                    if 'error' in result:
                        errors.append(f"{analyzer_name}: {result['error']}")
                        logger.error(f"Analyzer {analyzer_name} failed: {result['error']}")
                    else:
                        results[analyzer_name] = result
                        logger.info(f"Analyzer {analyzer_name} completed successfully")
                except Exception as e:
                    errors.append(f"{analyzer_name}: {str(e)}")
                    logger.error(f"Exception in analyzer {analyzer_name}: {e}")
        
        # Check if we have enough results to generate a report
        if len(results) == 0:
            error_msg = f"All analyzers failed: {'; '.join(errors)}"
            logger.error(error_msg)
            update_review_status(review_id, 'failed', error_msg)
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'reviewId': review_id,
                    'status': 'failed',
                    'errors': errors
                })
            }
        
        # Log any partial failures
        if errors:
            logger.warning(f"Some analyzers failed: {'; '.join(errors)}")
        
        # Invoke report generator
        logger.info("Invoking report generator")
        report_payload = {
            'reviewId': review_id,
            'instanceInfo': instance_info,
            'daysBack': base_payload['daysBack']
        }
        
        report_result = invoke_analyzer(
            os.environ.get('REPORT_GENERATOR_FUNCTION'),
            report_payload
        )
        
        if 'error' in report_result:
            error_msg = f"Report generation failed: {report_result['error']}"
            logger.error(error_msg)
            update_review_status(review_id, 'failed', error_msg)
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'reviewId': review_id,
                    'status': 'failed',
                    'error': error_msg
                })
            }
        
        # Update status to completed
        update_review_status(review_id, 'completed', 'Review completed successfully')
        
        logger.info(f"Review {review_id} completed successfully")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'reviewId': review_id,
                'status': 'completed',
                'reportUrl': report_result.get('reportUrl'),
                'analyzersCompleted': len(results),
                'analyzersFailed': len(errors),
                'errors': errors if errors else None
            })
        }
        
    except Exception as e:
        logger.error(f"Orchestrator error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Orchestrator failed',
                'message': str(e)
            })
        }
