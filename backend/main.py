from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.aqi import router as aqi_router

app = FastAPI(title="Sentinel AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(aqi_router)
from intervention_api import router as intervention_router
app.include_router(intervention_router)

@app.get("/")
def root():
    return {"service": "Sentinel AI", "status": "running"}

@app.get("/health")
def health():
    return {"status": "ok"}