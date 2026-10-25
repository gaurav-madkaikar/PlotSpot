import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Literal


class Settings(BaseModel):
    data_source: Literal["demo", "tmdb"] = "demo"
    tmdb_read_token: str = Field(default="", repr=False, exclude=True)
    lab_enabled: bool = False


def _flag(name: str) -> bool:
    value = os.getenv(name, "false").strip().lower()
    if value not in {"true", "false"}:
        raise RuntimeError(f"{name} must be true or false")
    return value == "true"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Existing environment variables take precedence over the local file.
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    source = os.getenv("MOVIE_DATA_SOURCE", "demo").strip().lower()
    if source not in {"demo", "tmdb"}:
        raise RuntimeError("MOVIE_DATA_SOURCE must be demo or tmdb")
    return Settings(
        data_source=source,
        tmdb_read_token=os.getenv("TMDB_READ_TOKEN", "").strip(),
        lab_enabled=_flag("PLOTSPOT_LAB_ENABLED"),
    )
