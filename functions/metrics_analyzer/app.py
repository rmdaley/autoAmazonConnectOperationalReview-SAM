"""
Metrics Analyzer Lambda Function
Analyzes CloudWatch metrics for Amazon Connect
"""
import os
import json
import boto3
import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import defaultdict
from decimal import Decimal

from utils import get_time_range
from storage_helper import store_result

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global client - will be initialized with correct region in lambda_handler
cloudwatch_client = None


def analyze_concurrent_calls(instance_id: str, days_back: int) -> Dict[str, Any]:
    """Analyze concurrent calls metrics"""
    start_time, end_time = get_time_range(days_back)
    
    try:
        response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/Connect',
            MetricName='ConcurrentCalls',
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Average', 'Maximum', 'Minimum']
        )
        
        datapoints = response.get('Datapoints', [])
        if not datapoints:
            return {'error': 'No data available'}
        
        averages = [dp['Average'] for dp in datapoints]
        maximums = [dp['Maximum'] for dp in datapoints]
        
        return {
            'period_average': sum(averages) / len(averages),
            'absolute_peak': max(maximums),
            'data_points': len(datapoints)
        }
        
    except Exception as e:
        logger.error(f"Error analyzing concurrent calls: {e}")
        return {'error': str(e)}


def analyze_missed_calls(instance_id: str, days_back: int) -> Dict[str, Any]:
    """Analyze missed calls metrics"""
    start_time, end_time = get_time_range(days_back)
    
    try:
        response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/Connect',
            MetricName='MissedCalls',
            Dimensions=[
                {'Name': 'InstanceId', 'Value': instance_id},
                {'Name': 'MetricGroup', 'Value': 'VoiceCalls'}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=86400,
            Statistics=['Sum']
        )
        
        datapoints = response.get('Datapoints', [])
        if not datapoints:
            return {'total': 0, 'daily_average': 0}
        
        total = sum(int(dp['Sum']) for dp in datapoints)
        
        return {
            'total': total,
            'daily_average': total / len(datapoints),
            'days_analyzed': len(datapoints)
        }
        
    except Exception as e:
        logger.error(f"Error analyzing missed calls: {e}")
        return {'error': str(e)}


def analyze_throttled_calls(instance_id: str, days_back: int) -> Dict[str, Any]:
    """
    Analyze throttled calls metrics with severity assessment
    
    Returns comprehensive analysis including:
    - Total throttled calls
    - Severity level (Excellent/Low/Moderate/High/Critical)
    - Daily breakdown
    - Peak hours
    - Recommendations
    """
    start_time, end_time = get_time_range(days_back)
    
    try:
        response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/Connect',
            MetricName='ThrottledCalls',
            Dimensions=[
                {'Name': 'InstanceId', 'Value': instance_id},
                {'Name': 'MetricGroup', 'Value': 'VoiceCalls'}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,  # 1-hour periods
            Statistics=['Sum', 'Maximum']
        )
        
        datapoints = response.get('Datapoints', [])
        
        if not datapoints:
            logger.info("No throttled calls found - instance operating within limits")
            return {
                'total_throttled': 0,
                'severity': 'Excellent',
                'message': 'No throttled calls found. Instance is operating well within capacity limits.',
                'daily_breakdown': {},
                'peak_hours': [],
                'recommendations': []
            }
        
        # Sort by timestamp
        sorted_data = sorted(datapoints, key=lambda x: x['Timestamp'])
        
        # Calculate statistics
        total_throttled = sum(int(dp['Sum']) for dp in sorted_data)
        hourly_counts = [int(dp['Sum']) for dp in sorted_data]
        max_hourly = max(hourly_counts)
        avg_hourly = statistics.mean(hourly_counts) if hourly_counts else 0
        hours_with_throttling = len([c for c in hourly_counts if c > 0])
        
        # Determine severity
        if total_throttled == 0:
            severity = 'Excellent'
        elif total_throttled < 10:
            severity = 'Low'
        elif total_throttled < 100:
            severity = 'Moderate'
        elif total_throttled < 1000:
            severity = 'High'
        else:
            severity = 'Critical'
        
        # Daily breakdown
        daily_stats = defaultdict(int)
        for dp in sorted_data:
            date = dp['Timestamp'].date().isoformat()
            daily_stats[date] += int(dp['Sum'])
        
        # Peak hours (top 5)
        peak_hours = []
        sorted_peaks = sorted(sorted_data, key=lambda x: x['Sum'], reverse=True)[:5]
        for dp in sorted_peaks:
            if dp['Sum'] > 0:
                peak_hours.append({
                    'timestamp': dp['Timestamp'].isoformat(),
                    'count': int(dp['Sum'])
                })
        
        # Generate recommendations based on severity
        recommendations = []
        if total_throttled > 0:
            recommendations.extend([
                'Review current service quotas for your Connect instance',
                'Consider requesting quota increases via AWS Support',
                'Analyze call patterns during peak throttling periods',
                'Implement call queuing or retry mechanisms',
                'Set up CloudWatch alarms for ThrottledCalls metric',
                'Monitor ConcurrentCalls to predict throttling',
                'Track CallsPerInterval for capacity planning'
            ])
            
            if severity in ['High', 'Critical']:
                recommendations.insert(0, 'IMMEDIATE ACTION REQUIRED - Severe throttling detected')
        
        return {
            'total_throttled': total_throttled,
            'severity': severity,
            'avg_hourly': Decimal(str(round(avg_hourly, 2))),
            'max_hourly': max_hourly,
            'hours_with_throttling': hours_with_throttling,
            'total_hours_analyzed': len(hourly_counts),
            'daily_breakdown': dict(daily_stats),
            'peak_hours': peak_hours,
            'recommendations': recommendations
        }
        
    except Exception as e:
        logger.error(f"Error analyzing throttled calls: {e}")
        return {'error': str(e)}


def analyze_queue_size(instance_id: str, days_back: int) -> Dict[str, Any]:
    """Analyze queue size metrics"""
    start_time, end_time = get_time_range(days_back)
    
    try:
        response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/Connect',
            MetricName='QueueSize',
            Dimensions=[
                {'Name': 'InstanceId', 'Value': instance_id},
                {'Name': 'MetricGroup', 'Value': 'Queue'}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Average', 'Maximum']
        )
        
        datapoints = response.get('Datapoints', [])
        if not datapoints:
            return {'message': 'No queue size data available'}
        
        averages = [dp['Average'] for dp in datapoints]
        maximums = [dp['Maximum'] for dp in datapoints]
        
        return {
            'avg_queue_size': Decimal(str(round(sum(averages) / len(averages), 2))),
            'max_queue_size': int(max(maximums)),
            'data_points': len(datapoints)
        }
        
    except Exception as e:
        logger.error(f"Error analyzing queue size: {e}")
        return {'error': str(e)}


def analyze_calls_per_interval(instance_id: str, days_back: int) -> Dict[str, Any]:
    """Analyze calls per interval metrics"""
    start_time, end_time = get_time_range(days_back)
    
    try:
        response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/Connect',
            MetricName='CallsPerInterval',
            Dimensions=[
                {'Name': 'InstanceId', 'Value': instance_id},
                {'Name': 'MetricGroup', 'Value': 'VoiceCalls'}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Sum', 'Average', 'Maximum']
        )
        
        datapoints = response.get('Datapoints', [])
        if not datapoints:
            return {'message': 'No calls per interval data available'}
        
        total_calls = sum(dp['Sum'] for dp in datapoints)
        averages = [dp['Average'] for dp in datapoints]
        maximums = [dp['Maximum'] for dp in datapoints]
        
        return {
            'total_calls': int(total_calls),
            'avg_per_hour': Decimal(str(round(sum(averages) / len(averages), 2))),
            'peak_per_hour': int(max(maximums)),
            'data_points': len(datapoints)
        }
        
    except Exception as e:
        logger.error(f"Error analyzing calls per interval: {e}")
        return {'error': str(e)}


def lambda_handler(event, context):
    """Main handler for metrics analysis"""
    try:
        logger.info("Starting metrics analysis")
        
        review_id = event['reviewId']
        instance_id = event['instanceId']
        aws_region = event['awsRegion']
        days_back = event.get('daysBack', 14)
        ttl = event['ttl']
        
        # Create client with correct region
        global cloudwatch_client
        cloudwatch_client = boto3.client('cloudwatch', region_name=aws_region)
        
        # Analyze different metrics
        analysis_result = {
            'concurrent_calls': analyze_concurrent_calls(instance_id, days_back),
            'missed_calls': analyze_missed_calls(instance_id, days_back),
            'throttled_calls': analyze_throttled_calls(instance_id, days_back),
            'queue_size': analyze_queue_size(instance_id, days_back),
            'calls_per_interval': analyze_calls_per_interval(instance_id, days_back),
            'days_analyzed': days_back
        }
        
        # Store results
        store_result(review_id, 'metrics', analysis_result, ttl)
        
        logger.info("Metrics analysis completed")
        
        return {
            'statusCode': 200,
            'componentType': 'metrics'
        }
        
    except Exception as e:
        logger.error(f"Metrics analyzer error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'error': str(e)
        }
