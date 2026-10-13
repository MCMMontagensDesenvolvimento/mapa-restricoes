from dataclasses import dataclass
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt import PyJWKClient
from .config import get_settings

bearer=HTTPBearer(auto_error=False)
@dataclass
class User:
    name:str; email:str; oid:str; groups:list[str]; role:str

def role_for(groups:list[str]):
    s=get_settings()
    if s.entra_admin_group_id and s.entra_admin_group_id in groups:return "Administrador"
    if s.entra_editor_group_id and s.entra_editor_group_id in groups:return "Editor"
    return "Visualizador"

async def current_user(token:HTTPAuthorizationCredentials|None=Depends(bearer)):
    s=get_settings()
    if s.app_env=="development" and not token:return User("Usuário Local","local@leancontrol","local",[],"Administrador")
    if not token:raise HTTPException(401,"Autenticação Microsoft necessária")
    issuer=f"https://login.microsoftonline.com/{s.entra_tenant_id}/v2.0"
    try:
        jwks=PyJWKClient(f"https://login.microsoftonline.com/{s.entra_tenant_id}/discovery/v2.0/keys")
        key=jwks.get_signing_key_from_jwt(token.credentials).key
        claims=jwt.decode(token.credentials,key,algorithms=["RS256"],audience=s.entra_api_client_id,issuer=issuer)
    except Exception as exc: raise HTTPException(401,"Token inválido") from exc
    groups=claims.get("groups",[])
    return User(claims.get("name",""),claims.get("preferred_username",claims.get("email","")),claims.get("oid",""),groups,role_for(groups))

def require(*roles):
    async def check(user:User=Depends(current_user)):
        if user.role not in roles:raise HTTPException(403,"Perfil sem permissão para esta operação")
        return user
    return check

