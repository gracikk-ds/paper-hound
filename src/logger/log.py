"""This module provides classes for custom logging with Loguru."""

from typing import Any


class DevelopFormatter:
    """Loguru formatter that formats logs for development environment."""

    def __init__(self, component_name: str) -> None:
        """Initialize a LoguruContainer instance.

        Args:
            component_name (str): The name of the component associated with the logger.
        """
        self.component_name = component_name

    @staticmethod
    def format_extra(record: dict[str, Any]) -> str:
        """Format the extra part of the log record.

        Args:
            record (dict): Log record dictionary.

        Returns:
            str: Formatted extra part of the log string.
        """
        extra_items = record.get("extra", {}).items()
        formatted_items = (f"<lvl>{key}={extra_value}</>" for key, extra_value in extra_items)
        return " ".join(formatted_items)

    @staticmethod
    def format_exception(record: dict[str, Any]) -> str:
        """Format the exception part of the log record.

        Args:
            record (Dict[str, Any]): Log record dictionary.

        Returns:
            str: Formatted exception part of the log string.
        """
        return "\n{exception}\n" if record.get("exception") else "\n"

    def __call__(self, record: dict[str, Any]) -> str:
        """Format the log record for the development environment.

        Args:
            record (Dict[str, Any]): Log record dictionary.

        Returns:
            str: Formatted log string.
        """
        extra = self.format_extra(record)
        exception = self.format_exception(record)
        return (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</> | <lvl>{level: <8}</> | "
            f"<cyan>{self.component_name}</> | "
            "<cyan>{name}</>:<cyan>{function}</>:<cyan>{line}</> "
            "- <lvl>{message}</> - "
            f"{extra}{exception}"
        )
