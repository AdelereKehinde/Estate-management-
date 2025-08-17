
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

JWT_SECRET = "change_me"     # move to .env in production
JWT_ALG = "HS256"
ACCESS_MINUTES = 60

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)

def hash_password(p: str) -> str:
    return pwd_ctx.hash(p)

def verify_password(p: str, hashed: str) -> bool:
    return pwd_ctx.verify(p, hashed)

def create_access_token(sub: str, role: str):
    now = datetime.utcnow()
    payload = {"sub": sub, "role": role, "iat": now, "exp": now + timedelta(minutes=ACCESS_MINUTES)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def get_current(identity: HTTPAuthorizationCredentials = Depends(bearer)):
    if not identity:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = identity.credentials
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return decoded  # dict with sub, role

def require_role(*roles: str):
    def dep(user = Depends(get_current)):
        if roles and user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return dep
