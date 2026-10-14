from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore', env_ignore_empty=True)
    database_url: str = 'sqlite:///./runtime/platform.db'
    mysql_host: str = ''
    mysql_port: int = 3306
    mysql_database: str = 'rag_eval'
    mysql_user: str = 'rag'
    mysql_password: str = ''
    provider_mode: str = 'demo'
    generation_api_key: str = ''
    generation_base_url: str = 'https://api.deepseek.com'
    generation_model: str = 'deepseek-flash'
    judge_api_key: str = ''
    judge_base_url: str = 'https://api.deepseek.com'
    judge_model: str = 'deepseek-v4-pro'
    embedding_api_key: str = ''
    embedding_base_url: str = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    embedding_model: str = 'text-embedding-v3'
    rerank_api_key: str = ''
    rerank_url: str = ''
    rerank_model: str = ''
    generation_input_price: float | None = None
    generation_output_price: float | None = None
    judge_input_price: float | None = None
    judge_output_price: float | None = None
    currency: str = 'CNY'
    api_concurrency: int = Field(default=3, ge=1, le=100)
    requests_per_minute: int = Field(default=30, ge=1, le=10000)
    max_retries: int = Field(default=4, ge=0, le=10)
    request_timeout: float = Field(default=60, gt=0, le=600)


settings = Settings()
