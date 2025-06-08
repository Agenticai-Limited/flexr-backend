from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.tools import tool
from crewai.agents.agent_builder.base_agent import BaseAgent
# from src.flexr.utils.milvus_util import MilvusUtil,SearchResult
from src.flexr.utils.milvus_util import MilvusUtil,SearchResult
from typing import List, Any
from loguru import logger
import queue
import json
from crewai.tasks.task_output import TaskOutput
from crewai.project import before_kickoff
from api.event_models import ProgressEvent
from api.pg_dbutil import PGDBUtil, NoResultLog
import os

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
    def before_kickoff(self,input):
        self.input = input
        event = ProgressEvent(
            type="status_update",
            stage="running",
            status="Searching Internal Knowledgebase",
        )
        self.update_task_progress(event)
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
    def answer_generator(self) -> Agent:
        return Agent(
            config=self.agents_config['answer_generator'], # type: ignore[index]
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
            output_type=List[SearchResult],
            callback=self.retrieval_task_callback
        )

    @task
    def answer_generation_task(self) -> Task:
        return Task(
            config=self.tasks_config['answer_generation_task'], # type: ignore[index]
            context=[self.retrieval_task()],
        )

    @tool
    def search_knowledgebase(query: str) -> List[SearchResult] :
        '''
        Search the query, retrieving the most relevant text excerpts or document references from the knowledge base
        Args:
            query (str): The original question asked by the user, do not modify it
        Returns:
            List[SearchResult]: The most relevant document references from the knowledge base, with content,score and metadata
        '''
        logger.debug(f"Searching for: {query}")
        return MilvusUtil().search(query)
    
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

        self.record_no_result_query(output)
        
        start_next_event = ProgressEvent(
            type="status_update",
            stage="running",
            status="Generating Answer",
        )
        self.update_task_progress(start_next_event)
    
    def record_no_result_query(self, output: TaskOutput):
        if not os.environ.get("APP_ENV") == "dev":
            if output.raw == '[]':
                PGDBUtil().save_no_result_query(NoResultLog(query=self.input["query"], username=self.username, task_id=self.task_id))

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
