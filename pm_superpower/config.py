"""Configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    anthropic_api_key: str
    linear_api_key: str | None = None
    jira_base_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None
    slack_bot_token: str | None = None
    github_token: str | None = None

    @classmethod
    def from_env(cls) -> "Config":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required. "
                "Copy .env.example to .env and add your key."
            )
        return cls(
            anthropic_api_key=api_key,
            linear_api_key=os.environ.get("LINEAR_API_KEY"),
            jira_base_url=os.environ.get("JIRA_BASE_URL"),
            jira_email=os.environ.get("JIRA_EMAIL"),
            jira_api_token=os.environ.get("JIRA_API_TOKEN"),
            slack_bot_token=os.environ.get("SLACK_BOT_TOKEN"),
            github_token=os.environ.get("GITHUB_TOKEN"),
        )

    @property
    def available_tools(self) -> list[str]:
        """Return list of connected PM tool integrations."""
        tools = []
        if self.linear_api_key:
            tools.append("linear")
        if self.jira_base_url and self.jira_email and self.jira_api_token:
            tools.append("jira")
        if self.slack_bot_token:
            tools.append("slack")
        if self.github_token:
            tools.append("github")
        return tools
