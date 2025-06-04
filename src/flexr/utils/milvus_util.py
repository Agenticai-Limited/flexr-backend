from typing import List
from langchain_aws import BedrockEmbeddings
import boto3
import re
from langchain_core.documents import Document as LangchainDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger
from langchain_milvus import Milvus
from pydantic import BaseModel
import traceback
import os 

class SearchResult(BaseModel):
    content: str
    similarity: float
    metadata: dict


class MilvusUtil:

    threshold = 0.5

    metric_type="IP"

    def __init__(self):
        try:
            
            self.embedding_function = BedrockEmbeddings(
                model_id=os.environ["EMBEDDING_MODEL"],
                region_name=os.environ["AWS_REGION_NAME"],
            )

            self.vectorStore = Milvus(
                embedding_function=self.embedding_function,
                collection_name=os.environ["milvus_collection_name"],
                connection_args={"uri": os.environ["milvus_uri"], "token": os.environ["milvus_token"]},
                auto_id=True,
                index_params={
                    "index_type": "AUTOINDEX",
                    "metric_type": self.metric_type,  # L2 for CV, IP for NLP
                },
            )

            self.splitter = RecursiveCharacterTextSplitter(chunk_size=1024, chunk_overlap=200)
            self._test_connection()
        except Exception as e:
            logger.error(f"Error initializing MilvusUtil: {e}")
            traceback.print_exc()

    def _test_connection(self):
        try:
            self.vectorStore.client.get_server_version() 
            logger.info("Milvus connection test successful.")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
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

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        logger.debug(
            f"{'=' *30 } Query: {query} | Embedding Model: {os.environ["EMBEDDING_MODEL"]} {'='*30}"
        )
        results = self.vectorStore.similarity_search_with_score(query, k=top_k)
        search_results = []
        for doc, score in results:
            search_result = SearchResult(
                content=doc.page_content,
                similarity=score,
                metadata=doc.metadata
            )
            search_results.append(search_result)
            logger.debug(
                f"Samiliary: {self.test_samilarity(query,search_result.content)}, Score: {score}; Content: {re.sub(r'\s+', ' ', doc.page_content)}"
            )
        logger.debug(f"{'*' *80 }")
        reranked = self.rerank(query, search_results)
        return reranked

    def test_samilarity(self, query, result):
        from numpy import dot
        from numpy.linalg import norm
        query_embedding = self.embedding_function.embed_query(query)
        result_embedding = self.embedding_function.embed_query(result)
        return dot(query_embedding, result_embedding) / (
            norm(query_embedding) * norm(result_embedding)
        )

    def rerank(self, query: str, search_results: List[SearchResult], top_n: int = 4) -> List[SearchResult]:
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
                filtered_count = 0
                for result in rerank_response.results:
                    if result.relevance_score < self.threshold:
                        filtered_count += 1
                        logger.debug(
                            f"Filtered out - Index: {result.index}, "
                            f"Score: {result.relevance_score:.3f} < threshold {self.threshold}"
                        )
                        continue

                    if result.index < len(search_results):
                        original_result = search_results[result.index]
                        reranked_result = SearchResult(
                            content=original_result.content,
                            similarity=result.relevance_score, 
                            metadata=original_result.metadata
                        )
                        reranked_results.append(reranked_result)
                        logger.debug(
                            f"Accepted - Index: {result.index}, "
                            f"Score: {result.relevance_score:.3f}; "
                            f"Content: {re.sub(r'\s+',' ', original_result.content)}"
                        )

                logger.info(f"Rerank filtering: {filtered_count} results filtered out, "
                        f"{len(reranked_results)} results accepted")

            return reranked_results

        except Exception as e:
            logger.error(f"Error in rerank: {e}")
            traceback.print_exc()
            return search_results
