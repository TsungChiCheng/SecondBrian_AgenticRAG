"""

Authentication middleware for Second Brain API
Validates JWT tokens from Google Sign-In and extracts user information
"""
from fastapi import HTTPException, Header, Depends
from typing import Optional
import jwt
from jwt import PyJWKClient
import os
import logging
logger = logging.getLogger(__name__)


# Google's public keys endpoint for JWT verification
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"

# Support both Web and iOS OAuth Client IDs
WEB_CLIENT_ID = "379223612421-22b3tbhsjricq56nolbujom513q0h7h7.apps.googleusercontent.com"
IOS_CLIENT_ID = "379223612421-up7uct4qnerdcuk8ti11sdtsu0ai6b47.apps.googleusercontent.com"
ALLOWED_CLIENT_IDS = [
    os.getenv("GOOGLE_CLIENT_ID", WEB_CLIENT_ID),  # Web client (for browser/Gradio)
    os.getenv("IOS_CLIENT_ID", IOS_CLIENT_ID),     # iOS client (for mobile app)
]


class User:
    """Represents an authenticated user"""
    def __init__(self, user_id: str, email: str, name: str, picture: Optional[str] = None):
        self.id = user_id
        self.email = email
        self.name = name
        self.picture = picture
    
    def __repr__(self):
        return f"User(id={self.id}, email={self.email}, name={self.name})"


def verify_google_token(token: str) -> dict:
    """
    Verify Google JWT token and return decoded payload
    Supports both Web and iOS OAuth Client IDs
    
    Args:
        token: JWT token from Google Sign-In
        
    Returns:
        Decoded token payload containing user information
        
    Raises:
        HTTPException: If token is invalid
    """
    # Get Google's public keys
    jwks_client = PyJWKClient(GOOGLE_JWKS_URL)
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    
    # Try to verify with each allowed client ID
    last_error = None
    for client_id in ALLOWED_CLIENT_IDS:
        try:
            # Verify and decode token
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=client_id,
                options={"verify_exp": True}
            )
            
            # Successfully verified!
            return payload
            
        except jwt.InvalidAudienceError:
            # This client ID doesn't match, try next one
            last_error = f"Audience doesn't match"
            continue
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Authentication error: {str(e)}")
    
    # If we get here, none of the client IDs matched
    raise HTTPException(
        status_code=401, 
        detail=f"Invalid token: {last_error}. Token audience does not match any configured client ID."
    )


async def get_current_user(authorization: Optional[str] = Header(None)) -> User:
    """
    FastAPI dependency to extract and validate user from Authorization header
    Supports TEST MODE for local development
    
    Usage:
        @app.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": user.id, "email": user.email}
    
    Args:
        authorization: Authorization header (Bearer token)
        
    Returns:
        User object with verified information
        
    Raises:
        HTTPException: If authentication fails
    """
    # TEST MODE: Bypass authentication for local development
    if os.getenv("ENABLE_TEST_MODE", "false").lower() == "true":
        logger.warning("⚠️  TEST MODE ENABLED - Authentication bypassed!")
        return User(
            user_id=os.getenv("TEST_USER_ID", "test-user-123"),
            email=os.getenv("TEST_USER_EMAIL", "test@localhost"),
            name=os.getenv("TEST_USER_NAME", "Local Test User"),
            picture=None
        )
    
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


async def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[User]:
    """
    Optional authentication - returns User if authenticated, None otherwise
    Useful for routes that work both authenticated and unauthenticated
    
    Usage:
        @app.get("/optional-auth")
        async def optional_route(user: Optional[User] = Depends(get_optional_user)):
            if user:
                return {"message": f"Hello {user.name}"}
            return {"message": "Hello guest"}
    """
    if not authorization:
        return None
    
    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None
