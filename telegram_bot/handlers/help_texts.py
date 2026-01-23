"""Centralized help texts for all bot commands."""
# ruff: noqa: E501

from telegram_bot.formatters import _escape_markdown

# Command help organized by command name
COMMAND_HELP = {
    "search": {
        "usage": "/search <query> [k:N] [t:0.7] [from:DATE] [to:DATE]",
        "description": "Performs semantic similarity search across indexed arXiv papers using vector embeddings.",
        "options": [
            ("k:N", "Number of results to return (default: 5)"),
            ("t:N", "Similarity threshold between 0 and 1 (default: 0.65)"),
            ("from:DATE", "Filter papers from this date (YYYY-MM-DD)"),
            ("to:DATE", "Filter papers until this date (YYYY-MM-DD)"),
        ],
        "examples": [
            "/search transformer architectures for vision",
            "/search diffusion models k:10 t:0.5",
            "/search attention from:2025-01-01 to:2025-01-15",
        ],
    },
    "similar": {
        "usage": "/similar <paper_id> [k:N] [t:0.7] [from:DATE] [to:DATE]",
        "description": "Finds papers with content similar to a reference paper using vector similarity.",
        "options": [
            ("k:N", "Number of results to return (default: 5)"),
            ("t:N", "Similarity threshold between 0 and 1 (default: 0.65)"),
            ("from:DATE", "Filter papers from this date (YYYY-MM-DD)"),
            ("to:DATE", "Filter papers until this date (YYYY-MM-DD)"),
        ],
        "examples": [
            "/similar 2601.02242",
            "/similar 2601.02242 k:10 t:0.7",
            "/similar 1706.03762 from:2024-01-01",
        ],
    },
    "paper": {
        "usage": "/paper <paper_id>",
        "description": "Retrieves full metadata for a paper including title, authors, abstract, publication dates, and arXiv category.",
        "options": [],
        "examples": [
            "/paper 2601.02242",
            "/paper 1706.03762",
        ],
    },
    "summarize": {
        "usage": "/summarize <paper_id|url> [cat:Category] [model:Name] [think:LEVEL]",
        "description": "Generates a comprehensive summary of the paper using Gemini AI and uploads it to Notion. Accepts paper IDs or arXiv URLs.",
        "options": [
            ("cat:Name", "Research category for organization (default: AdHoc Research)"),
            ("model:Name", "Model name to use (e.g., gemini-3-pro-preview)"),
            ("think:LEVEL", "Thinking level: LOW, MEDIUM, or HIGH"),
        ],
        "examples": [
            "/summarize 2601.02242",
            "/summarize https://arxiv.org/abs/2601.02242",
            "/summarize 2601.02242 cat:Image Editing",
            "/summarize 2601.02242 model:gemini-3-pro-preview think:HIGH",
        ],
    },
    "topics": {
        "usage": "/topics",
        "description": "Lists all available research topics from the Notion database. These topics can be used for subscriptions.",
        "options": [],
        "examples": ["/topics"],
    },
    "subscribe": {
        "usage": "/subscribe [topic_name]",
        "description": "Subscribe to a research topic. You'll receive notifications when new papers match the topic. Without arguments, shows available topics as buttons.",
        "options": [],
        "examples": [
            "/subscribe",
            "/subscribe Machine Learning",
        ],
    },
    "unsubscribe": {
        "usage": "/unsubscribe",
        "description": "Shows your active subscriptions and allows removing them via buttons.",
        "options": [],
        "examples": ["/unsubscribe"],
    },
    "subscriptions": {
        "usage": "/subscriptions",
        "description": "Displays all your personal subscriptions with creation dates.",
        "options": [],
        "examples": ["/subscriptions"],
    },
    "groupsubscribe": {
        "usage": "/groupsubscribe [topic_name]",
        "description": "Subscribe the entire group chat to a research topic. Only group administrators can use this command. All group members will receive notifications.",
        "options": [],
        "examples": [
            "/groupsubscribe",
            "/groupsubscribe Computer Vision",
        ],
    },
    "groupunsubscribe": {
        "usage": "/groupunsubscribe",
        "description": "Shows group's active subscriptions and allows removing them. Only group administrators can use this command.",
        "options": [],
        "examples": ["/groupunsubscribe"],
    },
    "groupsubscriptions": {
        "usage": "/groupsubscriptions",
        "description": "Displays all subscriptions for the current group chat. Available to all group members.",
        "options": [],
        "examples": ["/groupsubscriptions"],
    },
    "stats": {
        "usage": "/stats",
        "description": "Displays comprehensive database statistics including total papers count and a chart showing papers per month for the last 12 months.",
        "options": [],
        "examples": ["/stats"],
    },
    "insert": {
        "usage": "/insert <start_date> <end_date>",
        "description": "Fetches and indexes papers from arXiv for the specified date range. Only available to bot administrators.",
        "options": [],
        "examples": [
            "/insert 2025-01-10 2025-01-16",
        ],
    },
    "start": {
        "usage": "/start",
        "description": "Displays welcome message and quick start guide.",
        "options": [],
        "examples": ["/start"],
    },
    "help": {
        "usage": "/help [command]",
        "description": "Shows general help or detailed help for a specific command.",
        "options": [],
        "examples": [
            "/help",
            "/help search",
            "/help summarize",
        ],
    },
}

# Command categories for organized display
COMMAND_CATEGORIES = {
    "Discovery": ["search", "similar", "paper", "summarize"],
    "Personal Subscriptions": ["topics", "subscribe", "unsubscribe", "subscriptions"],
    "Group Subscriptions": ["groupsubscribe", "groupunsubscribe", "groupsubscriptions"],
    "Other": ["stats", "insert", "start", "help"],
}


def format_detailed_help(command: str) -> str:
    """Format detailed help for a specific command.

    Args:
        command: Command name (without /)

    Returns:
        Formatted help text with Markdown escaping
    """
    help_info = COMMAND_HELP.get(command)
    if not help_info:
        return ""

    lines = [f"*Command: /{command}*\n"]
    lines.append(_escape_markdown(help_info["description"]))
    lines.append("")
    lines.append(f"*Usage:* `{help_info['usage']}`")

    if help_info["options"]:
        lines.append("")
        lines.append("*Options:*")
        for opt_name, opt_desc in help_info["options"]:
            lines.append(f"  • `{opt_name}` \\- {_escape_markdown(opt_desc)}")

    if help_info["examples"]:
        lines.append("")
        lines.append("*Examples:*")
        for example in help_info["examples"]:
            lines.append(f"  `{example}`")  # noqa: PERF401

    return "\n".join(lines)


def format_general_help() -> str:
    """Format general help showing all commands by category.

    Returns:
        Formatted help text with Markdown escaping
    """
    lines = [
        "*ArXiv Paper Hound Bot*\n",
        "Use `/help <command>` for detailed information about a specific command\\.\n",
    ]

    for category, commands in COMMAND_CATEGORIES.items():
        lines.append(f"*{category}:*")
        for cmd in commands:
            info = COMMAND_HELP[cmd]
            lines.append(f"  `/{cmd}` \\- {_escape_markdown(info['description'])}")
        lines.append("")

    lines.append("*Quick Examples:*")
    lines.append("`/search transformer architectures`")
    lines.append("`/paper 2601.02242`")
    lines.append("`/summarize 2601.02242 cat:ML`")
    lines.append("`/stats` \\- View database statistics")

    return "\n".join(lines)


def get_command_help(command: str | None = None) -> str:
    """Get help text for specific command or general help.

    Args:
        command: Command name (without /) or None for general help

    Returns:
        Formatted help text with Markdown escaping
    """
    if command is None:
        return format_general_help()

    # Normalize: remove leading / if present
    command = command.lstrip("/").lower()

    if command in COMMAND_HELP:
        return format_detailed_help(command)

    # Command not found
    available = ", ".join(f"`/{cmd}`" for cmd in sorted(COMMAND_HELP.keys()))
    return (
        f"Command `/{_escape_markdown(command)}` not found\\.\n\n"
        f"Available commands: {available}\n\n"
        f"Use `/help` to see all commands\\."
    )


def get_usage_text(command: str) -> str:
    """Get inline usage text for command validation errors.

    Args:
        command: Command name (without /)

    Returns:
        Usage text string (not escaped for Markdown)
    """
    help_info = COMMAND_HELP.get(command, {})
    usage = help_info.get("usage", f"/{command}")

    lines = [f"Usage: {usage}"]

    if help_info.get("options"):
        lines.append("\nOptions:")
        for opt_name, opt_desc in help_info["options"]:
            lines.append(f"  {opt_name} - {opt_desc}")

    if help_info.get("examples"):
        lines.append("\nExamples:")
        for example in help_info["examples"]:
            lines.append(f"  {example}")  # noqa: PERF401

    return "\n".join(lines)
