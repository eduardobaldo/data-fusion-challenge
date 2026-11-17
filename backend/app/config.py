from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")
    sqlite_path_setting: str = Field(default="data/football.sqlite", validation_alias="SQLITE_PATH")
    mongo_url: str = ""
    mongo_database: str = "football_raw"
    duckdb_path_setting: str = Field(default="data/analytics.duckdb", validation_alias="DUCKDB_PATH")
    demo_city: str = "São Paulo"
    demo_region: str = "SP"
    demo_country: str = "Brasil"
    demo_timezone: str = "America/Sao_Paulo"
    overpass_bbox: str = "-23.75,-46.83,-23.35,-46.36"
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    frontend_origin: str = "http://localhost:5173"

    @staticmethod
    def project_path(value: str) -> Path:
        path = Path(value).expanduser()
        return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()

    @property
    def sqlite_path(self) -> Path:
        return self.project_path(self.sqlite_path_setting)

    @property
    def duckdb_path(self) -> Path:
        return self.project_path(self.duckdb_path_setting)

    @property
    def data_dir(self) -> Path:
        return self.duckdb_path.parent


settings = Settings()
