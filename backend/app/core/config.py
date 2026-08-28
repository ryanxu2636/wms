"""应用配置：统一 S0~S3 所需配置项。

环境变量可覆盖，.env 文件优先。
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "WMS 仓储管理系统"
    api_prefix: str = "/api"

    # 数据库（服务器实际用 psycopg v3）
    database_url: str = "postgresql+psycopg://wms:wms_dev_password@localhost:5432/wms"
    redis_url: str = "redis://localhost:6379/0"

    # JWT（T3.2 权限用）
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24

    # 出库卡点：面单未打印禁止出库（T3.1 打印门）
    REQUIRE_LABEL_PRINTED: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
