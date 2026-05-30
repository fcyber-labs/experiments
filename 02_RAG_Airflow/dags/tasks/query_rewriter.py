"""
Query rewriting using LLM to expand queries for better recall.
Handles acronyms, synonyms, and related terms.
"""

import logging
import os
from typing import List, Dict
from openai import OpenAI
import json

logger = logging.getLogger(__name__)


def rewrite_query_with_llm(query: str, max_variations: int = 3) -> List[str]:
    """
    Use LLM to generate query variations.
    
    Args:
        query: Original query
        max_variations: Maximum number of variations to generate
        
    Returns:
        List of query variations (including original)
    """
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    prompt = f"""Given the search query below, generate {max_variations} alternative phrasings 
that capture the same intent. Include:
- Expanded acronyms
- Synonyms
- Related terms
- Different phrasings

Return ONLY a JSON array of strings, nothing else.

Original query: "{query}"

Example output format:
["variation 1", "variation 2", "variation 3"]
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a query expansion expert. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )
        
        variations_text = response.choices[0].message.content.strip()
        
        # Parse JSON
        variations = json.loads(variations_text)
        
        # Add original query
        all_queries = [query] + variations[:max_variations]
        
        logger.info(f"Generated {len(variations)} query variations for: '{query}'")
        
        return all_queries
    
    except Exception as e:
        logger.error(f"Error rewriting query: {e}")
        # Fallback: return only original query
        return [query]


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
    variations = [query]
    
    # Expand acronyms
    for acronym, expansion in acronym_map.items():
        if acronym in query_lower.split():
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
        List of query variations
    """
    logger.info(f"Rewriting query: '{query}' (use_llm={use_llm})")
    
    if use_llm:
        variations = rewrite_query_with_llm(query, max_variations)
    else:
        variations = rewrite_query_rule_based(query)
    
    # Export metrics
    from utils.metrics_exporter import export_counter
    export_counter('query_rewrites_total', len(variations) - 1)  # Don't count original
    
    logger.info(f"Final query variations: {variations}")
    
    return variations