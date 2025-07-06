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
                        metadata={
                            "section_name": doc.metadata.get("section_name"),
                            "page_title": doc.metadata.get("page_title")
                        }
                    ),
                    score
                )
                for doc, score in results
            ]

            logger.debug(f"Search results: {results}")
        except Exception as e:
            logger.exception(f"Error in search: {e}")
            traceback.print_exc()
            return RerankedResults(results=[])
        
        search_results = []
        for doc, score in results:
            search_result = SearchResult(
                content=doc.page_content,
                similarity=score,
                metadata=doc.metadata
            )
            search_results.append(search_result)
            logger.debug(
                f"Samiliary score: {score}; Content: {re.sub(r'\s+', ' ', doc.page_content)}"
            )
        logger.debug(f"{'*' *80 }")
        reranked = self.rerank(query, search_results)
        return RerankedResults(results=reranked)

    # def test_samilarity(self, query, result):
    #     from numpy import dot
    #     from numpy.linalg import norm
    #     query_embedding = self.embedding_function.embed_query(query)
    #     result_embedding = self.embedding_function.embed_query(result)
    #     return dot(query_embedding, result_embedding) / (
    #         norm(query_embedding) * norm(result_embedding)
    #     )

    def rerank(self, query: str, search_results: List[SearchResult], top_n: int = 5) -> List[RerankedResult]:
        try:
            import cohere

            co = cohere.BedrockClientV2(aws_region="ap-northeast-1")

            if not search_results:
                return []

            documents = [result.content for result in search_results]

            rerank_response = co.rerank(
                model="cohere.rerank-v3-5:0",
                query=query,
                documents=documents,  
                top_n=min(top_n, len(documents)),
            )

            reranked_results = []
            if rerank_response and hasattr(rerank_response, "results"):
                for result in rerank_response.results:
                    if not self.is_benchmark:
                        if result.relevance_score < self.threshold:
                            logger.debug(
                                f"Filtered out - Index: {result.index}, "
                                f"Relevance: {result.relevance_score:.3f} < threshold {self.threshold}"
                            )
                            from api.pg_dbutil import PGDBUtil
                            PGDBUtil().save_low_relevance_result(query, result.index, result.relevance_score, search_results[result.index].content)
                            continue

                    if result.index < len(search_results):
                        original_result = search_results[result.index]
                        reranked_result = RerankedResult(
                            original_index=result.index,
                            content=original_result.content,
                            similarity=original_result.similarity,
                            relevance=result.relevance_score,
                            metadata=original_result.metadata
                        )
                        reranked_results.append(reranked_result)
                        logger.debug(
                            f"Accepted - Index: {reranked_result.original_index}, "
                            f"Similarity: {reranked_result.similarity:.3f}, "
                            f"Relevance: {reranked_result.relevance:.3f}; "
                            f"Content: {re.sub(r'\s+',' ', reranked_result.content)}"
                        )

                # logger.info(f"Rerank filtering: {filtered_count} results filtered out, "
                #         f"{len(reranked_results)} results accepted")

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