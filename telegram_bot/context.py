"""Bot context holder for shared dependencies."""

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from src.containers.containers import AppContainer


class BotContext:
    """Context holder for bot dependencies."""

    container: "AppContainer | None" = None
    admin_user_ids: ClassVar[set[int]] = set()


bot_context = BotContext()
