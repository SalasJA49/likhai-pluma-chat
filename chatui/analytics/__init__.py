"""
Analytics module for BSP AI Assistant
Provides chart generation and AI-powered insights
"""

from analytics.chart_generator import ChartGenerator
from analytics.insight_generator import InsightGenerator
from analytics.analytics_handler import AnalyticsHandler, handle_analytics_command
<<<<<<< HEAD

=======
from analytics.sql_agent import SQLAgent
>>>>>>> 2c6d00a (eda (sql, chart, insight) and deep research)
__all__ = [
    'ChartGenerator',
    'InsightGenerator',
    'AnalyticsHandler',
    'handle_analytics_command'
<<<<<<< HEAD
=======
    'SQLAgent'
    
>>>>>>> 2c6d00a (eda (sql, chart, insight) and deep research)
]

__version__ = '1.0.0'