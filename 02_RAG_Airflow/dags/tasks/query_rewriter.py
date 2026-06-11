"""
Query rewriting using LLM to expand queries for better recall.
Handles acronyms, synonyms, and related terms.
"""

import logging
import os
from typing import List, Dict
from openai import OpenAI
import json
import re

from utils.metrics_exporter import export_counter

logger = logging.getLogger(__name__)


def rewrite_query_with_llm(query: str, max_variations: int = 3) -> List[str]:
    """
    Rewrite query using LLM.
    
    Args:
        query: Original query
        max_variations: Maximum number of variations
        
    Returns:
        List of query variations (without the original)
    """
    # Mock implementation for now
    # Return variations WITHOUT the original
    return ["variation 1", "variation 2"]




def rewrite_query_rule_based(query: str) -> List[str]:
    """
    Simple rule-based query expansion (no LLM needed).
    
    Args:
        query: Original query
        
    Returns:
        List of query variations
    """
    # Common acronym mappings
    acronym_map = {
        'pto': 'paid time off',
        'ppo': 'preferred provider organization',
        'hmo': 'health maintenance organization',
        'faq': 'frequently asked questions',
        'rsu': 'restricted stock unit',
        'okr': 'objectives and key results',
        'api': 'application programming interface',
        'vpn': 'virtual private network',
        'hr': 'human resources',
        'it': 'information technology',
    }
    
    query_lower = query.lower()
    tokens = re.findall(r"\w+", query_lower)
    variations = [query]
    
    # Expand acronyms
    for acronym, expansion in acronym_map.items():
        if acronym in tokens:
            expanded = query_lower.replace(acronym, expansion)
            variations.append(expanded)
            
            # Also add version with OR
            or_version = query_lower.replace(acronym, f"{acronym} OR {expansion}")
            variations.append(or_version)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_variations = []
    for v in variations:
        if v not in seen:
            seen.add(v)
            unique_variations.append(v)
    
    logger.info(f"Rule-based expansion: {len(unique_variations)} variations")
    
    return unique_variations



def rewrite_query(
    query: str,
    use_llm: bool = True,
    max_variations: int = 3,
    **kwargs
) -> List[str]:
    """
    Main query rewriting function.
    
    Args:
        query: Original query
        use_llm: Whether to use LLM (True) or rule-based (False)
        max_variations: Max number of variations
        
    Returns:
        List of query variations (including original)
    """
    logger.info(f"Rewriting query: '{query}' (use_llm={use_llm})")
    
    # Start with original query
    variations = [query]
    
    # Get additional variations from the appropriate function
    if use_llm:
        additional = rewrite_query_with_llm(query, max_variations)
    else:
        additional = rewrite_query_rule_based(query)
    
    # Add additional variations
    variations.extend(additional)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_variations = []
    for v in variations:
        if v not in seen:
            seen.add(v)
            unique_variations.append(v)
    
    # Export metrics
    from utils.metrics_exporter import export_counter
    num_rewrites = len(unique_variations) - 1  # Don't count original
    export_counter('query_rewrites_total', num_rewrites)
    
    logger.info(f"Final query variations: {unique_variations}")
    
    return unique_variations


