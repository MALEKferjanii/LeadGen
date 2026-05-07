from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from config.settings import get_settings

settings = get_settings()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str = Security(api_key_header)) -> str:
    if api_key != settings.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )
    return api_key
