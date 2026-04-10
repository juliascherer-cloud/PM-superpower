"""PM Agent Team — orchestrates Researcher, Writer, and Executor agents.

Architecture
------------
                    ┌──────────────────────────┐
  User Request ────▶│  Orchestrator (Claude)   │
                    │  Adaptive thinking ON    │
                    └───────┬──────────────────┘
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────────┐
        │ Researcher│  │  Writer  │  │   Executor   │
        │ (Claude) │  │ (Claude) │  │  (Claude)    │
        │ +PM tools│  │  writes  │  │ +action tools│
        └──────────┘  └──────────┘  └──────────────┘

Each sub-agent is a separate Claude API call with a specialised system
prompt and a targeted tool set.  The orchestrator decides which agents to
invoke, collects their outputs, and synthesises a final response.
"""

import json

import anthropic

from pm_superpower.config import Config
from pm_superpower.prompts import (
    EXECUTOR_SYSTEM,
    ORCHESTRATOR_SYSTEM,
    RESEARCHER_SYSTEM,
    WRITER_SYSTEM,
)
from pm_superpower.tools import (
    execute_pm_action,
    execute_pm_tool,
    get_pm_action_tools,
    get_pm_query_tools,
)

# ---------------------------------------------------------------------------
# Orchestrator tool schemas (delegates to sub-agents)
# ---------------------------------------------------------------------------

_ORCHESTRATOR_TOOLS = [
    {
        "name": "research",
        "description": (
            "Delegate to the Research Agent to gather information from PM tools "
            "(Linear, Jira, GitHub, Slack, Google Calendar). "
            "Use this whenever you need current data before writing or acting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Specific question or data request — the more precise the better.",
                },
                "tools": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["linear", "jira", "github", "slack", "calendar"],
                    },
                    "description": "Which PM tools to query (choose the most relevant).",
                },
            },
            "required": ["query", "tools"],
        },
    },
    {
        "name": "write",
        "description": (
            "Delegate to the Writer Agent to create a polished PM artifact "
            "(ticket, PRD, status update, meeting notes, announcement, email). "
            "Always pass research results as context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Precisely what to write.",
                },
                "context": {
                    "type": "string",
                    "description": "All relevant context — research data, requirements, constraints.",
                },
                "artifact_type": {
                    "type": "string",
                    "enum": ["ticket", "prd", "status_update", "meeting_notes", "announcement", "email"],
                    "description": "Type of artifact.",
                },
            },
            "required": ["task", "context", "artifact_type"],
        },
    },
    {
        "name": "execute",
        "description": (
            "Delegate to the Executor Agent to take actions in PM tools "
            "(create tickets, schedule meetings, send Slack messages). "
            "Only use when the PM explicitly requests an action."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "What action to take — be specific.",
                },
                "tool": {
                    "type": "string",
                    "enum": ["linear", "jira", "github", "slack", "calendar"],
                    "description": "Which PM tool to act on.",
                },
                "parameters": {
                    "type": "object",
                    "description": "Tool-specific action parameters.",
                },
            },
            "required": ["action", "tool"],
        },
    },
]

_MAX_ORCHESTRATOR_TURNS = 12
_MAX_AGENT_TURNS = 6


class PMTeam:
    """Orchestrates a team of specialised PM agents powered by Claude Opus 4.6."""

    def __init__(self, config: Config) -> None:
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.config = config
        self.model = "claude-opus-4-6"
        # Track which agents were called (for display in the CLI)
        self.agent_calls: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, user_request: str) -> str:
        """Process a PM request using the agent team and return the result."""
        self.agent_calls = []
        messages: list[dict] = [{"role": "user", "content": user_request}]

        for _ in range(_MAX_ORCHESTRATOR_TURNS):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                thinking={"type": "adaptive"},
                system=ORCHESTRATOR_SYSTEM,
                tools=_ORCHESTRATOR_TOOLS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                return self._extract_text(response)

            if response.stop_reason != "tool_use":
                return self._extract_text(response)

            # Dispatch each tool call to the appropriate sub-agent
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self._dispatch(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        return "Task complete."

    # ------------------------------------------------------------------
    # Sub-agent dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, agent: str, params: dict) -> str:
        self.agent_calls.append({"agent": agent, "params": params})
        if agent == "research":
            return self._research(params)
        if agent == "write":
            return self._write(params)
        if agent == "execute":
            return self._execute(params)
        return f"Unknown agent: {agent}"

    # ------------------------------------------------------------------
    # Researcher sub-agent
    # ------------------------------------------------------------------

    def _research(self, params: dict) -> str:
        query = params["query"]
        requested_tools = params.get("tools", ["linear", "jira", "github"])

        # Always include calendar as a free query tool
        if "calendar" not in requested_tools:
            requested_tools = list(requested_tools)

        pm_tools = get_pm_query_tools(requested_tools)
        if not pm_tools:
            return "No PM query tools available. Configure at least one integration."

        messages: list[dict] = [{"role": "user", "content": query}]

        for _ in range(_MAX_AGENT_TURNS):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                system=RESEARCHER_SYSTEM,
                tools=pm_tools,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                return self._extract_text(response)

            if response.stop_reason != "tool_use":
                return self._extract_text(response)

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    data = execute_pm_tool(block.name, block.input, self.config)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": data,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        return "Research complete."

    # ------------------------------------------------------------------
    # Writer sub-agent
    # ------------------------------------------------------------------

    def _write(self, params: dict) -> str:
        task = params["task"]
        context = params.get("context", "")
        artifact_type = params.get("artifact_type", "document")

        prompt = (
            f"Create the following PM artifact:\n\n"
            f"**Task:** {task}\n"
            f"**Artifact type:** {artifact_type}\n\n"
            f"**Context:**\n{context}\n\n"
            "Write a complete, polished artifact that the PM can use immediately."
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=WRITER_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._extract_text(response)

    # ------------------------------------------------------------------
    # Executor sub-agent
    # ------------------------------------------------------------------

    def _execute(self, params: dict) -> str:
        action = params["action"]
        tool = params["tool"]
        parameters = params.get("parameters", {})

        action_tools = get_pm_action_tools([tool])
        if not action_tools:
            return f"No action tools configured for '{tool}'."

        prompt = (
            f"Execute the following PM action:\n\n"
            f"**Action:** {action}\n"
            f"**Tool:** {tool}\n"
            f"**Parameters:**\n```json\n{json.dumps(parameters, indent=2)}\n```\n\n"
            "Please execute this action now."
        )

        messages: list[dict] = [{"role": "user", "content": prompt}]

        for _ in range(_MAX_AGENT_TURNS):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=EXECUTOR_SYSTEM,
                tools=action_tools,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                return self._extract_text(response)

            if response.stop_reason != "tool_use":
                return self._extract_text(response)

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_pm_action(block.name, block.input, self.config)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        return "Action complete."

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text(response) -> str:
        return "\n".join(b.text for b in response.content if b.type == "text")
