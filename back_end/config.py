from typing import Optional
from pydantic import BaseModel

class Settings(BaseModel):
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    API_BASE_URL: Optional[str] = None

    def init_api_base_url(self):
        self.API_BASE_URL = f"http://{self.HOST}:{self.PORT}"
        return self.API_BASE_URL

settings = Settings()