from fastapi import FastAPI

app = FastAPI(
    title="AION",
    version="0.1.0"
)

@app.get("/")
async def root():
    return {
        "project": "AION",
        "status": "running"
    }

@app.get("/health")
async def health():
    return {
        "status": "ok"
    }
