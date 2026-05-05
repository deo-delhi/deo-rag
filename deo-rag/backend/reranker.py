import logging
from typing import List, Tuple
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder
from .config import SETTINGS
from .torch_device import preferred_torch_device

logger = logging.getLogger(__name__)

class Reranker:
    def __init__(self, model_name: str = None):
        self.model_name = model_name or SETTINGS.reranker_model
        self.device = preferred_torch_device()
        self.model = None
        
    def _load_model(self):
        if self.model is None:
            logger.info(f"Loading reranker model: {self.model_name} on {self.device}")
            self.model = CrossEncoder(self.model_name, device=self.device)
            
    def rerank(self, query: str, documents: List[Document], top_k: int = 10) -> List[Document]:
        if not documents:
            return []
            
        self._load_model()
        
        # Prepare pairs for cross-encoder
        pairs = [[query, doc.page_content] for doc in documents]
        
        # Predict scores
        scores = self.model.predict(pairs)
        
        # Sort documents by score
        doc_scores = list(zip(documents, scores))
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Return top_k
        return [doc for doc, score in doc_scores[:top_k]]
