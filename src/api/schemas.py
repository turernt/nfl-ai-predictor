from typing import Optional
from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    home_team: str = Field(..., examples=["KC"], description="Abréviation nflverse")
    away_team: str = Field(..., examples=["BUF"])
    neutral_site: bool = False


class PredictionResponse(BaseModel):
    home_team: str
    away_team: str
    home_elo: float
    away_elo: float
    prob_home_win: float
    prob_away_win: float
    predicted_spread: float
    confidence_score: str
    commentary: Optional[str] = None
