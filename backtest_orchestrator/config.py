from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    start_date: str | None = None
    end_date: str | None = None
    window_days: int = 252
    tcost_bps: float = 10.0
    risk_aversion: float = 1.0
    markowitz_url: str = "http://localhost:8000/optimize"
    qaoa_url: str = "http://localhost:8001/optimize"
    request_timeout: float = 300.0

    class Config:
        env_prefix = "BACKTEST_"
        
settings = Settings()
