from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.tools import tool
from crewai.agents.agent_builder.base_agent import BaseAgent
# from src.flexr.utils.milvus_util import MilvusUtil,SearchResult
from src.flexr.utils.milvus_util import MilvusUtil,SearchResult
from typing import List
from loguru import logger
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

    agents: List[BaseAgent]
    tasks: List[Task]

    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools
    @agent
    def information_retriever(self) -> Agent:
        return Agent(
            config=self.agents_config['information_retriever'], # type: ignore[index]
            verbose=True
        )

    @agent
    def answer_generator(self) -> Agent:
        return Agent(
            config=self.agents_config['answer_generator'], # type: ignore[index]
            verbose=True
        )

    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    @task
    def retrieval_task(self) -> Task:
        return Task(
            config=self.tasks_config['retrieval_task'], # type: ignore[index]
            tools=[self.search_knowledgebase],
            # output_type=List[SearchResult],
            # callback=print_output,
        )

    @task
    def answer_generation_task(self) -> Task:
        return Task(
            config=self.tasks_config['answer_generation_task'], # type: ignore[index]
            context=[self.retrieval_task()],
            # callback=print_output,
            # human_input=True,
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
            
        

    @crew
    def crew(self) -> Crew:
        """Creates the Flexr crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )
