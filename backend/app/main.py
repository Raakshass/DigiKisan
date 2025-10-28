from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response
from .api.routes import router
from .core.db import connect_to_mongo, close_mongo_connection
import json
import time

app = FastAPI(title="DigiKisan Backend", version="0.1.0")

# ✅ ADD CORS middleware to allow Flutter web app to call API
origins = [
    "http://localhost:3000",
    "http://localhost:8080", 
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8080",
    "http://localhost:*",
    "*"  # Allow all origins for development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔍 LOGGING MIDDLEWARE TO DEBUG CHAT REQUESTS/RESPONSES
@app.middleware("http")
async def log_chat_requests(request: Request, call_next):
    """Log request and response bodies for chat endpoints"""
    
    # Only log /chat/ endpoints to avoid spam
    if "/chat/" in str(request.url):
        start_time = time.time()
        
        # Read request body
        req_body = await request.body()
        
        print(f"\n{'='*60}")
        print(f"🔍 REQUEST: {request.method} {request.url}")
        print(f"🕐 Time: {time.strftime('%H:%M:%S')}")
        print(f"📤 REQUEST HEADERS: {dict(request.headers)}")
        
        try:
            if req_body:
                req_json = json.loads(req_body.decode())
                print(f"📤 REQUEST BODY:")
                print(json.dumps(req_json, indent=2, ensure_ascii=False))
            else:
                print(f"📤 REQUEST BODY: (empty)")
        except json.JSONDecodeError:
            print(f"📤 REQUEST BODY (raw): {req_body.decode()}")

        # Process the request
        response = await call_next(request)

        # Read response body
        resp_body = b""
        async for chunk in response.body_iterator:
            resp_body += chunk

        print(f"📥 RESPONSE STATUS: {response.status_code}")
        print(f"📥 RESPONSE HEADERS: {dict(response.headers)}")
        
        try:
            if resp_body:
                resp_json = json.loads(resp_body.decode())
                print(f"📥 RESPONSE BODY:")
                print(json.dumps(resp_json, indent=2, ensure_ascii=False))
            else:
                print(f"📥 RESPONSE BODY: (empty)")
        except json.JSONDecodeError:
            print(f"📥 RESPONSE BODY (raw): {resp_body.decode()}")

        process_time = time.time() - start_time
        print(f"⏱️  PROCESSING TIME: {process_time:.3f}s")
        print(f"{'='*60}\n")

        # Return fresh response
        return Response(
            content=resp_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type
        )
    else:
        return await call_next(request)

@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup"""
    print("🚀 Starting DigiKisan Backend...")
    await connect_to_mongo()
    print("✅ All services initialized successfully!")
    print("🔍 Request/Response logging enabled for /chat/ endpoints")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup services on application shutdown"""
    print("🔌 Shutting down DigiKisan Backend...")
    await close_mongo_connection()
    print("✅ All services closed successfully!")

# Health check endpoint
@app.get("/")
async def root():
    return {
        "message": "DigiKisan Backend API is running!",
        "version": "0.1.0",
        "status": "healthy",
        "docs": "/docs",
        "logging": "enabled for /chat/ endpoints"
    }

# Include API routes with prefix
app.include_router(router, prefix="/api")

# Additional metadata for API documentation
app.title = "DigiKisan Backend API"
app.description = """
🌱 **DigiKisan Backend API**

A comprehensive agricultural assistance platform providing:
- 💬 Intelligent price inquiry system with session management
- 🔍 Real-time market price data from AgMarkNet
- 🌿 Crop disease detection and treatment recommendations
- 📊 Historical price data and analytics
- 🤖 AI-powered conversational assistance
- 🔍 Request/Response logging for debugging

Built with FastAPI, MongoDB, and advanced ML models.
"""
app.version = "0.1.0"
app.contact = {
    "name": "DigiKisan Support",
    "email": "support@digikisan.com",
}
app.license_info = {
    "name": "MIT License",
    "url": "https://opensource.org/licenses/MIT",
}
