"""Database settings and the SQLAlchemy engine factory."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
SQL_DIR = PROJECT_ROOT / "sql"

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class DbConfig:
    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5433"))
    database: str = os.getenv("POSTGRES_DB", "erp")
    user: str = os.getenv("POSTGRES_USER", "erp")
    password: str = os.getenv("POSTGRES_PASSWORD", "erp_local_password")

    @property
    def url(self) -> str:
        return (
            f"postgresql+psycopg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


def make_engine(config: DbConfig | None = None, **kwargs) -> Engine:
    """Create an Engine with pre-ping, so a restarted container is recovered."""
    config = config or DbConfig()
    return create_engine(config.url, pool_pre_ping=True, future=True, **kwargs)
