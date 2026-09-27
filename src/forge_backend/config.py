import os

REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

CORS_ORIGINS: list[str] = [
  origin.strip()
  for origin in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
  if origin.strip()
]