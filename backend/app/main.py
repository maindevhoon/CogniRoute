from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from cogniroute.orchestration_loop import run_generate, run_generate_stream
from cogniroute.schemas import GenerateRequest, GenerateResponse


app = FastAPI(title="CogniRoute Backend", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "name": "CogniRoute",
        "status": "online",
        "version": "0.2.0",
        "endpoints": ["/health", "/generate", "/generate/stream", "/docs"],
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    run = await run_generate(req.prompt)
    return GenerateResponse(run=run)


@app.post("/generate/stream")
async def generate_stream(req: GenerateRequest):
    """SSE endpoint: streams orchestration events as they happen."""
    return StreamingResponse(
        run_generate_stream(req.prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
