# fastapi_proxy.py

from fastapi import FastAPI, Request
from fastapi.responses import Response
import httpx

app = FastAPI()

# -----------------------------
# CONFIG
# -----------------------------
STREAMLIT_URL = "https://innodatajiradashboard.streamlit.app"  # Hosted Streamlit URL

# -----------------------------
# PROXY ENDPOINT
# -----------------------------
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy(request: Request, path: str):
    """
    Reverse proxy to forward all requests to Streamlit and remove iframe-blocking headers
    """
    # Forward query parameters
    query_string = request.url.query
    url = f"{STREAMLIT_URL}/{path}"
    if query_string:
        url += f"?{query_string}"

    # Prepare headers
    headers = dict(request.headers)
    headers.pop("host", None)  # Remove host header to prevent conflicts

    # Prepare request body
    body = await request.body()

    # Forward the request to Streamlit
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            streamlit_response = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
                timeout=None
            )
        except httpx.RequestError as e:
            return Response(
                content=f"Error connecting to Streamlit: {e}",
                status_code=500
            )

    # Build response
    response = Response(
        content=streamlit_response.content,
        status_code=streamlit_response.status_code,
        media_type=streamlit_response.headers.get("content-type")
    )

    # Remove headers that block iframe embedding
    for h in ["x-frame-options", "content-security-policy"]:
        if h in response.headers:
            del response.headers[h]

    return response

# -----------------------------
# ROOT ENDPOINT
# -----------------------------
@app.get("/")
async def root(request: Request):
    """
    Root endpoint returns Streamlit app in an iframe for testing
    """
    url = STREAMLIT_URL
    if request.url.query:
        url += f"?{request.url.query}"
    return Response(
        content=f'<iframe src="{url}" width="100%" height="1000px"></iframe>',
        media_type="text/html"
    )
