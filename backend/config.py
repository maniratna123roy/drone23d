from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    POSTGRES_USER: str = "spatial_user"
    POSTGRES_PASSWORD: str = "spatial_twin_secret_dev"
    POSTGRES_DB: str = "spatial_twin"
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432

    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    STATIC_ASSETS_DIR: str = "./static"
    PIPELINE_JOBS_DIR: str = "./output/phase_d/jobs"
    PIPELINE_MAX_UPLOAD_MB: int = Field(default=512, ge=1, le=4096)
    PIPELINE_MAX_FRAMES: int = Field(default=36, ge=5, le=120)
    PIPELINE_CAMERA_MODEL: str = "SIMPLE_RADIAL"
    PIPELINE_IMAGE_WIDTH: int = Field(default=640, ge=64, le=1920)
    PIPELINE_RENDER_WIDTH: int = Field(default=320, ge=32, le=1024)
    PIPELINE_TRAIN_ITERATIONS: int = Field(default=600, ge=1, le=10000)
    PIPELINE_MAX_GAUSSIANS: int = Field(default=40000, ge=500, le=100000)
    PIPELINE_DEVICE: Literal["cuda", "cpu"] = "cuda"
    PIPELINE_TIMEOUT_SECONDS: int = Field(default=7200, ge=60, le=86400)
    KAGGLE_USERNAME: str = ""
    KAGGLE_KEY: str = ""

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
