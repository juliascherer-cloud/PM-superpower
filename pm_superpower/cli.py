"""CLI interface for PM Superpower."""

import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table
from rich.theme import Theme

from pm_superpower.config import Config
from pm_superpower.team import PMTeam

_THEME = Theme({
    "info": "bold cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "dim": "dim white",
    "agent": "bold magenta",
})

console = Console(theme=_THEME)

_BANNER = """[bold cyan]
  ██████╗ ███╗   ███╗    ███████╗██╗   ██╗██████╗ ███████╗██████╗ ██████╗  ██████╗ ██╗    ██╗███████╗██████╗
  ██╔══██╗████╗ ████║    ██╔════╝██║   ██║██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔═══██╗██║    ██║██╔════╝██╔══██╗
  ██████╔╝██╔████╔██║    ███████╗██║   ██║██████╔╝█████╗  ██████╔╝██████╔╝██║   ██║██║ █╗ ██║█████╗  ██████╔╝
  ██╔═══╝ ██║╚██╔╝██║    ╚════██║██║   ██║██╔═══╝ ██╔══╝  ██╔══██╗██╔═══╝ ██║   ██║██║███╗██║██╔══╝  ██╔══██╗
  ██║     ██║ ╚═╝ ██║    ███████║╚██████╔╝██║     ███████╗██║  ██║██║     ╚██████╔╝╚███╔███╔╝███████╗██║  ██║
  ╚═╝     ╚═╝     ╚═╝    ╚══════╝ ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝      ╚═════╝  ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝[/bold cyan]
[dim]  Powered by Claude Agent Teams (claude-opus-4-6)[/dim]
"""

_COMPACT_BANNER = "[bold cyan]PM Superpower[/bold cyan] [dim]— powered by Claude Agent Teams[/dim]"

_EXAMPLES = [
    ("standup", "Generate my standup for today"),
    ("ticket",  "Write a ticket for the auth bug Carol mentioned in Slack"),
    ("status",  "Create a Q3 status update for the payments team"),
    ("ask",     "What's blocking the mobile launch?"),
    ("ask",     "Summarise what engineering shipped last week"),
]


def _load_config() -> Config | None:
    try:
        return Config.from_env()
    except ValueError as exc:
        console.print(f"[error]Configuration error:[/error] {exc}")
        console.print(
            "[dim]Tip: copy [bold].env.example[/bold] to [bold].env[/bold] "
            "and add your ANTHROPIC_API_KEY[/dim]"
        )
        return None


def _show_tools(config: Config) -> None:
    if config.available_tools:
        console.print(f"[success]Connected:[/success] {', '.join(config.available_tools)}")
    else:
        console.print(
            "[warning]Demo mode[/warning] [dim]— no PM tools connected. "
            "Add API keys to .env for real data.[/dim]"
        )


def _run_request(request: str, config: Config, quiet: bool = False) -> None:
    """Send a request to the PM team and print the result."""
    team = PMTeam(config)

    if not quiet:
        console.print(f"\n[dim]Request:[/dim] {request}\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("[cyan]Agent team working…", total=None)
        result = team.run(request)
        progress.update(task, description="[green]Done!")

    # Show which agents were called
    if team.agent_calls and not quiet:
        agents_used = list({c["agent"] for c in team.agent_calls})
        console.print(
            f"[dim]Agents used: {', '.join(f'[agent]{a}[/agent]' for a in agents_used)}[/dim]\n"
        )

    console.print(
        Panel(
            Markdown(result),
            title="[bold green]PM Superpower[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def cli(ctx: click.Context) -> None:
    """PM Superpower — AI-powered PM assistant using Claude agent teams.

    Run without arguments to start an interactive chat session.
    """
    if ctx.invoked_subcommand is None:
        _interactive()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("request", nargs=-1, required=False)
def ask(request: tuple[str, ...]) -> None:
    """Ask the PM team anything.

    Examples:

      pm ask "What's blocking the mobile launch?"

      pm ask "Summarise what engineering shipped last week"
    """
    config = _load_config()
    if not config:
        sys.exit(1)

    text = " ".join(request).strip() if request else Prompt.ask("[cyan]What do you need help with?[/cyan]")
    if not text:
        return

    console.print(_COMPACT_BANNER)
    _show_tools(config)
    _run_request(text, config)


@cli.command()
def standup() -> None:
    """Generate today's standup update from your PM tools."""
    config = _load_config()
    if not config:
        sys.exit(1)

    console.print(_COMPACT_BANNER)
    _show_tools(config)
    _run_request(
        "Generate my daily standup update. Pull recent activity from my PM tools "
        "and format it as: what I completed yesterday, what I'm working on today, "
        "and any blockers I need to flag.",
        config,
    )


@cli.command()
@click.argument("description", nargs=-1, required=False)
@click.option("--tool", "-t", type=click.Choice(["linear", "jira"]), default=None,
              help="Create the ticket in Linear or Jira")
def ticket(description: tuple[str, ...], tool: str | None) -> None:
    """Write a well-structured ticket from a description.

    Examples:

      pm ticket "Auth fails for SSO users on mobile"

      pm ticket --tool linear "Add dark mode to the dashboard"
    """
    config = _load_config()
    if not config:
        sys.exit(1)

    text = " ".join(description).strip() if description else Prompt.ask("[cyan]Describe the ticket[/cyan]")
    if not text:
        return

    tool_clause = f" Create it in {tool.capitalize()}." if tool else ""
    request = (
        f"Write a complete, production-ready ticket for: {text}.{tool_clause} "
        "Search Slack and existing issues for any relevant context first."
    )

    console.print(_COMPACT_BANNER)
    _show_tools(config)
    _run_request(request, config)


@cli.command()
@click.argument("project", nargs=-1, required=False)
def status(project: tuple[str, ...]) -> None:
    """Generate a project status update.

    Examples:

      pm status "payments team"

      pm status "Q3 mobile launch"
    """
    config = _load_config()
    if not config:
        sys.exit(1)

    project_name = " ".join(project).strip() if project else Prompt.ask("[cyan]Which project?[/cyan]")
    if not project_name:
        return

    console.print(_COMPACT_BANNER)
    _show_tools(config)
    _run_request(
        f"Create a status update for '{project_name}'. "
        "Pull recent activity, issues, and PRs from the relevant tools. "
        "Include: overall status, recent wins, what's in flight, blockers/risks, and next milestones.",
        config,
    )


@cli.command()
def examples() -> None:
    """Show example commands you can run."""
    table = Table(title="PM Superpower — Example Commands", show_header=True, header_style="bold cyan")
    table.add_column("Command", style="bold", no_wrap=True)
    table.add_column("What it does")
    for cmd, desc in _EXAMPLES:
        table.add_row(f"pm {cmd} \"{desc}\"", "")
    console.print(table)


@cli.command()
def chat() -> None:
    """Start an interactive PM chat session."""
    _interactive()


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------

def _interactive() -> None:
    config = _load_config()
    if not config:
        sys.exit(1)

    console.print(_BANNER)
    _show_tools(config)
    console.print(
        "\n[dim]Type a request and press Enter. "
        "Examples: 'generate my standup', 'write a ticket for X', 'exit' to quit.[/dim]\n"
    )

    while True:
        try:
            text = Prompt.ask("[bold cyan]PM ›[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        text = text.strip()
        if not text:
            continue
        if text.lower() in ("exit", "quit", "bye", "q"):
            console.print("[dim]Goodbye![/dim]")
            break

        _run_request(text, config, quiet=True)
