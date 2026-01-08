"""
Catastrophe Classifier for FusionBot
====================================

Uses sentence transformers to semantically classify headlines as catastrophes.
Replaces keyword matching with semantic similarity for better accuracy.
"""

from typing import Optional
import numpy as np
from sentence_transformers import SentenceTransformer

from src.utils.logging import get_logger

logger = get_logger(__name__)


class CatastropheClassifier:
    """
    Classifies headlines as catastrophes using semantic similarity.
    
    Uses sentence transformer embeddings to compare headlines against
    reference examples of actual catastrophes vs hypothetical/analytical articles.
    """
    
    # Reference examples of ACTUAL catastrophes (real events)
    CATASTROPHE_EXAMPLES = [
        "Market crashes 20% as trading halted on NYSE",
        "Exchange hack: $100M stolen from Binance",
        "Circuit breaker triggered: S&P 500 drops 7%",
        "Flash crash wipes out $1 trillion in market value",
        "Trading halted across all major exchanges",
        "Black swan event causes systemic market collapse",
        "Bank run forces major financial institution into insolvency",
        "Exchange hacked: user funds compromised",
        "Market crash: Dow drops 2000 points in single day",
        "Systemic collapse: multiple exchanges halt trading",
    ]
    
    # Reference examples of NON-catastrophes (hypothetical, questions, historical)
    NON_CATASTROPHE_EXAMPLES = [
        "If the next market crash mirrors 2008, here's what could happen",
        "Will the stock market crash in 2026? Analysts weigh in",
        "What if market crashes? How to protect your portfolio",
        "Analyst recalls 2008 Lehman collapse and lessons learned",
        "Could the market crash? Here's what experts think",
        "Market crash analysis: understanding historical patterns",
        "Should you worry about a market crash? Expert opinion",
        "If market crashes, these stocks might survive",
        "Market crash predictions: what analysts are saying",
        "Understanding market crashes: a historical perspective",
    ]
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize catastrophe classifier.
        
        Loads model immediately (eager loading) since this is a critical component.
        Better to fail fast at startup than delay during a catastrophe.
        
        Args:
            model_name: Sentence transformer model to use
        """
        self.model_name = model_name
        
        # Similarity thresholds (tuned for accuracy)
        self.catastrophe_threshold = 0.65  # Min similarity to catastrophe examples
        self.non_catastrophe_threshold = 0.60  # Max similarity to non-catastrophe examples
        
        # Eager loading - load model immediately
        try:
            logger.info(f"Loading sentence transformer model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            
            # Pre-compute embeddings for reference examples
            logger.info("Pre-computing reference embeddings...")
            catastrophe_embeddings = self._model.encode(
                self.CATASTROPHE_EXAMPLES,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            
            non_catastrophe_embeddings = self._model.encode(
                self.NON_CATASTROPHE_EXAMPLES,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            
            # Pre-normalize embeddings for efficient cosine similarity computation
            # Store normalized versions to avoid re-normalizing on every classification
            self._catastrophe_norms = catastrophe_embeddings / np.linalg.norm(
                catastrophe_embeddings, axis=1, keepdims=True
            )
            self._non_catastrophe_norms = non_catastrophe_embeddings / np.linalg.norm(
                non_catastrophe_embeddings, axis=1, keepdims=True
            )
            
            logger.info(
                "Catastrophe classifier ready",
                model=model_name,
                catastrophe_examples=len(self.CATASTROPHE_EXAMPLES),
                non_catastrophe_examples=len(self.NON_CATASTROPHE_EXAMPLES),
            )
            
        except Exception as e:
            logger.error(
                "Failed to initialize catastrophe classifier",
                error=str(e),
                note="Will fallback to keyword matching",
            )
            self._model = None
            self._catastrophe_norms = None
            self._non_catastrophe_norms = None
    
    def is_catastrophe(self, headline: str) -> bool:
        """
        Classify headline as catastrophe or not using semantic similarity.
        
        Args:
            headline: News headline to classify
        
        Returns:
            True if headline is an actual catastrophe event, False otherwise
        """
        if not self._model or self._catastrophe_norms is None:
            # Model failed to load at initialization - return False (fallback to keyword matching)
            logger.debug("Classifier not available, skipping semantic check")
            return False
        
        try:
            # Generate embedding for the headline
            headline_embedding = self._model.encode(
                [headline],
                convert_to_numpy=True,
            )[0].reshape(1, -1)
            
            # Normalize headline embedding for cosine similarity
            headline_norm = headline_embedding / np.linalg.norm(headline_embedding)
            
            # Compute cosine similarity to pre-normalized catastrophe examples
            catastrophe_similarities = np.dot(self._catastrophe_norms, headline_norm.T).flatten()
            max_catastrophe_sim = float(np.max(catastrophe_similarities))
            
            # Compute cosine similarity to pre-normalized non-catastrophe examples
            non_catastrophe_similarities = np.dot(self._non_catastrophe_norms, headline_norm.T).flatten()
            max_non_catastrophe_sim = float(np.max(non_catastrophe_similarities))
            
            # Classification logic:
            # - High similarity to catastrophe examples AND
            # - Low similarity to non-catastrophe examples
            is_catastrophe = (
                max_catastrophe_sim >= self.catastrophe_threshold and
                max_non_catastrophe_sim < self.non_catastrophe_threshold
            )
            
            logger.debug(
                "Catastrophe classification",
                headline=headline[:80],
                catastrophe_sim=round(max_catastrophe_sim, 3),
                non_catastrophe_sim=round(max_non_catastrophe_sim, 3),
                is_catastrophe=is_catastrophe,
            )
            
            return is_catastrophe
            
        except Exception as e:
            logger.error(
                "Error in catastrophe classification",
                headline=headline[:80],
                error=str(e),
            )
            return False  # Fail safe: don't trigger catastrophe on error

