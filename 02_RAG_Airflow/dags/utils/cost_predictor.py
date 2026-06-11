"""
Cost prediction and budgeting based on historical data.
Uses linear regression to forecast future costs.
"""

import logging
from typing import Dict, List
import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta
import json
from typing import Any, Dict, List
import requests

logger = logging.getLogger(__name__)


def predict_monthly_cost(
    historical_costs: List[Dict[str, float]],
    days_to_predict: int = 30
) -> Dict[str, float]:
    """
    Predict future costs using linear regression.
    
    Args:
        historical_costs: List of {'timestamp': unix_timestamp, 'cost': float}
        days_to_predict: Number of days to forecast
        
    Returns:
        Prediction dictionary with estimates
    """
    if len(historical_costs) < 3:
        logger.warning("Not enough historical data for prediction (need at least 3 points)")
        return {
            'predicted_cost': 0.0,
            'confidence': 'low',
            'message': 'Insufficient historical data'
        }
    
    # Step 1: Prepare data
    timestamps = np.array([point['timestamp'] for point in historical_costs]).reshape(-1, 1)
    costs = np.array([point['cost'] for point in historical_costs])
    
    # Step 2: Train linear regression model
    model = LinearRegression()
    model.fit(timestamps, costs)
    
    # Step 3: Predict future costs
    now = datetime.now().timestamp()
    future_timestamp = now + (days_to_predict * 24 * 60 * 60)
    predicted_daily_cost = float(model.predict([[future_timestamp]])[0])

    predicted_cost = predicted_daily_cost * days_to_predict 
    
    # Step 4: Calculate confidence based on R² score
    r2_score = model.score(timestamps, costs)
    
    if r2_score > 0.8:
        confidence = 'high'
    elif r2_score > 0.5:
        confidence = 'medium'
    else:
        confidence = 'low'
    
    # Step 5: Calculate daily and monthly averages
    daily_avg = predicted_daily_cost   
    monthly_estimate = predicted_daily_cost * 30     
    
    # Step 6: Identify trend
    slope = model.coef_[0]
    if slope > 0:
        trend = 'increasing'
    elif slope < 0:
        trend = 'decreasing'
    else:
        trend = 'stable'
    
    logger.info(
        f"Cost prediction: ${predicted_cost:.2f} over {days_to_predict} days "
        f"(monthly: ${monthly_estimate:.2f}, trend: {trend}, confidence: {confidence})"
    )
    
    return {
        'predicted_cost': round(predicted_cost, 2),
        'daily_avg': round(daily_avg, 4),
        'monthly_estimate': round(monthly_estimate, 2),
        'trend': trend,
        'confidence': confidence,
        'r2_score': round(r2_score, 3),
        'days_predicted': days_to_predict
    }


def get_historical_costs_from_prometheus(
    prometheus_url: str = 'http://prometheus:9090',
    metric_name: str = 'rag_embedding_cost_usd',
    days_back: int = 30
) -> List[Dict[str, float]]:
    """
    Fetch historical cost data from Prometheus.
    
    Args:
        prometheus_url: Prometheus server URL
        metric_name: Metric to query
        days_back: How many days of history to fetch
        
    Returns:
        List of cost data points
    """
    import requests
    
    try:
        # Query Prometheus range data
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)
        
        query = f'{metric_name}[{days_back}d]'
        
        response = requests.get(
            f'{prometheus_url}/api/v1/query',
            params={'query': query},
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Parse results
        if data['status'] == 'success' and data['data']['result']:
            values = data['data']['result'][0]['values']
            historical_costs = [
                {'timestamp': float(ts), 'cost': float(value)}
                for ts, value in values
            ]
            
            logger.info(f"Fetched {len(historical_costs)} historical cost data points")
            return historical_costs
        else:
            logger.warning("No historical cost data found in Prometheus")
            return []
    
    except Exception as e:
        logger.error(f"Error fetching from Prometheus: {e}")
        return []


def generate_cost_budget_alert(
    current_cost: float,
    predicted_monthly_cost: float,
    budget_limit: float = 50.0
) -> Dict[str, Any]:
    # Calculate utilization
    utilization = (predicted_monthly_cost / budget_limit) * 100
    
    # Calculate derived values
    predicted_cost = predicted_monthly_cost
    daily_avg = current_cost
    monthly_estimate = predicted_monthly_cost
    
    # Use >= for thresholds (not >)
    if utilization >= 100:  # Changed from > to >=
        severity = 'critical'
        message = f"🚨 Cost exceeding budget! Predicted: ${predicted_monthly_cost:.2f} > Budget: ${budget_limit:.2f}"
    elif utilization >= 95:  # Changed from > 95 to >= 95
        severity = 'warning'
        message = f"⚠️ Cost approaching budget limit ({utilization:.1f}% of ${budget_limit:.2f})"
    else:
        severity = 'ok'
        message = f"✅ Cost within budget ({utilization:.1f}% of ${budget_limit:.2f})"
    
    return {
        'severity': severity,
        'message': message,
        'utilization': round(utilization, 1),
        "predicted_cost": round(predicted_cost, 2),
        "predicted_monthly_cost": round(predicted_monthly_cost, 2),
        "daily_avg": round(daily_avg, 4),
        "monthly_estimate": round(monthly_estimate, 2),
        'budget_limit': budget_limit,
        'current_cost': current_cost
    }