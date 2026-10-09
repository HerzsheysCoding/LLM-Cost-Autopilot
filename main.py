import httpx
import tiktoken
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from vector_store import RedisSemanticCache
from budget import BudgetEnforcer

app = FastAPI(title="LLM Cost Autopilot Gateway")
cache = RedisSemanticCache()
# Establish connection pool to prevent socket exhaustion under load
http_client = httpx.AsyncClient(limits=httpx.Limits(max_keepalive_connections=100))
tokenizer = tiktoken.get_encoding("cl100k_base")

@app.on_event("startup")
async def startup_event():
    await cache.initialize_index()
    app.state.budget = BudgetEnforcer(cache.redis)

def estimate_cost(model: str, text: str) -> float:
    """Uses exact BPE tokenization for financial safety limits."""
    tokens = len(tokenizer.encode(text))
    rates = {
        # Fall 2026 Pricing Matrix
        "gpt-4o-mini": {"in": 0.15, "out": 0.60},
        "gpt-4o": {"in": 2.50, "out": 10.00}
    }
    rate = rates.get(model, rates["gpt-4o-mini"])
    return (tokens / 1_000_000) * rate["in"]

@app.post("/v1/chat/completions")
async def proxy_inference(request: Request):
    body = await request.json()
    prompt = " ".join([m.get("content", "") for m in body.get("messages", [])])
    
    # 1. Semantic Cache Intercept (Bypasses Upstream Entirely)
    cached_response = await cache.get_match(prompt)
    if cached_response:
        return JSONResponse(
            content={**cached_response, "x_autopilot_cache": "HIT"},
            headers={"X-Cache-Status": "HIT"}
        )

    # 2. Dynamic Cascading Classifier
    target_model = "gpt-4o-mini" if len(tokenizer.encode(prompt)) < 1500 else "gpt-4o"
    body["model"] = target_model
    est_cost = estimate_cost(target_model, prompt)
    org_id = request.headers.get("X-Organization-Id", "default")
    
    # 3. Atomic Budget Authorization
    authorized = await app.state.budget.authorize_spend(org_id, est_cost, daily_limit=50.0)
    if not authorized:
        raise HTTPException(status_code=429, detail="Daily LLM FinOps budget exceeded.")

    # 4. Asynchronous Upstream Streaming Proxy
    upstream_req = http_client.build_request(
        method="POST",
        url="https://api.openai.com/v1/chat/completions",
        headers={"Authorization": request.headers.get("Authorization")},
        json=body
    )
    
    upstream_resp = await http_client.send(upstream_req, stream=True)
    
    return StreamingResponse(
        upstream_resp.aiter_raw(),
        status_code=upstream_resp.status_code,
        headers={"X-Autopilot-Routed-Model": target_model}
    )
