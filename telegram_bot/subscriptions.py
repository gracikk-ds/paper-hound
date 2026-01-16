"""SQLite-based subscription storage for Telegram bot."""

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from loguru import logger


@dataclass
class Subscription:
    """Represents a user subscription."""

    id: int
    user_id: int
    chat_id: int
    query: str
    threshold: float
    created_at: datetime
    last_notified_at: datetime | None
    is_active: bool


class SubscriptionStore:
    """SQLite-based storage for user subscriptions."""

    def __init__(self, db_path: str = "subscriptions.db") -> None:
        """Initialize the subscription store.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    query TEXT NOT NULL,
                    threshold REAL DEFAULT 0.65,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_notified_at TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id
                ON subscriptions(user_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_subscriptions_is_active
                ON subscriptions(is_active)
            """)
            conn.commit()
        logger.info(f"Subscription database initialized at {self.db_path}")

    def add_subscription(
        self,
        user_id: int,
        chat_id: int,
        query: str,
        threshold: float = 0.65,
    ) -> Subscription:
        """Add a new subscription.

        Args:
            user_id: Telegram user ID.
            chat_id: Telegram chat ID for notifications.
            query: Search query for the subscription.
            threshold: Similarity threshold for matches.

        Returns:
            The created Subscription.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO subscriptions (user_id, chat_id, query, threshold)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, chat_id, query, threshold),
            )
            conn.commit()
            subscription_id = cursor.lastrowid

        return Subscription(
            id=subscription_id,
            user_id=user_id,
            chat_id=chat_id,
            query=query,
            threshold=threshold,
            created_at=datetime.now(),  # noqa: DTZ005
            last_notified_at=None,
            is_active=True,
        )

    def get_user_subscriptions(self, user_id: int) -> list[Subscription]:
        """Get all active subscriptions for a user.

        Args:
            user_id: Telegram user ID.

        Returns:
            List of active subscriptions.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM subscriptions
                WHERE user_id = ? AND is_active = TRUE
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()

        return [self._row_to_subscription(row) for row in rows]

    def get_all_active_subscriptions(self) -> list[Subscription]:
        """Get all active subscriptions.

        Returns:
            List of all active subscriptions.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM subscriptions
                WHERE is_active = TRUE
                ORDER BY user_id, created_at DESC
                """,
            )
            rows = cursor.fetchall()

        return [self._row_to_subscription(row) for row in rows]

    def get_subscription_by_id(self, subscription_id: int) -> Subscription | None:
        """Get a subscription by ID.

        Args:
            subscription_id: The subscription ID.

        Returns:
            The Subscription or None if not found.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM subscriptions WHERE id = ?",
                (subscription_id,),
            )
            row = cursor.fetchone()

        return self._row_to_subscription(row) if row else None

    def deactivate_subscription(self, subscription_id: int, user_id: int) -> bool:
        """Deactivate a subscription.

        Args:
            subscription_id: The subscription ID to deactivate.
            user_id: The user ID (for verification).

        Returns:
            True if deactivated, False if not found or not owned by user.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE subscriptions
                SET is_active = FALSE
                WHERE id = ? AND user_id = ? AND is_active = TRUE
                """,
                (subscription_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_last_notified(
        self,
        subscription_id: int,
        notified_at: datetime | None = None,
    ) -> None:
        """Update the last notified timestamp for a subscription.

        Args:
            subscription_id: The subscription ID.
            notified_at: The notification timestamp (defaults to now).
        """
        notified_at = notified_at or datetime.now()  # noqa: DTZ005
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE subscriptions
                SET last_notified_at = ?
                WHERE id = ?
                """,
                (notified_at.isoformat(), subscription_id),
            )
            conn.commit()

    def count_user_subscriptions(self, user_id: int) -> int:
        """Count active subscriptions for a user.

        Args:
            user_id: Telegram user ID.

        Returns:
            Number of active subscriptions.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM subscriptions
                WHERE user_id = ? AND is_active = TRUE
                """,
                (user_id,),
            )
            return cursor.fetchone()[0]

    def _row_to_subscription(self, row: sqlite3.Row) -> Subscription:
        """Convert a database row to a Subscription object.

        Args:
            row: SQLite row.

        Returns:
            Subscription object.
        """
        last_notified = None
        if row["last_notified_at"]:
            last_notified = datetime.fromisoformat(row["last_notified_at"])

        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        return Subscription(
            id=row["id"],
            user_id=row["user_id"],
            chat_id=row["chat_id"],
            query=row["query"],
            threshold=row["threshold"],
            created_at=created_at,
            last_notified_at=last_notified,
            is_active=bool(row["is_active"]),
        )


# Global subscription store instance with thread-safe initialization
_subscription_store: SubscriptionStore | None = None
_subscription_store_lock = threading.Lock()


def get_subscription_store(db_path: str = "subscriptions.db") -> SubscriptionStore:
    """Get or create the global subscription store instance.

    Thread-safe singleton pattern using double-checked locking.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        The SubscriptionStore instance.
    """
    global _subscription_store  # noqa: PLW0603
    if _subscription_store is None:
        with _subscription_store_lock:
            # Double-check after acquiring lock
            if _subscription_store is None:
                _subscription_store = SubscriptionStore(db_path)
    return _subscription_store
