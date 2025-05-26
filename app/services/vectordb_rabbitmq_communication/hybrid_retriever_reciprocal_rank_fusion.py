#!/usr/bin/env python3
import os
import sys
import logging
import numpy as np
import re
from typing import Dict, Any, List, Optional

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Implements hybrid retrieval combining vector similarity and BM25-style
    keyword matching with support for Anthropic's Contextual Retrieval.
    """

    def __init__(self, scope_manager, project_name, vector_weight=0.7, enable_contextual=True,
                 use_rrf=False, rrf_k=60):
        """
        Initialize the hybrid retriever.

        Args:
            scope_manager: ScopeCollectionsManager instance
            project_name: Project name for collection
            vector_weight: Weight for vector similarity (1-weight for keywords)
            enable_contextual: Whether to use contextual retrieval techniques
            use_rrf: Whether to use Reciprocal Rank Fusion
            rrf_k: Constant used in RRF formula (default: 60)
        """
        self.scope_manager = scope_manager
        self.project_name = project_name
        self.vector_weight = vector_weight
        self.enable_contextual = enable_contextual
        self.use_rrf = use_rrf  # RRF parameter
        self.rrf_k = rrf_k  # RRF constant parameter

        # Try to get collection
        try:
            self.collection_name = f"{project_name}_pdf_content"
            self.collection = scope_manager.client.get_collection(
                name=self.collection_name,
                embedding_function=scope_manager.openai_ef
            )
        except Exception:
            # Try to find any collections for this project
            collections = scope_manager.client.list_collections()
            project_collections = [c for c in collections if c.startswith(f"{project_name}_")]

            if not project_collections:
                raise ValueError(f"No collections found for project: {project_name}")

            self.collection_name = project_collections[0]
            self.collection = scope_manager.client.get_collection(
                name=self.collection_name,
                embedding_function=scope_manager.openai_ef
            )

        # Initialize BM25 parameters for keyword search
        self.k1 = 1.5  # Term saturation parameter
        self.b = 0.75  # Length normalization parameter

        # Import the formatter here to avoid circular imports
        from app.utils.content_formatter import formatter
        self.formatter = formatter

        # Initialize stop words for better keyword search
        self.stop_words = self._initialize_stop_words()

    def _initialize_stop_words(self):
        """Initialize stop words using NLTK if available."""
        try:
            # Try using NLTK stopwords
            from nltk.corpus import stopwords
            try:
                return set(stopwords.words('english'))
            except LookupError:
                # If stopwords not downloaded, try to download them
                import nltk
                try:
                    logger.info("Downloading NLTK stopwords")
                    nltk.download('stopwords', quiet=True)
                    return set(stopwords.words('english'))
                except Exception as e:
                    logger.warning(f"Failed to download NLTK stopwords: {e}")
                    # Fall back to basic stop words
                    return self._get_basic_stop_words()
        except ImportError:
            logger.warning("NLTK not available, using basic stop words list")
            return self._get_basic_stop_words()

    def _get_basic_stop_words(self):
        """Return a basic set of English stop words if NLTK is not available."""
        return set([
            'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'what',
            'which', 'this', 'that', 'these', 'those', 'then', 'just', 'so', 'than', 'such',
            'when', 'who', 'how', 'where', 'why', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'can',
            'could', 'should', 'would', 'shall', 'will', 'may', 'might', 'must', 'to', 'in',
            'on', 'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through',
            'during', 'before', 'after', 'above', 'below', 'from', 'up', 'down', 'of'
        ])

    # Add a new Contextual BM25 implementation
    def _calculate_contextual_keyword_scores(self, query, documents, doc_ids, contexts=None):
        """
        Calculate keyword-based relevance scores using Contextual BM25 approach.

        Args:
            query: User query
            documents: List of document text chunks
            doc_ids: List of document IDs corresponding to the documents
            contexts: Optional list of contextual information for each document

        Returns:
            Dictionary mapping document IDs to relevance scores
        """
        # Tokenize query (with stop word removal)
        query_terms = self._tokenize(query)
        query_terms = [term for term in query_terms if term not in self.stop_words]

        # If no terms left after stop word removal, use original terms
        if not query_terms:
            logger.warning("No terms left after stop word removal, using original query")
            query_terms = self._tokenize(query)

        doc_tokens = [self._tokenize(doc) for doc in documents]

        # If we have contextual information, add it to the tokens
        if contexts and self.enable_contextual:
            context_tokens = [self._tokenize(ctx) if ctx else [] for ctx in contexts]
            # Combine document tokens with context tokens, giving more weight to document tokens
            doc_tokens = [doc_tok + ctx_tok for doc_tok, ctx_tok in zip(doc_tokens, context_tokens)]

        # Calculate document frequencies
        doc_freq = {}
        for term in set(query_terms):
            doc_freq[term] = sum(1 for tokens in doc_tokens if term in tokens)

        # Calculate average document length
        avg_doc_len = sum(len(tokens) for tokens in doc_tokens) / len(doc_tokens) if doc_tokens else 0

        # Calculate BM25 scores
        scores = {}
        for i, tokens in enumerate(doc_tokens):
            score = 0
            doc_len = len(tokens)

            # Count term frequencies in this document
            term_freq = {}
            for term in tokens:
                term_freq[term] = term_freq.get(term, 0) + 1

            # Calculate score for each query term
            for term in query_terms:
                if term in term_freq and term in doc_freq and doc_freq[term] > 0:
                    tf = term_freq[term]
                    idf = max(0, np.log((len(documents) - doc_freq[term] + 0.5) /
                                        (doc_freq[term] + 0.5)))

                    # BM25 formula
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / avg_doc_len)
                    score += idf * numerator / denominator

            scores[doc_ids[i]] = score

        return scores

    # Updated HybridRetriever.retrieve method with RRF support and fixed distance calculation
    def retrieve(self, query, top_k=5):
        logger.info(f"HybridRetriever.retrieve called with query: '{query}', RRF: {self.use_rrf}")

        # Get all chunks
        logger.info("Calling collection.get()")
        all_chunks = self.collection.get()
        logger.info(f"Received {len(all_chunks.get('documents', []))} documents from get()")

        # Vector search
        logger.info(f"Calling collection.query() with query: '{query}'")
        vector_results = self.collection.query(
            query_texts=[query],
            n_results=max(1, min(top_k * 2, len(all_chunks["documents"])))
        )
        logger.info(f"Received vector results with {len(vector_results.get('ids', [[]])[0])} items")

        # Extract contexts from metadata if available (for contextual retrieval)
        contexts = None
        if self.enable_contextual and "metadatas" in all_chunks and all_chunks["metadatas"]:
            contexts = [m.get("context", "") for m in all_chunks["metadatas"]] if all_chunks["metadatas"] else None

        # Calculate keyword relevance scores for all chunks using contextual BM25 if available
        if self.enable_contextual and contexts:
            keyword_scores = self._calculate_contextual_keyword_scores(
                query, all_chunks["documents"], all_chunks["ids"], contexts
            )
        else:
            keyword_scores = self._calculate_keyword_scores(query, all_chunks["documents"], all_chunks["ids"])

        # Get document IDs and distances from vector search and store similarities
        # This is done for both weighted and RRF methods
        vector_ids = vector_results["ids"][0] if vector_results["ids"] and vector_results["ids"][0] else []
        vector_distances = vector_results["distances"][0] if vector_results["distances"] and \
                                                             vector_results["distances"][0] else []

        # Convert distances to similarity scores (1 - distance)
        vector_similarities = [1 - dist for dist in vector_distances]

        # Create map of ID to vector similarity - do this regardless of method
        id_to_vector_sim = {id_val: sim for id_val, sim in zip(vector_ids, vector_similarities)}

        # Create map of ID to document and metadata
        id_to_doc = {}
        id_to_metadata = {}

        for i, id_val in enumerate(all_chunks["ids"]):
            id_to_doc[id_val] = all_chunks["documents"][i]
            id_to_metadata[id_val] = all_chunks["metadatas"][i] if all_chunks["metadatas"] else {}

        # Get document summary from metadata if available
        document_summary = None
        for metadata in all_chunks["metadatas"]:
            if metadata and "document_summary" in metadata:
                document_summary = metadata["document_summary"]
                break

        # Determine which method to use (RRF or Weighted)
        combined_scores = {}

        if self.use_rrf:
            # --- RECIPROCAL RANK FUSION APPROACH ---
            logger.info("Using Reciprocal Rank Fusion to combine results")

            # Create ranked lists
            vector_ranks = {id_val: rank for rank, id_val in enumerate(vector_ids)}

            # Sort keyword scores and create ranks
            keyword_ranked_ids = sorted(
                keyword_scores.keys(),
                key=lambda x: keyword_scores[x],
                reverse=True
            )[:top_k * 2]
            keyword_ranks = {id_val: rank for rank, id_val in enumerate(keyword_ranked_ids)}

            # Calculate RRF scores
            all_ids = set(vector_ranks.keys()) | set(keyword_ranks.keys())

            for id_val in all_ids:
                # Default to a high rank if not in the list (worse than last place)
                v_rank = vector_ranks.get(id_val, len(all_chunks["ids"]))
                k_rank = keyword_ranks.get(id_val, len(all_chunks["ids"]))

                # RRF formula: 1/(rank + k)
                combined_scores[id_val] = (1 / (v_rank + self.rrf_k)) + (1 / (k_rank + self.rrf_k))

            logger.info(f"RRF scores computed for {len(combined_scores)} documents")
        else:
            # --- WEIGHTED APPROACH (Original method) ---
            logger.info("Using weighted approach to combine results")

            # Normalize vector similarities to 0-1 range
            if vector_similarities:
                max_sim = max(vector_similarities)
                min_sim = min(vector_similarities)
                range_sim = max_sim - min_sim
                if range_sim > 0:
                    normalized_vector_similarities = [(sim - min_sim) / range_sim for sim in vector_similarities]
                    # Update id_to_vector_sim with normalized values for weighted scoring
                    id_to_vector_sim = {id_val: sim for id_val, sim in zip(vector_ids, normalized_vector_similarities)}

            # First add vector results
            for id_val in vector_ids:
                vector_sim = id_to_vector_sim.get(id_val, 0)
                keyword_score = keyword_scores.get(id_val, 0)

                # Normalize keyword score to 0-1 range
                norm_keyword_score = min(1.0, keyword_score / 10.0) if keyword_score > 0 else 0

                # Combine scores with weighting
                combined_scores[id_val] = (
                        self.vector_weight * vector_sim +
                        (1 - self.vector_weight) * norm_keyword_score
                )

            # Add any high keyword matches that weren't in vector results
            for id_val, score in keyword_scores.items():
                if id_val not in combined_scores and score > 5:  # Threshold for keyword-only inclusion
                    norm_score = min(1.0, score / 10.0)
                    combined_scores[id_val] = (1 - self.vector_weight) * norm_score

            logger.info(f"Weighted scores computed for {len(combined_scores)} documents")

        # Sort by combined score and get top results
        top_ids = sorted(combined_scores.keys(),
                         key=lambda x: combined_scores[x],
                         reverse=True)[:top_k]

        # Create normalized distances based on combined scores
        # (so distance values match the ranking order)
        normalized_distances = {}
        if combined_scores:
            max_score = max(combined_scores.values())
            min_score = min(combined_scores.values())
            range_score = max_score - min_score

            if range_score > 0:
                for id_val in combined_scores:
                    # Convert combined score to distance (1 - normalized score)
                    # This makes lower distance = better match
                    normalized_score = (combined_scores[id_val] - min_score) / range_score
                    normalized_distances[id_val] = 1 - normalized_score
            else:
                # If all scores are the same, use default distance
                for id_val in combined_scores:
                    normalized_distances[id_val] = 0.5

        # Store the original vector distances for reference
        original_distances = {}
        for id_val, dist in zip(vector_ids, vector_distances):
            original_distances[id_val] = dist

        # Format results
        processed_results = []
        for id_val in top_ids:
            if id_val in id_to_doc:
                # Clean the document text
                raw_text = id_to_doc[id_val]
                cleaned_text = self.formatter.clean_text_content(raw_text)

                # Get metadata
                metadata = id_to_metadata.get(id_val, {})

                # Add page reference to beginning of text if available - prioritize page_number
                page_num = metadata.get("page_number", metadata.get("chunk_index", None))
                if page_num is not None:
                    cleaned_text = f"[Page {page_num}] {cleaned_text}"

                # Get PDF filename from metadata
                pdf_filename = metadata.get("pdf_filename", "Unknown")

                # Include context in results if available
                context = metadata.get("context", "") if self.enable_contextual else ""

                # Get actual vector similarity (now correctly preserved for RRF too)
                vector_sim = id_to_vector_sim.get(id_val, 0)

                processed_results.append({
                    "text": cleaned_text,
                    "metadata": metadata,
                    "distance": normalized_distances.get(id_val, 0.5),  # Use combined-score based distance
                    "keyword_score": keyword_scores.get(id_val, 0),
                    "combined_score": combined_scores[id_val],
                    "id": id_val,
                    "filename": pdf_filename,  # Add filename for consistency with standard search
                    "pdf_filename": pdf_filename,  # Keep pdf_filename for backward compatibility
                    "context": context,  # Add context if available
                    "retrieval_method": "rrf" if self.use_rrf else "weighted"
                })

        return {
            "status": "success",
            "query": query,
            "results": processed_results,
            "document_summary": document_summary,
            "collection": self.collection_name,
            "count": len(processed_results),
            "contextual_retrieval": self.enable_contextual,
            "retrieval_method": "rrf" if self.use_rrf else "weighted",
            "rrf_k": self.rrf_k if self.use_rrf else None,
            "vector_weight": self.vector_weight if not self.use_rrf else None
        }

    def _calculate_keyword_scores(self, query, documents, doc_ids):
        """
        Calculate keyword-based relevance scores using BM25-inspired approach.

        Args:
            query: User query
            documents: List of document text chunks
            doc_ids: List of document IDs corresponding to the documents

        Returns:
            Dictionary mapping document IDs to relevance scores
        """
        # Tokenize query (with stop word removal)
        query_terms = self._tokenize(query)
        query_terms = [term for term in query_terms if term not in self.stop_words]

        # If no terms left after stop word removal, use original terms
        if not query_terms:
            logger.warning("No terms left after stop word removal, using original query")
            query_terms = self._tokenize(query)

        doc_tokens = [self._tokenize(doc) for doc in documents]

        # Calculate document frequencies
        doc_freq = {}
        for term in set(query_terms):
            doc_freq[term] = sum(1 for tokens in doc_tokens if term in tokens)

        # Calculate average document length
        avg_doc_len = sum(len(tokens) for tokens in doc_tokens) / len(doc_tokens) if doc_tokens else 0

        # Calculate BM25 scores
        scores = {}
        for i, tokens in enumerate(doc_tokens):
            score = 0
            doc_len = len(tokens)

            # Count term frequencies in this document
            term_freq = {}
            for term in tokens:
                term_freq[term] = term_freq.get(term, 0) + 1

            # Calculate score for each query term
            for term in query_terms:
                if term in term_freq and term in doc_freq and doc_freq[term] > 0:
                    tf = term_freq[term]
                    idf = max(0, np.log((len(documents) - doc_freq[term] + 0.5) /
                                        (doc_freq[term] + 0.5)))

                    # BM25 formula
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / avg_doc_len)
                    score += idf * numerator / denominator

            scores[doc_ids[i]] = score

        return scores

    def _tokenize(self, text):
        """
        Tokenize text for keyword search.

        Args:
            text: Text to tokenize

        Returns:
            List of tokens
        """
        # Simple whitespace and punctuation-based tokenization
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens