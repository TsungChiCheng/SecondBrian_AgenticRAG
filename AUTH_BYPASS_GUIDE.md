# Local Testing Guide - Bypass Google Authentication

## Option 1: Use Environment Variable (Recommended)

Add this to your `.env` file to enable test mode:

```bash
# Enable test mode (bypasses Google OAuth)
ENABLE_TEST_MODE=true
TEST_USER_ID=test-user-123
TEST_USER_EMAIL=test@example.com
TEST_USER_NAME=Test User
```

Then update `auth/middleware.py` as shown below.

## Option 2: Use API Documentation (Swagger)

1. Go to http://localhost:8001/docs
2. Most endpoints don't require auth in the Swagger UI
3. You can test endpoints directly from there

## Modified auth/middleware.py for Test Mode

Replace the `get_current_user` function in `/services/api-service/auth/middleware.py` with this version:

```python
async def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    """
    FastAPI dependency to extract and validate user from Authorization header
    Supports TEST MODE for local development
    """
    # TEST MODE: Bypass authentication for local development
    if os.getenv("ENABLE_TEST_MODE", "false").lower() == "true":
        logger.warning("⚠️  TEST MODE ENABLED - Authentication bypassed!")
        return User(
            user_id=os.getenv("TEST_USER_ID", "test-user-123"),
            email=os.getenv("TEST_USER_EMAIL", "test@localhost"),
            name=os.getenv("TEST_USER_NAME", "Test User"),
            picture=None
        )
    
    # Normal authentication flow
    if not authorization:
        raise HTTPException(
            status_code=401, 
            detail="Authorization header missing. Please log in."
        )
    
    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Expected: Bearer <token>"
        )
    
    token = parts[1]
    
    # Verify token and extract user info
    payload = verify_google_token(token)
    
    # Create User object from payload
    user = User(
        user_id=payload.get("sub"),  # Google user ID
        email=payload.get("email"),
        name=payload.get("name"),
        picture=payload.get("picture")
    )
    
    # Validate required fields
    if not user.id or not user.email:
        raise HTTPException(
            status_code=401,
            detail="Invalid token: missing required user information"
        )
    
    # Log successful authentication with user details (DEBUG level)
    logger.debug(f"🔐 Authenticated: {user.name} ({user.email}) | user_id: {user.id}")
    
    return user
```

## Quick Fix Script

Run this to enable test mode automatically:

```bash
cd /Users/tsungchicheng/Desktop/SecondBrain_AgenticRAG

# Add test mode to .env
echo "" >> .env
echo "# Test Mode - Bypass Google OAuth for local testing" >> .env
echo "ENABLE_TEST_MODE=true" >> .env
echo "TEST_USER_ID=local-test-user" >> .env
echo "TEST_USER_EMAIL=test@localhost" >> .env
echo "TEST_USER_NAME=Local Test User" >> .env

# Stop and rebuild API service
docker stop api-service
docker rm api-service  
docker compose build --no-cache api
docker run -d --name api-service --network secondbrain_agenticrag_microservices --env-file .env -e DATABASE_URL=postgresql://alvin:securepass123@secondbrain_agenticrag-db-1:5432/secondbrain -e VECTOR_SERVICE_URL=http://secondbrain_agenticrag-vector-1:8002 -p 8001:8001 secondbrain_agenticrag-api

# Wait for startup
sleep 10

# Test it
curl http://localhost:8001/health
```

## Alternative: Setup Google OAuth Properly

If you want real Google authentication:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable "Google+ API"
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Configure OAuth consent screen
6. Add authorized JavaScript origins: `http://localhost:8000`
7. Add authorized redirect URIs: `http://localhost:8000/auth/callback`
8. Copy the Client ID and update `.env`:
   ```bash
   GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
   ```

## Test Without Browser (curl)

Using test mode, you can now call APIs without auth headers:

```bash
# This will work with test mode enabled
curl -X POST http://localhost:8001/ask \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "Hello, test the system!",
    "use_agentic_rag": true
  }'
```
