# main.py - your FastAPI server
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.price_comparison import router as price_comparison_router
from app.database import engine, Base

# create tables if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Grocery Price API")

# let the frontend connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "https://mii-pricecomparison.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# add the price comparison endpoints
app.include_router(price_comparison_router)

@app.get("/")
def read_root():
    return {"message": "API is running!"}
