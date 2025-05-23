import os
from typing import Any

from crewai import Agent, Crew, LLM, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent

MODEL = 'gemini/gemini-2.5-flash-preview-04-17'


class GeminiWithGoogleSearch(LLM):
    """A Gemini-specific LLM that has the 'google_search' tool enabled.
    
    This tool has some quota included on the "free tier" of the API, so you
    can use Google Search as a tool in your app without needing an additional
    service.

    Be sure to read the docs on using the Google Search grounding tool at
    https://ai.google.dev/gemini-api/docs/grounding.
    """

    def __init__(self, model: str | None = None, **kwargs):
       if not model:
          # Use a default Gemini model.
          model = os.getenv('MODEL', 'gemini/gemini-2.5-flash-preview-04-17')

       super().__init__(model, **kwargs)

    def call(
        self,
        messages: str | list[dict[str, str]],
        tools: list[dict] | None = None,
        callbacks: list[Any] | None = None,
        available_functions: dict[str, Any] | None = None,
    ) -> str | Any:
        if not tools:
            tools = []

        # LiteLLM will throw a warning if it sees `google_search`, so use camel case here.
        tools.insert(0, {'googleSearch': {}})

        return super().call(
            messages=messages,
            tools=tools,
            callbacks=callbacks,
            available_functions=available_functions
        )


@CrewBase
class GithubRoaster:
    """GithubRoaster crew"""

    agents: list[BaseAgent]
    tasks: list[Task]

    @agent
    def user_researcher(self) -> Agent:
        gemini_with_search = GeminiWithGoogleSearch(model=MODEL)
        return Agent(
            config=self.agents_config['user_researcher'], # type: ignore[reportAttributeAccessIssue]
            llm=gemini_with_search,
            verbose=True,
        )

    @agent
    def project_researcher(self) -> Agent:
        gemini_with_search = GeminiWithGoogleSearch(model=MODEL)
        return Agent(
            config=self.agents_config['project_researcher'], # type: ignore[reportAttributeAccessIssue]
            llm=gemini_with_search,
            verbose=True,
        )
    
    @agent
    def roast_writer(self) -> Agent:
        return Agent(
            config=self.agents_config['roast_writer'], # type: ignore[reportAttributeAccessIssue]
            verbose=True,
            llm=MODEL,
        )

    @task
    def user_research_task(self) -> Task:
        return Task(
            config=self.tasks_config['user_research_task'], # type: ignore[reportAttributeAccessIssue]
        )

    @task
    def project_research_task(self) -> Task:
        return Task(
            config=self.tasks_config['project_research_task'], # type: ignore[reportAttributeAccessIssue]
        )

    @task
    def roasting_task(self) -> Task:
        return Task(
            config=self.tasks_config['roasting_task'], # type: ignore[reportAttributeAccessIssue]
            # output_file='roast.md'
        )

    @crew
    def crew(self, **kwargs) -> Crew:
        """Creates the GithubRoaster crew"""
        return Crew(
            agents=self.agents,  # type: ignore[reportCallIssue]
            tasks=self.tasks, # type: ignore[reportCallIssue]
            process=Process.sequential,
            verbose=True,
            **kwargs,
        )
