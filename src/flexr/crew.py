from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.tools import tool
from crewai.agents.agent_builder.base_agent import BaseAgent
from src.flexr.utils.milvus_util import MilvusUtil,RerankedResults
from typing import List, Any
from loguru import logger
import queue
import json
from crewai.tasks.task_output import TaskOutput
from crewai.project import before_kickoff
from api.event_models import ProgressEvent
from api.pg_dbutil import PGDBUtil, NoResultLog
import os
from src.flexr.utils.schemas import AgentOutput

# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

# import panel as pn

# chat_interface = pn.chat.ChatInterface()

# from crewai.tasks.task_output import TaskOutput

# def print_output(output: TaskOutput):

#     message = output.raw
#     chat_interface.send(message, user=output.agent, respond=False)


@CrewBase
class Flexr():
    """Flexr crew"""

    @before_kickoff
    def before_kickoff(self,input: dict):
        self.input = input
        event = ProgressEvent(
            type="status_update",
            stage="running",
            status="Searching Internal Knowledgebase",
        )
        self.update_task_progress(event)
        logger.debug(f"Searching for: {input['query']} from {self.task_id}")
        return input
        

    agents: List[BaseAgent]
    tasks: List[Task]

    @agent
    def information_retriever(self) -> Agent:
        return Agent(
            config=self.agents_config['information_retriever'], # type: ignore[index]
            max_iter=1,
            verbose=True
        )

    @agent
    def content_structuring_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['content_structuring_agent'], # type: ignore[index]
            llm=os.environ["CONTENT_STRUCTURING_MODEL"],
            verbose=True
        )
    
    @agent
    def markdown_rendering_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['markdown_rendering_agent'], # type: ignore[index]
            llm=os.environ["MARKDOWN_RENDERING_MODEL"],
            verbose=True
        )

    @task
    def retrieval_task(self) -> Task:
        search_tool = self.search_knowledgebase
        search_tool.result_as_answer = True
        
        return Task(
            config=self.tasks_config["retrieval_task"],  # type: ignore[index]
            tools=[search_tool],
            max_retries=1,
            output_pydantic=RerankedResults,
            callback=self.retrieval_task_callback
        )

    @task
    def structure_content_task(self) -> Task:
        return Task(
            config=self.tasks_config['structure_content_task'], # type: ignore[index]
            context=[self.retrieval_task()],
            output_pydantic=AgentOutput,
            callback=self.structure_content_task_callback
        )

    @task
    def render_markdown_task(self) -> Task:
        return Task(
            config=self.tasks_config['render_markdown_task'], # type: ignore[index]
            context=[self.structure_content_task()],
        )

    @tool
    def search_knowledgebase(query: str) -> str :
        '''
        Search the query, retrieving the most relevant text excerpts or document references from the knowledge base
        Args:
            query (str): The original question asked by the user, do not modify it
        Returns:
            str: A JSON string representing the reranked results. The format is as follows:
             {
               "results": [
                 {
                   "original_index": int,
                   "content": str,
                   "relevance": float,
                   "metadata": {
                     "file_name": str,
                     "pk": int,
                     "page_label": str
                   }
                 },
                 ...
               ]
             }
        '''
        search_results:RerankedResults = MilvusUtil().search_with_rse(query)
        return search_results.model_dump_json()
    
    def update_task_progress(self, event: ProgressEvent):
        if self.queue:
            self.queue.put(event.to_sse_format())

    def retrieval_task_callback(self, output: TaskOutput):
        done_event = ProgressEvent(
            type="status_update",
            stage="running",
            status="Searching Internal Knowledgebase Done",
        )
        self.update_task_progress(done_event)

        logger.debug(f"retrieval_task_callback for{'*'*100}")

        self.record_query_results(output)
        
        start_next_event = ProgressEvent(
            type="status_update",
            stage="running",
            status="Summarizing Results",
        )
        self.update_task_progress(start_next_event)
    
    def structure_content_task_callback(self, output: TaskOutput):
        done_event = ProgressEvent(
            type="status_update",
            stage="running",
            status="Summarizing Results Done",
        )
        self.update_task_progress(done_event)
        
        start_next_event = ProgressEvent(
            type="status_update",
            stage="running",
            status="Rendering Answer",
        )
        self.update_task_progress(start_next_event)
    
    def record_query_results(self, output: TaskOutput):
        if not os.environ.get("APP_ENV") == "dev":
            if len(output.pydantic.results) == 0:
                PGDBUtil().save_no_result_query(NoResultLog(query=self.input["query"], task_id=self.task_id))
            else:
                PGDBUtil().save_reranked_results(task_id=self.task_id, results=output.pydantic.results)

    @crew
    def crew(self, task_id: str, q: queue.Queue, username: str) -> Crew:
        """Creates the Flexr crew"""
        self.task_id = task_id
        self.queue = q
        self.username = username
        # self.retrieval_task().callback = lambda output: self.update_task_progress(output, retrieval_task_data)

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
        )
