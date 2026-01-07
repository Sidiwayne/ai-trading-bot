"""Database infrastructure for FusionBot."""

from src.infrastructure.database.connection import (
    DatabaseManager,
    get_db_manager,
    get_session,
)
from src.infrastructure.database.models import (
    Base,
    SeenNewsORM,
    TradeORM,
    MacroEventORM,
    SystemStateORM,
    DailyPerformanceORM,
)
from src.infrastructure.database.repositories import (
    NewsRepository,
    TradeRepository,
    MacroEventRepository,
    SystemStateRepository,
)

__all__ = [
    # Connection
    "DatabaseManager",
    "get_db_manager",
    "get_session",
    # ORM Models
    "Base",
    "SeenNewsORM",
    "TradeORM",
    "MacroEventORM",
    "SystemStateORM",
    "DailyPerformanceORM",
    # Repositories
    "NewsRepository",
    "TradeRepository",
    "MacroEventRepository",
    "SystemStateRepository",
]

