from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import json
import httpx
import asyncio


VISUAL_SERVER_URL = "http://127.0.0.1:7995"

app = FastAPI()


@app.post("/search/{item_name}")
async def trigger_search(item_name: str):
    async with httpx.AsyncClient() as client:
        try:
            await client.post(f"{VISUAL_SERVER_URL}/track/start", json={"name": item_name})
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Visual Server unavailable")

    async def event_generator():
        async with httpx.AsyncClient() as client:
            while True:
                try:
                    response = await client.get(f"{VISUAL_SERVER_URL}/track/latest")
                    data = response.json()
                    
                    # {"status":"idle","name":null,"found":null,"confidence":null,"x":null,"y":null,"w":null,"h":null}
                    yield json.dumps(data) + "\n"

                except Exception as e:
                    yield json.dumps({"error": str(e)}) + "\n"
                    break
                
                # Polling interval: 200ms
                await asyncio.sleep(0.2)

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@app.post("/cancel")
async def trigger_cancel():
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{VISUAL_SERVER_URL}/track/stop")
        return response.json()
