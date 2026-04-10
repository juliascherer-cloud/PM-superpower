"""MCP server — exposes PM Superpower as tools usable in Claude.ai chat.

Usage
-----
1. Install: pip install -e ".[mcp]"
2. Run server: pm-mcp   (or: python -m pm_superpower.mcp_server)
3. Add to Claude config (see README):
   {
     "mcpServers": {
       "pm-superpower": {
         "command": "pm-mcp",
         "env": { "ANTHROPIC_API_KEY": "sk-ant-..." }
       }
     }
   }

Once connected, Claude's chat interface will show PM Superpower tools that
let you ask PM questions, generate standups, write tickets, analyse metrics,
and more — all driven by the agent team under the hood.
"""

import sys

from mcp.server.fastmcp import FastMCP

from pm_superpower.config import Config
from pm_superpower.team import PMTeam

mcp = FastMCP(
    "PM Superpower",
    instructions=(
        "PM Superpower is an AI team for product managers. "
        "Use these tools to generate standups, write tickets, analyse metrics, "
        "get project status updates, and answer PM questions. "
        "Each tool delegates to a team of Claude agents (Researcher, Analyst, Writer, Executor) "
        "that pull real data from Linear, Jira, GitHub, Slack, and Calendar."
    ),
)


def _get_team() -> PMTeam | None:
    try:
        config = Config.from_env()
        return PMTeam(config)
    except ValueError as exc:
        return None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def ask_pm(request: str) -> str:
    """Ask the PM agent team anything.

    Examples:
    - "What's blocking the mobile launch?"
    - "Summarise what engineering shipped last week"
    - "Who owns the auth integration?"
    """
    team = _get_team()
    if team is None:
        return "Error: ANTHROPIC_API_KEY not configured. Set it in your environment."
    return team.run(request)


@mcp.tool()
def generate_standup() -> str:
    """Generate today's standup update from your PM tools.

    Pulls recent activity from Linear/Jira/GitHub/Slack and formats it as:
    what was completed yesterday, what's in progress today, and any blockers.
    """
    team = _get_team()
    if team is None:
        return "Error: ANTHROPIC_API_KEY not configured."
    return team.run(
        "Generate my daily standup update. Pull recent activity from my PM tools "
        "and format it as: what I completed yesterday, what I'm working on today, "
        "and any blockers I need to flag."
    )


@mcp.tool()
def write_ticket(description: str, tool: str = "") -> str:
    """Write a complete, production-ready ticket from a description.

    Args:
        description: What the ticket is about (e.g. "Auth fails for SSO users on mobile")
        tool: Optional — create in "linear" or "jira" (leave empty to just write the ticket)
    """
    team = _get_team()
    if team is None:
        return "Error: ANTHROPIC_API_KEY not configured."
    tool_clause = f" Create it in {tool.capitalize()}." if tool else ""
    request = (
        f"Write a complete, production-ready ticket for: {description}.{tool_clause} "
        "Search Slack and existing issues for any relevant context first."
    )
    return team.run(request)


@mcp.tool()
def project_status(project_name: str) -> str:
    """Generate a project status update.

    Args:
        project_name: Name of the project (e.g. "Q3 mobile launch", "payments team")
    """
    team = _get_team()
    if team is None:
        return "Error: ANTHROPIC_API_KEY not configured."
    return team.run(
        f"Create a status update for '{project_name}'. "
        "Pull recent activity, issues, and PRs from the relevant tools. "
        "Include: overall status, recent wins, what's in flight, blockers/risks, and next milestones."
    )


@mcp.tool()
def analyse_metrics(question: str) -> str:
    """Analyse product and engineering metrics, surface trends, and get actionable insights.

    Args:
        question: What you want to understand (e.g. "How is conversion trending this month?",
                  "What's our sprint velocity been over the last 6 sprints?",
                  "Why might churn be increasing?")
    """
    team = _get_team()
    if team is None:
        return "Error: ANTHROPIC_API_KEY not configured."
    return team.run(question)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
