"""
Embedding generation using OpenAI or local models.
"""

import logging
import os
from typing import List, Dict, Any
import time
#from openai import OpenAI
#import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
def _get_openai_embeddings(texts: List[str], model: str) -> List[List[float]]:
    """
    Get embeddings from OpenAI API with retry logic.
    
    Args:
        texts: List of texts to embed
        model: OpenAI embedding model name
        
    Returns:
        List of embedding vectors
    """
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    response = client.embeddings.create(
        model=model,
        input=texts,
    )
    
    embeddings = [item.embedding for item in response.data]
    return embeddings


def _get_local_embeddings(texts: List[str], model_name: str) -> List[List[float]]:
    """
    Get embeddings from local SentenceTransformer model.
    
    Args:
        texts: List of texts to embed
        model_name: HuggingFace model name
        
    Returns:
        List of embedding vectors
    """
    from sentence_transformers import SentenceTransformer
    
    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, show_progress_bar=False)
    
    return embeddings.tolist()


def embed_chunks(
    chunks: Any,
    model_name: str = "text-embedding-3-small",
    batch_size: int = 100,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Generate embeddings for text chunks.
    
    Args:
        chunks: List of chunk dictionaries or XCom reference
        model_name: Name of embedding model (OpenAI or HuggingFace)
        batch_size: Number of chunks to embed in one API call
        
    Returns:
        List of chunks with added 'embedding' field
    """
    # Handle XCom input
    if isinstance(chunks, str):
        try:
            chunks = eval(chunks)
        except Exception as e:
            logger.error(f"Could not parse chunks from XCom: {e}")
            return []
    
    if not chunks:
        logger.warning("No chunks to embed")
        return []
    
    # Parse parameters
    if isinstance(model_name, str) and model_name.startswith("{{"):
        # Handle Airflow template
        model_name = "text-embedding-3-small"
    if isinstance(batch_size, str):
        batch_size = int(batch_size)
    
    logger.info(f"Starting embedding for {len(chunks)} chunks using model '{model_name}'")
    
    embedded_chunks = []
    total_tokens = 0
    start_time = time.time()
    
    # Determine if using OpenAI or local model
    is_openai = model_name.startswith('text-embedding-')
    
    # Process in batches
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        batch_texts = [chunk['text'] for chunk in batch]
        
        try:
            if is_openai:
                embeddings = _get_openai_embeddings(batch_texts, model_name)
                # Estimate tokens (rough)
                total_tokens += sum(len(text.split()) * 1.3 for text in batch_texts)
            else:
                embeddings = _get_local_embeddings(batch_texts, model_name)
            
            # Add embeddings to chunks
            for chunk, embedding in zip(batch, embeddings):
                chunk['embedding'] = embedding
                chunk['embedding_model'] = model_name
                chunk['embedding_dimension'] = len(embedding)
                embedded_chunks.append(chunk)
            
            logger.debug(f"Embedded batch {i//batch_size + 1}/{(len(chunks)-1)//batch_size + 1}")
            
        except Exception as e:
            logger.error(f"Error embedding batch starting at index {i}: {e}")
            # Continue with next batch
            continue
    
    elapsed_time = time.time() - start_time
    
    logger.info(
        f"Embedding complete: {len(embedded_chunks)} chunks embedded in {elapsed_time:.2f}s "
        f"({len(embedded_chunks)/elapsed_time:.2f} chunks/sec)"
    )
    
    # Export metrics
    from utils.metrics_exporter import export_counter, export_histogram
    export_counter('chunks_embedded_total', len(embedded_chunks))
    export_counter('embedding_tokens_total', int(total_tokens))
    export_histogram('embedding_latency_seconds', elapsed_time)
    
    # Estimate cost (OpenAI pricing as of 2024)
    if is_openai:
        cost_per_1k_tokens = 0.00002  # $0.02 per 1M tokens
        estimated_cost = (total_tokens / 1000) * cost_per_1k_tokens
        export_counter('embedding_cost_usd', estimated_cost)
        logger.info(f"Estimated embedding cost: ${estimated_cost:.4f}")
    
    return embedded_chunks