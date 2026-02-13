"""
Phone Analyzer Lambda Function
Analyzes phone numbers and carrier diversity
"""
import os
import json
import boto3
import logging
from typing import Dict, Any, List
from collections import Counter, defaultdict

from storage_helper import store_result

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global clients - will be initialized with correct region in lambda_handler
connect_client = None
pinpoint_client = None


def validate_phone_number(phone_number: str, country_code: str) -> Dict[str, Any]:
    """Validate phone number and get carrier information"""
    try:
        response = pinpoint_client.phone_number_validate(
            NumberValidateRequest={
                'PhoneNumber': phone_number,
                'IsoCountryCode': country_code
            }
        )
        
        result = response['NumberValidateResponse']
        return {
            'carrier': result.get('Carrier', 'Unknown'),
            'phone_type': result.get('PhoneType', 'Unknown'),
            'is_valid': result.get('PhoneType') != 'INVALID'
        }
        
    except Exception as e:
        logger.error(f"Error validating phone number {phone_number}: {e}")
        return {'carrier': 'Unknown', 'phone_type': 'Unknown', 'is_valid': False}


def analyze_phone_numbers(instance_id: str) -> Dict[str, Any]:
    """
    Comprehensive phone number analysis including cost optimization and diversity
    """
    try:
        phone_numbers = []
        paginator = connect_client.get_paginator('list_phone_numbers_v2')
        
        for page in paginator.paginate(InstanceId=instance_id):
            for number_summary in page.get('ListPhoneNumbersSummaryList', []):
                phone_info = validate_phone_number(
                    number_summary['PhoneNumber'],
                    number_summary['PhoneNumberCountryCode']
                )
                
                phone_numbers.append({
                    'phone_number': number_summary['PhoneNumber'],
                    'type': number_summary['PhoneNumberType'],
                    'country': number_summary['PhoneNumberCountryCode'],
                    'carrier': phone_info['carrier'],
                    'phone_type_detail': phone_info['phone_type']
                })
        
        total_numbers = len(phone_numbers)
        
        if total_numbers == 0:
            return {
                'total_numbers': 0,
                'message': 'No phone numbers found',
                'recommendations': []
            }
        
        # Analyze diversity
        type_counts = Counter(pn['type'] for pn in phone_numbers)
        country_counts = Counter(pn['country'] for pn in phone_numbers)
        carrier_counts = Counter(pn['carrier'] for pn in phone_numbers)
        
        # Group by country and carrier for diversity analysis
        country_carrier_groups = defaultdict(list)
        for pn in phone_numbers:
            key = f"{pn['country']}|{pn['carrier']}"
            country_carrier_groups[key].append(pn['phone_number'])
        
        # Convert to list format for report
        carrier_diversity_table = [
            {
                'country_carrier': key,
                'count': len(numbers),
                'numbers': numbers
            }
            for key, numbers in sorted(country_carrier_groups.items(), key=lambda x: len(x[1]), reverse=True)
        ]
        
        # Cost optimization analysis
        toll_free_count = type_counts.get('TOLL_FREE', 0)
        did_count = type_counts.get('DID', 0)
        uifn_count = type_counts.get('UIFN', 0)
        short_code_count = type_counts.get('SHORT_CODE', 0)
        third_party_tf_count = type_counts.get('THIRD_PARTY_TF', 0)
        third_party_did_count = type_counts.get('THIRD_PARTY_DID', 0)
        
        toll_free_percentage = (toll_free_count / total_numbers * 100) if total_numbers > 0 else 0
        did_percentage = (did_count / total_numbers * 100) if total_numbers > 0 else 0
        
        # International presence
        countries_count = len(country_counts)
        
        # Generate cost optimization insights
        cost_insights = []
        
        if toll_free_percentage > 70:
            cost_insights.append({
                'type': 'warning',
                'message': f'High toll-free usage: {toll_free_percentage:.1f}% of numbers are toll-free',
                'detail': 'Toll-free numbers provide additional resiliency but come with higher costs compared to DIDs'
            })
        elif toll_free_percentage < 20 and toll_free_count > 0:
            cost_insights.append({
                'type': 'info',
                'message': f'Low toll-free usage: Only {toll_free_percentage:.1f}% are toll-free',
                'detail': 'Consider customer accessibility and toll-free options for better customer experience'
            })
        
        if did_percentage > 50:
            cost_insights.append({
                'type': 'info',
                'message': f'DID numbers provide local presence: {did_percentage:.1f}% of total numbers',
                'detail': 'DIDs are cost-effective but provide less carrier redundancy than toll-free numbers'
            })
        
        if countries_count > 1:
            cost_insights.append({
                'type': 'positive',
                'message': f'International presence: Numbers in {countries_count} countries',
                'detail': 'Multi-country presence improves global accessibility'
            })
        
        if uifn_count > 0:
            cost_insights.append({
                'type': 'positive',
                'message': f'Global accessibility: {uifn_count} UIFN numbers for international toll-free access',
                'detail': 'UIFN provides consistent international toll-free experience'
            })
        
        if short_code_count > 0:
            cost_insights.append({
                'type': 'positive',
                'message': f'SMS capability: {short_code_count} short codes for messaging services',
                'detail': 'Short codes enable SMS/text messaging capabilities'
            })
        
        # Generate recommendations
        recommendations = []
        
        # Carrier diversity recommendations
        if len(carrier_counts) < 2 and total_numbers > 1:
            recommendations.append({
                'priority': 'high',
                'category': 'Carrier Diversity',
                'recommendation': 'Consider diversifying across multiple carriers for increased resilience',
                'detail': 'Single carrier dependency creates a potential single point of failure'
            })
        
        # Toll-free recommendations
        if toll_free_count == 0:
            recommendations.append({
                'priority': 'medium',
                'category': 'Cost vs Resilience',
                'recommendation': 'Consider using toll-free numbers for international toll-free access',
                'detail': 'In the US, toll-free numbers provide automatic load balancing across multiple carriers'
            })
        
        if toll_free_count > 0 and did_count > 0 and toll_free_count < did_count:
            recommendations.append({
                'priority': 'medium',
                'category': 'Resilience',
                'recommendation': 'In the US, use toll-free phone numbers wherever possible to load balance across multiple carriers',
                'detail': 'For DIDs, load balance across numbers from multiple carriers when possible. This comes at additional cost.'
            })
        
        if toll_free_count > did_count and toll_free_count > 5:
            recommendations.append({
                'priority': 'low',
                'category': 'Cost Optimization',
                'recommendation': 'Review toll-free vs DID balance for cost optimization',
                'detail': 'Toll-free numbers provide additional resiliency but come with higher costs. Apply your workload availability and resiliency requirements.'
            })
        
        # SMS capability recommendation
        if short_code_count == 0 and total_numbers > 5:
            recommendations.append({
                'priority': 'low',
                'category': 'Capability',
                'recommendation': 'Consider short codes if SMS/text messaging is needed',
                'detail': 'Short codes enable two-way SMS communication with customers'
            })
        
        return {
            'total_numbers': total_numbers,
            'by_type': dict(type_counts),
            'by_country': dict(country_counts),
            'by_carrier': dict(carrier_counts),
            'carrier_diversity_table': carrier_diversity_table,
            'carrier_diversity_score': len(carrier_counts),
            'countries_count': countries_count,
            'toll_free_percentage': round(toll_free_percentage, 1),
            'did_percentage': round(did_percentage, 1),
            'has_uifn': uifn_count > 0,
            'has_short_code': short_code_count > 0,
            'has_third_party': (third_party_tf_count + third_party_did_count) > 0,
            'cost_insights': cost_insights,
            'recommendations': recommendations,
            'phone_numbers': phone_numbers
        }
        
    except Exception as e:
        logger.error(f"Error analyzing phone numbers: {e}")
        return {'error': str(e)}


def lambda_handler(event, context):
    """Main handler for phone analysis"""
    try:
        logger.info("Starting phone analysis")
        
        review_id = event['reviewId']
        instance_id = event['instanceId']
        aws_region = event['awsRegion']
        ttl = event['ttl']
        
        # Create clients with correct region
        global connect_client, pinpoint_client
        connect_client = boto3.client('connect', region_name=aws_region)
        pinpoint_client = boto3.client('pinpoint', region_name=aws_region)
        
        # Perform analysis
        analysis_result = analyze_phone_numbers(instance_id)
        
        # Store results
        store_result(review_id, 'phone', analysis_result, ttl)
        
        logger.info(f"Phone analysis completed: {analysis_result.get('total_numbers', 0)} numbers analyzed")
        
        return {
            'statusCode': 200,
            'componentType': 'phone'
        }
        
    except Exception as e:
        logger.error(f"Phone analyzer error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'error': str(e)
        }
