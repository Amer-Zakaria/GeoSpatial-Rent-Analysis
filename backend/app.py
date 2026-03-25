from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class PredictionRequest(BaseModel):
    lat: float
    lon: float
    bedrooms: int
    bathrooms: int
    size: float

@app.post("/predict")
def predict(data: PredictionRequest):
    return {
        "predicted_price": 85000  # fake MVP response
    }
# remember smarty pants run using :"uvicorn backend.app:app --reload" ... I hate windows -_-