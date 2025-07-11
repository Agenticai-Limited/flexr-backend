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
class RefineQueryCrew():
    """Refine Query Crew"""

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
    def query_optimizer(self) -> Agent:
        return Agent(
            config=self.agents_config['query_optimizer'], # type: ignore[index]
            max_iter=1,
            verbose=True
        )

    @task
    def retrieve_information(self) -> Task:
        search_tool = self.search_knowledgebase
        search_tool.result_as_answer = True
        return Task(
            config=self.tasks_config['retrieve_information'], # type: ignore[index]
            tools=[search_tool],
            max_retries=1,
        )

    @task
    def optimize_query(self) -> Task:
        return Task(
            config=self.tasks_config['optimize_query'], # type: ignore[index]
            verbose=True
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Refine Query Crew"""

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
        )

    @tool
    def search_knowledgebase(query: str) -> str:
        '''
        Search the query, retrieving the relevant text excerpts or document references from the knowledge base
        Args:
            query (str): The original question asked by the user, do not modify it
        Returns:
            str: A JSON string representing the reranked results. The format is as follows:
             [
                {
                    "metadata": {
                    "page_label": "string",
                    "file_name": "string",
                    "pk": "integer"
                    },
                    "page_content": "string"
                }
             ]
        '''
        logger.info(f"Searching for: {query}")
        results = MilvusUtil().search(query)
        logger.info(f"Results: {results}")
        return [item.model_dump_json() for item,score in results]
    