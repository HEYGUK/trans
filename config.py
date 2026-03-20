import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ⭐ OpenRouter 配置
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"  # ⭐ OpenRouter 端点
    MODEL_NAME = os.getenv("MODEL_NAME", "anthropic/claude-sonnet-4-20250514")  # ⭐ 最新模型

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    MAX_TEXT_LENGTH = 10000
