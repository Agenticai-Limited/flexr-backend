from typing import List
from langchain_aws import BedrockEmbeddings
import boto3
import re
from langchain_core.documents import Document as LangchainDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger
from langchain_milvus import Milvus
from pydantic import BaseModel
from .models import SearchResult, SearchResults, RerankedResult, RerankedResults
import traceback
import os 
from collections import defaultdict


class MilvusUtil:

    threshold = float(os.environ["RERANK_THRESHOLD"])

    metric_type="IP"

    def __init__(self, is_benchmark: bool = False):
        try:
            self.is_benchmark = is_benchmark
            self.embedding_function = BedrockEmbeddings(
                model_id=os.environ["EMBEDDING_MODEL"],
                region_name=os.environ["AWS_REGION_NAME"],
            )

            self.vectorStore = Milvus(
                embedding_function=self.embedding_function,
                collection_name=os.environ["milvus_collection_name"],
                connection_args={"uri": os.environ["milvus_uri"], "token": os.environ["milvus_token"]},
                auto_id=True,
                text_field="text_content",
                index_params={
                    "index_type": "AUTOINDEX",
                    "metric_type": self.metric_type,  # L2 for CV, IP for NLP # test cosine similarity
                },
            )

            self.splitter = RecursiveCharacterTextSplitter(chunk_size=1024, chunk_overlap=200)
            self._test_connection()
        except Exception as e:
            logger.exception(f"Error initializing MilvusUtil: {e}")
            traceback.print_exc()

    def _test_connection(self):
        try:
            self.vectorStore.client.get_server_version() 
            logger.info("Milvus connection test successful.")
            return True
        except Exception as e:
            logger.exception(f"Connection test failed: {e}")
            return False

    def save(self, documents: List[LangchainDocument]):
        doc_chunks= self.splitter.split_documents(documents)
        logger.info(f"save {len(doc_chunks)} rows to milvus")
        return self.vectorStore.add_documents(doc_chunks)

    def insert(self, documents: List[LangchainDocument]):
        for doc in documents:
            if hasattr(doc, "metadata"):
                doc.metadata = {key: value for key, value in doc.metadata.items() if value is not None}

        return self.vectorStore.add_documents(documents)

    def search(self, query: str, top_k: int = 25) -> RerankedResults:
        logger.debug(
            f"{'=' *30 } Query: {query} | Embedding Model: {os.environ["EMBEDDING_MODEL"]} {'='*30}"
        )
        try:
            results = self.vectorStore.similarity_search_with_score(query, k=top_k)
            results = [
                (
                    LangchainDocument(
                        page_content=doc.page_content, # Keep the original text content
                        metadata=doc.metadata
                    )
                )
                for doc in results
            ]

            logger.debug(f"Search results: {results}")
        except Exception as e:
            logger.exception(f"Error in search: {e}")
            traceback.print_exc()
            return RerankedResults(results=[])
        
        reranked = self.rerank(query, results)
        return RerankedResults(results=reranked)

    def search_with_rse(self, query: str) -> RerankedResults:
        """
        Retrieve initial chunks, identify relevant OneNote pages, retrieve all chunks
        for those pages, reconstruct full pages, and then re-rank the full pages.

        This method leverages the structure of OneNote pages (identified by page_id
        and ordered by chunk_id) to provide richer context for LLM generation.

        Args:
            query (str): The user's query.
            top_k (int): The number of top full pages to return after re-ranking.

        Returns:
            RerankedResults: An object containing a list of highly relevant,
                             re-ranked full OneNote pages.
        """
        logger.info(f"Performing RSE {'=' *30 } Query: {query} | Embedding Model: {os.environ["EMBEDDING_MODEL"]} {'='*30}")
        
        # 1. Initial Broad Retrieval: Fetch a large number of chunks to cast a wide net.
        initial_k = 30 
        initial_candidate_chunks_with_scores = self.vectorStore.similarity_search_with_score(
            query, k=initial_k
        )

        # Extract unique page_ids from the initial candidate chunks
        unique_candidate_page_ids = list(set(
            doc.metadata.get("page_id")
            for doc, _ in initial_candidate_chunks_with_scores
            if doc.metadata and doc.metadata.get("page_id")
        ))
        
        if not unique_candidate_page_ids:
            logger.warning(f"No unique OneNote page IDs found in initial broad retrieval for query: '{query}'. Returning empty results.")
            return RerankedResults(results=[])

        logger.info(f"Identified {len(unique_candidate_page_ids)} unique OneNote pages as candidates.")

        # 2. Retrieve All Chunks for Identified Pages in a Single Query
        formatted_page_ids = [f'"{pid}"' for pid in unique_candidate_page_ids]
        filter_expr = f"page_id in [{','.join(formatted_page_ids)}]"

        raw_results = self.vectorStore.client.query(
            collection_name=self.vectorStore.collection_name,
            filter=filter_expr,
            output_fields=["chunk_id", "page_id", "text_content", "section_name", "page_title"],  # Get all fields
            limit=1000  # Assuming no single page has more than 10,000 chunks
        )
        
        if not raw_results:
            logger.warning(f"No chunks found for any identified candidate pages. Returning empty results.")
            return RerankedResults(results=[])

        # 3. Reconstruct Full OneNote Pages (RSE Core Logic)
        page_content_map = defaultdict(list)
        page_metadata_map = {}  # Store metadata of the first chunk per page_id

        for doc in raw_results:
            page_id = doc.get("page_id")
            chunk_id = doc.pop("chunk_id")
            text_content = doc.pop("text_content")

            # Store (chunk_id, page_content) tuples for sorting
            page_content_map[page_id].append((chunk_id, text_content))
            if page_id not in page_metadata_map:
                page_metadata_map[page_id] = doc

        reconstructed_pages: List[LangchainDocument] = []
        for page_id, chunks_data in page_content_map.items():
            # Sort chunks by their `chunk_id` to guarantee the original page order.
            sorted_chunks_data = sorted(chunks_data, key=lambda x: x[0])  # x[0] is chunk_id
            full_page_content = " ".join([content for _, content in sorted_chunks_data])
            page_metadata = page_metadata_map.get(page_id, {})
            
            reconstructed_pages.append(
                LangchainDocument(
                    page_content=full_page_content,
                    metadata=page_metadata
                )
            )

        logger.info(f"Successfully reconstructed {len(reconstructed_pages)} full OneNote pages.")

        # 4. Re-rank the Reconstructed Full Pages
        reranked_final_pages = self.rerank(query, reconstructed_pages)
        logger.info(f"RSE search completed. Returned {len(reranked_final_pages)} re-ranked full OneNote pages.")
        return RerankedResults(results=reranked_final_pages)

    def rerank(self, query: str, search_results: List[LangchainDocument], top_n: int = 5) -> List[RerankedResult]:
        try:
            import cohere

            co = cohere.BedrockClientV2(aws_region="ap-northeast-1")

            if not search_results:
                return []

            documents = [result.page_content for result in search_results]

            rerank_response = co.rerank(
                model="cohere.rerank-v3-5:0",
                query=query,
                documents=documents,
                top_n=min(top_n, len(documents)),
            )

            reranked_results = []
            log_near_threshold_rejections = True
            if rerank_response and hasattr(rerank_response, "results"):
                for result in rerank_response.results:
                    if not self.is_benchmark:
                        if result.relevance_score < self.threshold:
                            if log_near_threshold_rejections:
                                logger.debug(f"The near threshold rejections is: {result.relevance_score} - {search_results[result.index].metadata.get('page_id')}")
                                
                                from api.pg_dbutil import PGDBUtil
                                PGDBUtil().save_low_relevance_result(
                                    query,
                                    result.index,
                                    result.relevance_score,
                                    re.sub(r'\s+',' ', search_results[result.index].page_content),
                                    search_results[result.index].metadata.get('page_id')
                                )
                                
                                log_near_threshold_rejections = False

                            logger.debug(
                                f"Filtered out - Index: {result.index}, "
                                f"Relevance: {result.relevance_score:.3f} < threshold {self.threshold}"
                            )
                            
                            continue

                    if result.index < len(search_results):
                        original_result = search_results[result.index]
                        reranked_result = RerankedResult(
                            original_index=result.index,
                            content=original_result.page_content,
                            relevance=result.relevance_score,
                            metadata=original_result.metadata
                        )
                        reranked_results.append(reranked_result)
                        logger.debug(
                            f"Accepted - Index: {reranked_result.original_index}, "
                            f"Relevance: {reranked_result.relevance:.3f}; "
                            f"Content: {re.sub(r'\s+',' ', reranked_result.content)}"
                        )

                logger.debug(f"Rerank filtering: {len(search_results) - len(reranked_results)} results filtered out, "
                        f"{len(reranked_results)} results accepted")

            return reranked_results

        except Exception as e:
            logger.exception(f"Error in rerank: {e}")
            traceback.print_exc()
            return []

    def _test_search(self, query: str, top_k: int = 15):
        results = self.vectorStore.similarity_search_with_score(query, k=top_k)
        search_results = []
        for doc, score in results:
            search_results.append([score,doc.metadata["page_label"],doc.page_content])
        return search_results
    
    def _test_rerank(self, query: str, results: List[tuple[float, str, str]], top_n: int = 2):
        try:
            import cohere

            co = cohere.BedrockClientV2(aws_region="ap-northeast-1")

            if not results:
                return []

            documents = [result[2] for result in results]

            rerank_response = co.rerank(
                model="cohere.rerank-v3-5:0",
                query=query,
                documents=documents,  
                top_n=min(top_n, len(documents)),
            )

            reranked_results = []
            if rerank_response and hasattr(rerank_response, "results"):
                for result in rerank_response.results:

                    if result.index < len(results):
                        original_result = results[result.index]
                        reranked_result = result.relevance_score, original_result[1], original_result[2]
                        logger.debug(f"Reranked result: {reranked_result}")
                        reranked_results.append(reranked_result)

            return reranked_results

        except Exception as e:
            logger.error(f"Error in rerank: {e}")
            traceback.print_exc()
            return []