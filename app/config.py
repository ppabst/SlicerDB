from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SLICERDB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Field(default=Path("./data"))
    spoolman_url: str | None = Field(default=None)
    bind_host: str = Field(default="0.0.0.0")
    bind_port: int = Field(default=8080)
    debug: bool = Field(default=False)

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'db.sqlite'}"

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"


settings = Settings()
