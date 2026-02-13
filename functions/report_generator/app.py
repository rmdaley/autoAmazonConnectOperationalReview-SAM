"""
Report Generator Lambda Function
Consolidates analysis results and generates HTML report
"""
import os
import json
import boto3
from botocore.exceptions import ClientError
import logging
from datetime import datetime
from html import escape
from typing import Dict, Any, List

from storage_helper import get_all_results
from utils import get_color_by_percentage

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')
# Global client - will be initialized with correct region in lambda_handler
connect_client = None


def normalize_instance_url(url: str) -> str:
    """
    Normalize instance access URL by ensuring it has https:// protocol.
    
    Args:
        url: Instance access URL (may or may not have protocol prefix)
        
    Returns:
        Normalized URL with https:// protocol and no duplicate protocols
    """
    if not url:
        return ""
    
    # Strip any existing protocol prefix
    clean_url = url.replace('https://', '').replace('http://', '')
    
    # Return with https:// prefix
    return f"https://{clean_url}"


def generate_html_header(instance_info: Dict[str, Any]) -> str:
    """Generate HTML header section"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Amazon Connect Instance - Operations Review</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 30px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #232F3E; border-bottom: 3px solid #FF9900; padding-bottom: 10px; }}
            h2 {{ color: #232F3E; margin-top: 30px; border-bottom: 2px solid #FF9900; padding-bottom: 5px; }}
            h3 {{ color: #545b64; margin-top: 20px; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #232F3E; color: white; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .metric-card {{ background-color: #f9f9f9; padding: 15px; margin: 10px 0; border-left: 4px solid #FF9900; }}
            .status-critical {{ background-color: #FF0000; color: white; padding: 5px 10px; border-radius: 3px; }}
            .status-warning {{ background-color: #FFA500; color: white; padding: 5px 10px; border-radius: 3px; }}
            .status-normal {{ background-color: #00FF00; color: black; padding: 5px 10px; border-radius: 3px; }}
            .recommendation {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 15px 0; }}
            .timestamp {{ color: #666; font-style: italic; }}
            .console-link {{ color: #0073bb; text-decoration: none; font-weight: bold; }}
            .console-link:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Amazon Connect Instance - Operations Review</h1>
            <p class="timestamp">Generated on: {escape(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))}</p>
            
            <div class="metric-card">
                <h3>Instance Information</h3>
                <table style="width: 60%;">
                    <tr><th>Instance ID</th><td>{escape(instance_info['instance_id'])}</td></tr>
                    <tr><th>AWS Region</th><td>{escape(instance_info['aws_region'])}</td></tr>
                    <tr><th>Account ID</th><td>{escape(instance_info['account_id'])}</td></tr>
                </table>
            </div>
    """


def get_instance_details(instance_id: str) -> Dict[str, Any]:
    """Get detailed Connect instance information with enhanced error handling"""
    # Validate instance_id before API call
    is_valid, error_message = validate_instance_id(instance_id)
    if not is_valid:
        logger.error(f"Invalid instance_id: {error_message} (value: {instance_id})")
        return {}
    
    try:
        response = connect_client.describe_instance(InstanceId=instance_id)
        instance_details = response.get('Instance', {})
        logger.info(f"Successfully retrieved instance details for instance_id={instance_id}")
        return instance_details
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        if error_code == 'AccessDeniedException':
            logger.error(
                f"Error getting instance details for instance_id={instance_id}: "
                f"AccessDeniedException: {error_message}. "
                f"The Lambda function lacks the required connect:DescribeInstance permission."
            )
        elif error_code == 'ResourceNotFoundException':
            logger.error(
                f"Error getting instance details for instance_id={instance_id}: "
                f"ResourceNotFoundException: {error_message}. "
                f"The specified instance does not exist."
            )
        elif error_code == 'InvalidParameterException':
            logger.error(
                f"Error getting instance details for instance_id={instance_id}: "
                f"InvalidParameterException: {error_message}. "
                f"The instance_id parameter is malformed."
            )
        else:
            logger.error(
                f"Error getting instance details for instance_id={instance_id}: "
                f"{error_code}: {error_message}"
            )
        return {}
    except Exception as e:
        logger.error(
            f"Error getting instance details for instance_id={instance_id}: "
            f"{type(e).__name__}: {str(e)}"
        )
        return {}
def validate_instance_id(instance_id: str) -> tuple[bool, str]:
    """
    Validate instance ID format.

    Args:
        instance_id: The instance ID to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if valid, False otherwise
        - error_message: Empty string if valid, error description if invalid
    """
    import re

    # Check if instance_id is None
    if instance_id is None:
        return (False, "Instance ID is None")

    # Check if instance_id is empty string
    if instance_id == "":
        return (False, "Instance ID is empty")

    # Check if instance_id contains only whitespace
    if instance_id.strip() == "":
        return (False, "Instance ID contains only whitespace")

    # Validate UUID format (8-4-4-4-12 hex digits)
    # UUID pattern: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    uuid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'

    if not re.match(uuid_pattern, instance_id.strip()):
        return (False, f"Instance ID '{instance_id}' does not match UUID format (8-4-4-4-12 hex digits)")

    # All validations passed
    return (True, "")
def extract_instance_id_from_arn(arn: str) -> str:
    """
    Extract instance ID from Amazon Connect ARN.

    Args:
        arn: Amazon Connect instance ARN in format:
             arn:aws:connect:<region>:<account>:instance/<instance-id>

    Returns:
        The instance ID portion, or empty string if ARN is malformed
    """
    if not arn:
        logger.error("ARN is None or empty")
        return ""

    # ARN format: arn:aws:connect:<region>:<account>:instance/<instance-id>
    # Split by ':' to get parts
    parts = arn.split(':')

    # Validate basic ARN structure (should have at least 6 parts)
    if len(parts) < 6:
        logger.error(f"Malformed ARN: '{arn}' - insufficient parts")
        return ""

    # Check if it's a Connect ARN
    if parts[2] != 'connect':
        logger.error(f"Not a Connect ARN: '{arn}' - service is '{parts[2]}'")
        return ""

    # The resource part is the last element (instance/<instance-id>)
    resource_part = parts[5]

    # Split by '/' to extract instance ID
    if '/' not in resource_part:
        logger.error(f"Malformed ARN resource: '{arn}' - no '/' in resource part")
        return ""

    resource_parts = resource_part.split('/', 1)

    # Verify it's an instance resource
    if resource_parts[0] != 'instance':
        logger.error(f"Not an instance ARN: '{arn}' - resource type is '{resource_parts[0]}'")
        return ""

    # Extract and return the instance ID
    if len(resource_parts) < 2:
        logger.error(f"Malformed ARN: '{arn}' - no instance ID after 'instance/'")
        return ""

    instance_id = resource_parts[1]
    logger.info(f"Extracted instance ID '{instance_id}' from ARN")
    return instance_id





def generate_instance_details_section(instance_info: Dict[str, Any]) -> str:
    """Generate instance details and configuration section"""
    # Validate instance_info contains 'instance_id' key
    if not instance_info or 'instance_id' not in instance_info:
        logger.error("instance_info is missing or does not contain 'instance_id' key")
        return """
        <div class="section">
            <h2>Instance Details & Configuration</h2>
            <p>Unable to retrieve instance details. Invalid instance information provided.</p>
        </div>
        """
    
    instance_id = instance_info['instance_id']
    aws_region = instance_info.get('aws_region', 'us-east-1')
    
    # Validate instance_id is not None or empty
    if not instance_id:
        logger.error("instance_id is None or empty")
        return """
        <div class="section">
            <h2>Instance Details & Configuration</h2>
            <p>Unable to retrieve instance details. Instance ID is missing.</p>
        </div>
        """
    
    instance_details = get_instance_details(instance_id)
    
    if not instance_details:
        return """
        <div class="section">
            <h2>Instance Details & Configuration</h2>
            <p>Unable to retrieve instance details. Check CloudWatch logs for details.</p>
        </div>
        """
    
    # Build console link to the Connect instance
    connect_console_url = f"https://{aws_region}.console.aws.amazon.com/connect/v2/app/instances/{instance_id}/overview"
    
    html = f"""
    <div class="section">
        <h2>Instance Details & Configuration</h2>
        <p><a href="{connect_console_url}" target="_blank" class="console-link">» Open in Connect Console</a></p>
        <table style="width: 70%;">
    """
    
    # Basic instance information
    if 'InstanceAlias' in instance_details:
        html += f"<tr><th>Instance Alias</th><td>{escape(instance_details['InstanceAlias'])}</td></tr>"
    if 'Arn' in instance_details:
        html += f"<tr><th>Instance ARN</th><td>{escape(instance_details['Arn'])}</td></tr>"
    if 'IdentityManagementType' in instance_details:
        html += f"<tr><th>Identity Management Type</th><td>{escape(instance_details['IdentityManagementType'])}</td></tr>"
    if 'InstanceStatus' in instance_details:
        html += f"<tr><th>Instance Status</th><td>{escape(instance_details['InstanceStatus'])}</td></tr>"
    if 'ServiceRole' in instance_details:
        html += f"<tr><th>Service Role</th><td>{escape(instance_details['ServiceRole'])}</td></tr>"
    if 'CreatedTime' in instance_details:
        created_time = instance_details['CreatedTime']
        # Handle datetime objects
        if hasattr(created_time, 'strftime'):
            created = created_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        # Handle string timestamps - try to parse and format
        elif isinstance(created_time, str):
            try:
                from dateutil import parser
                parsed_dt = parser.parse(created_time)
                created = parsed_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            except Exception:
                # If parsing fails, use the string as-is
                created = created_time
        else:
            # Fallback for other types
            created = str(created_time)
        html += f"<tr><th>Created Time</th><td>{escape(created)}</td></tr>"
    
    # Call configuration
    if 'InboundCallsEnabled' in instance_details:
        html += f"<tr><th>Inbound Calls Enabled</th><td>{escape(str(instance_details['InboundCallsEnabled']))}</td></tr>"
    if 'OutboundCallsEnabled' in instance_details:
        html += f"<tr><th>Outbound Calls Enabled</th><td>{escape(str(instance_details['OutboundCallsEnabled']))}</td></tr>"
    
    # Contact flow logs
    if 'ContactFlowLogsEnabled' in instance_details:
        html += f"<tr><th>Contact Flow Logs Enabled</th><td>{escape(str(instance_details['ContactFlowLogsEnabled']))}</td></tr>"
    
    # Contact lens
    if 'ContactLensEnabled' in instance_details:
        html += f"<tr><th>Contact Lens Enabled</th><td>{escape(str(instance_details['ContactLensEnabled']))}</td></tr>"
    
    # Instance access URL
    if 'InstanceAccessUrl' in instance_details:
        access_url = instance_details['InstanceAccessUrl']
        access_url_link = normalize_instance_url(access_url)
        # Display clean URL without protocol in text
        clean_url = access_url.replace('https://', '').replace('http://', '')
        html += f"<tr><th>Instance Access URL</th><td><a href='{escape(access_url_link)}' target='_blank'>{escape(clean_url)}</a></td></tr>"
    
    html += "</table>"
    
    # Replication configuration
    try:
        replication_response = connect_client.describe_instance(InstanceId=instance_id)
        # Check if 'Instance' key exists in response
        if 'Instance' not in replication_response:
            html += "<h3>Replication Configuration</h3><p>No replication configuration available.</p>"
        # Check if 'ReplicationConfiguration' exists in the Instance
        elif 'ReplicationConfiguration' not in replication_response['Instance']:
            html += "<h3>Replication Configuration</h3><p>No replication configuration available.</p>"
        else:
            replication = replication_response['Instance']['ReplicationConfiguration']
            # Check if replication config is not None or empty
            if not replication:
                html += "<h3>Replication Configuration</h3><p>No replication configuration available.</p>"
            else:
                html += """
            <h3>Replication Configuration</h3>
            <table style="width: 70%;">
            """
                # Check for each replication field before accessing
                if 'ReplicationRegion' in replication:
                    html += f"<tr><th>Replication Region</th><td>{escape(replication['ReplicationRegion'])}</td></tr>"
                if 'ReplicationStatus' in replication:
                    html += f"<tr><th>Replication Status</th><td>{escape(replication['ReplicationStatus'])}</td></tr>"
                if 'GlobalSignInEndpoint' in replication:
                    html += f"<tr><th>Global Sign-In Endpoint</th><td>{escape(replication['GlobalSignInEndpoint'])}</td></tr>"
                html += "</table>"
    except Exception as e:
        logger.error(
            f"Error retrieving replication configuration for instance_id={instance_id}: "
            f"{type(e).__name__}: {str(e)}"
        )
        html += "<h3>Replication Configuration</h3><p>Unable to retrieve replication configuration.</p>"
    
    html += "</div>"
    return html


def generate_resilience_section(instance_info: Dict[str, Any]) -> str:
    """Generate resilience information section with ACGR recommendation if no replica"""
    html = """
    <div class="section">
        <h2>Resilience</h2>
        <p>Amazon Connect is designed for high availability and resilience:</p>
        <ul>
            <li><strong>Multi-AZ Architecture:</strong> Amazon Connect automatically distributes your instance across multiple Availability Zones in an active-active-active configuration.</li>
            <li><strong>Automatic Failover:</strong> If there is a failure in one AZ, that node is taken out of rotation without impacting production.</li>
            <li><strong>Zero Downtime Maintenance:</strong> This architecture allows you to perform maintenance, release new features, and expand infrastructure without requiring any downtime.</li>
            <li><strong>Data Replication:</strong> Contact data and configurations are automatically replicated across AZs for durability.</li>
        </ul>
        <p>For more information, refer to the <a href="https://docs.aws.amazon.com/connect/latest/adminguide/disaster-recovery-resiliency.html" target="_blank">Amazon Connect Disaster Recovery and Resiliency documentation</a>.</p>
    """
    
    # Check if instance has replication configured
    instance_id = instance_info.get('instance_id')
    has_replica = False
    
    if instance_id:
        try:
            response = connect_client.describe_instance(InstanceId=instance_id)
            instance_details = response.get('Instance', {})
            
            # Check if ReplicationConfiguration exists and is not empty
            if 'ReplicationConfiguration' in instance_details and instance_details['ReplicationConfiguration']:
                has_replica = True
        except Exception as e:
            logger.error(f"Error checking replication status: {e}")
    
    # Add ACGR recommendation if no replica is configured
    if not has_replica:
        html += """
        <h3>Amazon Connect Global Resiliency</h3>
        <h4>Recommendation</h4>
        <ul>
            <li>No replica configured. Consider Amazon Connect Global Resiliency (ACGR) for region resiliency requirements.</li>
            <li>ACGR provides customers with geographic telephony redundancy, offering a flexible solution to distribute inbound voice traffic and agents across linked instances with the same reserved capacity limit, in another Region in the event of unplanned Region outages or disruptions or other requirements.</li>
            <li>Refer to the <a href="https://docs.aws.amazon.com/connect/latest/adminguide/setup-connect-global-resiliency.html" target="_blank">Amazon Connect Global Resiliency documentation</a> for more information.</li>
        </ul>
        """
    
    html += "</div>"
    return html


def generate_quota_section(quota_data: Dict[str, Any]) -> str:
    """Generate quota analysis section"""
    if not quota_data or 'error' in quota_data:
        return "<h2>Quota Analysis</h2><p>Error retrieving quota data</p>"
    
    summary = quota_data.get('summary', {})
    quotas = quota_data.get('quotas', [])
    
    html = f"""
    <h2>Operational Excellence - Capacity Analysis</h2>
    
    <div class="metric-card">
        <h3>Summary</h3>
        <p>Total Resources Analyzed: {summary.get('total_analyzed', 0)}</p>
        <p>
            <span class="status-critical">Critical: {summary.get('critical', 0)}</span>
            <span class="status-warning">Warning: {summary.get('warning', 0)}</span>
            <span class="status-normal">Normal: {summary.get('normal', 0)}</span>
        </p>
    </div>
    
    <h3>Current Instance Usage vs Limits</h3>
    <table>
        <tr>
            <th>Resource Type</th>
            <th>Current Use</th>
            <th>Quota Limit</th>
            <th>Usage %</th>
            <th>Status</th>
        </tr>
    """
    
    for quota in quotas:
        status_class = f"status-{quota['status']}"
        html += f"""
        <tr>
            <td>{escape(quota['name'])}</td>
            <td>{quota['current']}</td>
            <td>{quota['limit']}</td>
            <td style="background-color: {quota['color']};">{quota['percentage']}%</td>
            <td><span class="{status_class}">{quota['status'].upper()}</span></td>
        </tr>
        """
    
    html += """
    </table>
    
    <div class="recommendation">
        <h4>Recommendations</h4>
        <ul>
            <li><span style="background-color: #00FF00; padding: 2px 8px;">Green</span>: Usage is well within limits</li>
            <li><span style="background-color: #FFA500; padding: 2px 8px;">Orange</span>: Usage is approaching limits - monitor closely</li>
            <li><span style="background-color: #FF0000; color: white; padding: 2px 8px;">Red</span>: Usage is critical - request quota increase via <a href="https://console.aws.amazon.com/servicequotas/home/services/connect/quotas" target="_blank">AWS Service Quotas Console</a></li>
        </ul>
    </div>
    """
    
    return html


def generate_metrics_section(metrics_data: Dict[str, Any], days_back: int, instance_access_url: str = None) -> str:
    """Generate comprehensive metrics analysis section"""
    if not metrics_data or 'error' in metrics_data:
        return "<h2>Metrics Analysis</h2><p>Error retrieving metrics data</p>"
    
    # Extract instance_id and region if available
    instance_id = metrics_data.get('instance_id', '')
    aws_region = metrics_data.get('aws_region', 'us-east-1')
    
    concurrent = metrics_data.get('concurrent_calls', {})
    missed = metrics_data.get('missed_calls', {})
    throttled = metrics_data.get('throttled_calls', {})
    queue_size = metrics_data.get('queue_size', {})
    calls_per_interval = metrics_data.get('calls_per_interval', {})
    
    html = f"""
    <h2>Performance Metrics (Last {days_back} Days)</h2>
    """
    
    # Add links to both CloudWatch and Connect console dashboards
    if instance_id:
        # CloudWatch metrics console URL
        cw_metrics_url = f"https://{aws_region}.console.aws.amazon.com/cloudwatch/home?region={aws_region}#metricsV2:graph=~();namespace=AWS/Connect;dimensions=InstanceId"
        html += f'<p><a href="{cw_metrics_url}" target="_blank" class="console-link">» View Metrics in CloudWatch Console</a></p>'
    
    # Add Connect instance console links for real-time and historical metrics
    if instance_access_url:
        # Normalize URL and build dashboard links
        base_url = normalize_instance_url(instance_access_url).replace('https://', '')
        realtime_url = f"https://{base_url}/real-time-metrics/landing"
        historical_url = f"https://{base_url}/historical-metrics/landing"
        html += f'<p><a href="{realtime_url}" target="_blank" class="console-link">» View Real-Time Metrics Dashboard</a> | '
        html += f'<a href="{historical_url}" target="_blank" class="console-link">Historical Metrics</a></p>'
    
    html += f"""
    <div class="metric-card">
        <h3>Concurrent Calls Analysis</h3>
        <table style="width: 60%;">
            <tr><th>Period Average</th><td>{concurrent.get('period_average', 0):.2f} calls</td></tr>
            <tr><th>Absolute Peak</th><td>{concurrent.get('absolute_peak', 0):.0f} calls</td></tr>
            <tr><th>Data Points</th><td>{concurrent.get('data_points', 0)} hours</td></tr>
        </table>
    </div>
    
    <div class="metric-card">
        <h3>Missed Calls Analysis</h3>
        <table style="width: 60%;">
            <tr><th>Total Missed Calls</th><td>{missed.get('total', 0):,}</td></tr>
            <tr><th>Daily Average</th><td>{missed.get('daily_average', 0):.1f} calls</td></tr>
            <tr><th>Days Analyzed</th><td>{missed.get('days_analyzed', 0)}</td></tr>
        </table>
    </div>
    """
    
    # Throttled Calls Section
    if throttled and 'error' not in throttled:
        severity = throttled.get('severity', 'Unknown')
        severity_colors = {
            'Excellent': '#00FF00',
            'Low': '#90EE90',
            'Moderate': '#FFFF00',
            'High': '#FFA500',
            'Critical': '#FF0000'
        }
        severity_color = severity_colors.get(severity, '#CCCCCC')
        
        html += f"""
        <div class="metric-card">
            <h3>Throttled Calls Analysis</h3>
            <p><strong>Severity:</strong> <span style="background-color: {severity_color}; padding: 5px 15px; border-radius: 3px; color: {'white' if severity in ['High', 'Critical'] else 'black'};">{severity}</span></p>
            <table style="width: 60%;">
                <tr><th>Total Throttled Calls</th><td>{throttled.get('total_throttled', 0):,}</td></tr>
                <tr><th>Average per Hour</th><td>{throttled.get('avg_hourly', 0):.2f}</td></tr>
                <tr><th>Maximum in Single Hour</th><td>{throttled.get('max_hourly', 0):,}</td></tr>
                <tr><th>Hours with Throttling</th><td>{throttled.get('hours_with_throttling', 0)} / {throttled.get('total_hours_analyzed', 0)}</td></tr>
            </table>
        """
        
        # Peak hours
        peak_hours = throttled.get('peak_hours', [])
        if peak_hours:
            html += """
            <h4>Peak Throttling Hours</h4>
            <table style="width: 70%;">
                <tr><th>Timestamp</th><th>Throttled Calls</th></tr>
            """
            for peak in peak_hours:
                html += f"<tr><td>{escape(peak['timestamp'])}</td><td>{peak['count']:,}</td></tr>"
            html += "</table>"
        
        # Recommendations
        recommendations = throttled.get('recommendations', [])
        if recommendations:
            html += "<h4>Recommendations</h4><ul>"
            for rec in recommendations:
                html += f"<li>{escape(rec)}</li>"
            html += "</ul>"
        
        html += "</div>"
    
    # Queue Size Section
    if queue_size and 'error' not in queue_size and 'message' not in queue_size:
        html += f"""
        <div class="metric-card">
            <h3>Queue Size Analysis</h3>
            <table style="width: 60%;">
                <tr><th>Average Queue Size</th><td>{queue_size.get('avg_queue_size', 0):.2f}</td></tr>
                <tr><th>Maximum Queue Size</th><td>{queue_size.get('max_queue_size', 0)}</td></tr>
                <tr><th>Data Points</th><td>{queue_size.get('data_points', 0)} hours</td></tr>
            </table>
        </div>
        """
    
    # Calls Per Interval Section
    if calls_per_interval and 'error' not in calls_per_interval and 'message' not in calls_per_interval:
        html += f"""
        <div class="metric-card">
            <h3>Calls Per Interval Analysis</h3>
            <table style="width: 60%;">
                <tr><th>Total Calls</th><td>{calls_per_interval.get('total_calls', 0):,}</td></tr>
                <tr><th>Average per Hour</th><td>{calls_per_interval.get('avg_per_hour', 0):.2f}</td></tr>
                <tr><th>Peak per Hour</th><td>{calls_per_interval.get('peak_per_hour', 0):,}</td></tr>
                <tr><th>Data Points</th><td>{calls_per_interval.get('data_points', 0)} hours</td></tr>
            </table>
        </div>
        """
    
    return html


def generate_phone_section(phone_data: Dict[str, Any], instance_access_url: str = None) -> str:
    """Generate comprehensive phone analysis section with cost insights"""
    if not phone_data or 'error' in phone_data:
        return "<h2>Phone Number Analysis</h2><p>Error retrieving phone data</p>"
    
    total_numbers = phone_data.get('total_numbers', 0)
    
    if total_numbers == 0:
        return "<h2>Cost Considerations - Phone Number Analysis</h2><p>No phone numbers found for this instance.</p>"
    
    html = f"""
    <h2>Cost Considerations - Phone Number Analysis</h2>
    """
    
    # Add console link to phone numbers using Connect instance console
    if instance_access_url:
        # Normalize URL and build phone numbers link
        base_url = normalize_instance_url(instance_access_url).replace('https://', '')
        phone_console_url = f"https://{base_url}/numbers#/"
        html += f'<p><a href="{phone_console_url}" target="_blank" class="console-link">» Manage Phone Numbers in Console</a></p>'
    
    html += f"""
    <div class="metric-card">
        <h3>Summary</h3>
        <p>Total Phone Numbers: {total_numbers}</p>
        <p>Carrier Diversity Score: {phone_data.get('carrier_diversity_score', 0)} unique carriers</p>
        <p>Countries: {phone_data.get('countries_count', 0)}</p>
        <p>Toll-Free Percentage: {phone_data.get('toll_free_percentage', 0):.1f}%</p>
        <p>DID Percentage: {phone_data.get('did_percentage', 0):.1f}%</p>
    </div>
    
    <h3>Phone Numbers by Type</h3>
    <table style="width: 60%;">
        <tr><th>Type</th><th>Count</th><th>Percentage</th></tr>
    """
    
    by_type = phone_data.get('by_type', {})
    for phone_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_numbers * 100) if total_numbers > 0 else 0
        html += f"<tr><td>{escape(phone_type)}</td><td>{count}</td><td>{percentage:.1f}%</td></tr>"
    
    html += """
    </table>
    
    <h3>Carrier Diversity Analysis</h3>
    <p>Distributing phone numbers across multiple carriers increases resilience and reduces single points of failure.</p>
    <table style="width: 80%;">
        <tr><th>Country | Carrier</th><th>Count</th><th>Phone Numbers</th></tr>
    """
    
    carrier_table = phone_data.get('carrier_diversity_table', [])
    for entry in carrier_table:
        numbers_str = ', '.join(entry['numbers'][:5])  # Show first 5 numbers
        if len(entry['numbers']) > 5:
            numbers_str += f" ... (+{len(entry['numbers']) - 5} more)"
        html += f"""
        <tr>
            <td>{escape(entry['country_carrier'])}</td>
            <td>{entry['count']}</td>
            <td style="font-size: 0.9em;">{escape(numbers_str)}</td>
        </tr>
        """
    
    html += "</table>"
    
    # Cost Insights
    cost_insights = phone_data.get('cost_insights', [])
    if cost_insights:
        html += """
        <h3>Cost & Capability Insights</h3>
        <div class="metric-card">
        """
        for insight in cost_insights:
            insight_type = insight.get('type', 'info')
            icon = '⚠️' if insight_type == 'warning' else '✅' if insight_type == 'positive' else 'ℹ️'
            html += f"""
            <p><strong>{icon} {escape(insight['message'])}</strong><br>
            <span style="color: #666; font-size: 0.9em;">{escape(insight['detail'])}</span></p>
            """
        html += "</div>"
    
    # Recommendations
    recommendations = phone_data.get('recommendations', [])
    if recommendations:
        html += """
        <div class="recommendation">
            <h4>Recommendations</h4>
        """
        
        # Group by priority
        high_priority = [r for r in recommendations if r.get('priority') == 'high']
        medium_priority = [r for r in recommendations if r.get('priority') == 'medium']
        low_priority = [r for r in recommendations if r.get('priority') == 'low']
        
        if high_priority:
            html += "<p><strong>High Priority:</strong></p><ul>"
            for rec in high_priority:
                html += f"<li><strong>{escape(rec['recommendation'])}</strong><br><span style='font-size: 0.9em; color: #666;'>{escape(rec['detail'])}</span></li>"
            html += "</ul>"
        
        if medium_priority:
            html += "<p><strong>Medium Priority:</strong></p><ul>"
            for rec in medium_priority:
                html += f"<li><strong>{escape(rec['recommendation'])}</strong><br><span style='font-size: 0.9em; color: #666;'>{escape(rec['detail'])}</span></li>"
            html += "</ul>"
        
        if low_priority:
            html += "<p><strong>Low Priority:</strong></p><ul>"
            for rec in low_priority:
                html += f"<li><strong>{escape(rec['recommendation'])}</strong><br><span style='font-size: 0.9em; color: #666;'>{escape(rec['detail'])}</span></li>"
            html += "</ul>"
        
        html += "</div>"
    
    # Additional resources
    html += """
    <div class="metric-card">
        <h4>Additional Resources</h4>
        <ul>
            <li><a href="https://docs.aws.amazon.com/connect/latest/adminguide/ag-overview-numbers.html" target="_blank">Amazon Connect Phone Number Types</a></li>
            <li><a href="https://docs.aws.amazon.com/connect/latest/adminguide/operational-excellence.html#prepare" target="_blank">Operational Excellence Best Practices</a></li>
        </ul>
    </div>
    """
    
    return html


def generate_flow_section(flow_data: Dict[str, Any], instance_access_url: str = None) -> str:
    """Generate flow analysis section"""
    if not flow_data or 'error' in flow_data:
        return "<h2>Contact Flow Analysis</h2><p>Error retrieving flow data</p>"
    
    html = f"""
    <h2>Contact Flow Analysis</h2>
    
    <div class="metric-card">
        <h3>Summary</h3>
        <p>Total Contact Flows: {flow_data.get('total_flows', 0)}</p>
        <p>Flows Without Logging: {flow_data.get('flows_without_logging_count', 0)}</p>
        <p>Logging Compliance: {flow_data.get('logging_compliance_percentage', 0):.1f}%</p>
    """
    
    # Add console link to contact flows using Connect instance console
    if instance_access_url:
        # Normalize URL and build flows link
        base_url = normalize_instance_url(instance_access_url).replace('https://', '')
        flows_console_url = f"https://{base_url}/contact-flows"
        html += f'<p><a href="{flows_console_url}" target="_blank" class="console-link">» Manage Contact Flows in Console</a></p>'
    
    html += "</div>"
    
    flows_without_logging = flow_data.get('flows_without_logging', [])
    
    if flows_without_logging:
        html += """
        <h3>Flows Missing Logging Configuration</h3>
        <table>
            <tr><th>Flow Name</th><th>Flow ID</th><th>Type</th><th>State</th><th>Status</th><th>Actions</th></tr>
        """
        
        for flow in flows_without_logging:
            flow_id = flow.get('id', '')
            flow_arn = flow.get('arn', '')
            
            # Build console link to edit the specific flow using Connect instance console
            if instance_access_url and flow_arn:
                # Normalize URL and build flow editor link
                base_url = normalize_instance_url(instance_access_url).replace('https://', '')
                # Deep link directly to the flow editor with ARN
                flow_edit_url = f"https://{base_url}/contact-flows/edit?id={flow_arn}&tab=designer"
                action_link = f'<a href="{flow_edit_url}" target="_blank">Edit Flow</a>'
            else:
                action_link = 'N/A'
            
            html += f"""
            <tr>
                <td>{escape(flow['name'])}</td>
                <td>{escape(flow['id'])}</td>
                <td>{escape(flow['type'])}</td>
                <td>{escape(flow.get('state', 'UNKNOWN'))}</td>
                <td>{escape(flow.get('status', 'UNKNOWN'))}</td>
                <td>{action_link}</td>
            </tr>
            """
        
        html += """
        </table>
        
        <div class="recommendation">
            <h4>Recommendations</h4>
            <ul>
                <li>Enable logging in contact flows using the "Set logging behavior" block</li>
                <li>Logging helps with troubleshooting and compliance</li>
                <li>Consider disabling logging only for segments handling sensitive data</li>
                <li>Learn more: <a href="https://docs.aws.amazon.com/connect/latest/adminguide/about-contact-flow-logs.html" target="_blank">Contact Flow Logging Documentation</a></li>
            </ul>
        </div>
        """
    else:
        html += "<p>✅ All contact flows have logging properly configured!</p>"
    
    return html


def generate_cloudtrail_section(cloudtrail_data: Dict[str, Any], days_back: int) -> str:
    """Generate CloudTrail API throttling analysis section"""
    if not cloudtrail_data or 'error' in cloudtrail_data:
        return ""  # Skip section if no data
    
    total_throttled = cloudtrail_data.get('total_throttled', 0)
    
    if total_throttled == 0:
        return """
        <h2>Amazon Connect API Throttling (Account Level)</h2>
        <div class="metric-card">
            <p>✅ No API throttling detected in the last {days_back} days. Your API usage is within limits.</p>
        </div>
        """
    
    html = f"""
    <h2>Amazon Connect API Throttling (Account Level)</h2>
    """
    
    # Add CloudTrail console link
    aws_region = cloudtrail_data.get('region', 'us-east-1')
    cloudtrail_url = f"https://{aws_region}.console.aws.amazon.com/cloudtrailv2/home?region={aws_region}#/events"
    html += f'<p><a href="{cloudtrail_url}" target="_blank" class="console-link">» View API Calls in CloudTrail Console</a></p>'
    
    html += f"""
    <div class="metric-card">
        <h3>Summary</h3>
        <p>Total Events Analyzed: {cloudtrail_data.get('total_events_analyzed', 0):,}</p>
        <p>Total Throttled API Calls: <strong style="color: #FF0000;">{total_throttled:,}</strong></p>
        <p>Account: {escape(cloudtrail_data.get('account_id', 'N/A'))}</p>
        <p>Region: {escape(aws_region)}</p>
    </div>
    
    <h3>Throttled API Calls by Event Type</h3>
    <table style="width: 70%;">
        <tr><th>API Event Name</th><th>Throttle Count</th></tr>
    """
    
    throttled_apis = cloudtrail_data.get('throttled_by_api', [])
    for api in throttled_apis:
        html += f"<tr><td>{escape(api['event_name'])}</td><td>{api['count']:,}</td></tr>"
    
    html += "</table>"
    
    # Recommendations
    recommendations = cloudtrail_data.get('recommendations', [])
    if recommendations:
        html += """
        <div class="recommendation">
            <h4>Recommendations</h4>
            <ul>
        """
        for rec in recommendations:
            html += f"<li>{escape(rec)}</li>"
        html += """
            </ul>
        </div>
        """
    
    return html


def generate_log_insights_section(log_data: Dict[str, Any], days_back: int) -> str:
    """Generate CloudWatch Log Insights analysis section"""
    if not log_data or 'error' in log_data:
        return ""  # Skip section if no data
    
    total_errors = log_data.get('total_errors', 0)
    log_group = log_data.get('log_group', '')
    aws_region = log_data.get('aws_region', 'us-east-1')
    
    if total_errors == 0:
        html = f"""
        <h2>Contact Flow Error Analysis</h2>
        <div class="metric-card">
            <p>✅ No contact flow errors detected in logs for the last {days_back} days.</p>
        </div>
        """
    else:
        html = f"""
        <h2>Contact Flow Error Analysis</h2>
        """
        
        # Add CloudWatch Logs Insights console link
        if log_group:
            # URL encode the log group name
            import urllib.parse
            encoded_log_group = urllib.parse.quote(log_group)
            logs_insights_url = f"https://{aws_region}.console.aws.amazon.com/cloudwatch/home?region={aws_region}#logsV2:logs-insights$3FqueryDetail$3D~(end~0~start~-{days_back*86400}~timeType~'RELATIVE~unit~'seconds~editorString~'fields*20*40timestamp*2c*20*40message*0a*7c*20filter*20*40message*20like*20*2fERROR*2f*0a*7c*20sort*20*40timestamp*20desc~isLiveTail~false~queryId~'~source~(~'{encoded_log_group}))"
            html += f'<p><a href="{logs_insights_url}" target="_blank" class="console-link">» View Logs in CloudWatch Logs Insights</a></p>'
        
        html += f"""
        <div class="metric-card">
            <h3>Summary</h3>
            <p>Total Errors Found: <strong style="color: #FF0000;">{total_errors:,}</strong></p>
            <p>Flows with Errors: {log_data.get('flows_with_errors', 0)}</p>
            <p>Log Group: {escape(log_group)}</p>
            <p>Days Analyzed: {log_data.get('days_analyzed', days_back)}</p>
        </div>
        """
    
    # Error types distribution
    error_types = log_data.get('error_types', {})
    if error_types:
        html += """
        <h3>Error Types Distribution</h3>
        <table style="width: 60%;">
            <tr><th>Error Type</th><th>Count</th></tr>
        """
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            html += f"<tr><td>{escape(error_type)}</td><td>{count:,}</td></tr>"
        html += "</table>"
    
    # Top flows with errors
    error_summary = log_data.get('error_summary', [])
    if error_summary:
        html += """
        <h3>Top Contact Flows with Errors</h3>
        <table style="width: 80%;">
            <tr><th>Flow Name</th><th>Flow ID</th><th>Error Count</th></tr>
        """
        for flow in error_summary:
            html += f"""
            <tr>
                <td>{escape(flow['flow_name'])}</td>
                <td style="font-size: 0.85em;">{escape(flow['flow_id'])}</td>
                <td><strong>{flow['error_count']:,}</strong></td>
            </tr>
            """
        html += "</table>"
    
    # Sample errors
    sample_errors = log_data.get('sample_errors', [])
    if sample_errors:
        html += """
        <h3>Sample Recent Errors</h3>
        <table style="width: 100%;">
            <tr><th>Timestamp</th><th>Flow Name</th><th>Error Message</th></tr>
        """
        for error in sample_errors[:10]:  # Show first 10
            html += f"""
            <tr>
                <td style="font-size: 0.85em;">{escape(error.get('timestamp', 'N/A'))}</td>
                <td>{escape(error.get('flow_name', 'Unknown'))}</td>
                <td style="font-size: 0.85em;">{escape(error.get('message', 'N/A'))}</td>
            </tr>
            """
        html += "</table>"
    
    # Recommendations
    recommendations = log_data.get('recommendations', [])
    if recommendations:
        html += """
        <div class="recommendation">
            <h4>Recommendations</h4>
            <ul>
        """
        for rec in recommendations:
            html += f"<li>{escape(rec)}</li>"
        html += """
            </ul>
        </div>
        """
    
    return html


def generate_html_footer() -> str:
    """Generate HTML footer"""
    return """
        </div>
    </body>
    </html>
    """


def lambda_handler(event, context):
    """Main handler for report generation"""
    try:
        logger.info("Starting report generation")
        
        review_id = event['reviewId']
        instance_info = event['instanceInfo']
        days_back = event.get('daysBack', 14)
        
        # Create Connect client with correct region
        global connect_client
        connect_client = boto3.client('connect', region_name=instance_info['aws_region'])
        
        # Get instance details to extract access URL
        instance_id = instance_info.get('instance_id')
        instance_access_url = None
        if instance_id:
            instance_details = get_instance_details(instance_id)
            if instance_details and 'InstanceAccessUrl' in instance_details:
                instance_access_url = instance_details['InstanceAccessUrl']
        
        # Retrieve all analysis results
        results = get_all_results(review_id)
        
        # Organize results by component type
        results_by_type = {r['componentType']: r['data'] for r in results}
        
        # Generate HTML report
        html_content = generate_html_header(instance_info)
        html_content += generate_instance_details_section(instance_info)
        html_content += generate_resilience_section(instance_info)
        html_content += generate_quota_section(results_by_type.get('quota', {}))
        html_content += generate_metrics_section(results_by_type.get('metrics', {}), days_back, instance_access_url)
        html_content += generate_cloudtrail_section(results_by_type.get('cloudtrail', {}), days_back)
        html_content += generate_phone_section(results_by_type.get('phone', {}), instance_access_url)
        html_content += generate_flow_section(results_by_type.get('flow', {}), instance_access_url)
        html_content += generate_log_insights_section(results_by_type.get('logs', {}), days_back)
        html_content += generate_html_footer()
        
        # Upload to S3
        bucket_name = os.environ.get('S3_REPORTING_BUCKET')
        object_key = f'connect-ops-review-{review_id}.html'
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=html_content,
            ContentType='text/html'
        )
        
        report_url = f"https://{bucket_name}.s3.amazonaws.com/{object_key}"
        
        logger.info(f"Report generated successfully: {report_url}")
        
        return {
            'statusCode': 200,
            'reportUrl': report_url,
            'reviewId': review_id
        }
        
    except Exception as e:
        logger.error(f"Report generator error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'error': str(e)
        }
