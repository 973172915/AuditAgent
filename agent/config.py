"""全局配置。"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    # 数据路径
    bank_statement_path: Path = BASE_DIR / "data" / "bank_statement.csv"
    ledger_path: Path = BASE_DIR / "data" / "ledger.csv"
    schema_path: Path = BASE_DIR / "data" / "schema.yaml"

    # 安全
    max_result_rows: int = 500
    query_timeout_seconds: int = 30
    sql_whitelist_tables: str = "bank_statement,ledger"

    # 日志
    audit_log_path: Path = BASE_DIR / "logs" / "audit_log.jsonl"

    # Agent
    max_retries: int = 3


settings = Settings()
settings.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
