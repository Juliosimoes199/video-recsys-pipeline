"""
Validação do token de sessão do Clerk.

Isso valida o token de sessão PADRÃO do Clerk (o que `useAuth().getToken()`
já devolve no frontend, sem passar nenhum `template`) — não precisa de
nenhum "JWT Template" customizado no dashboard do Clerk. O token vem
assinado em RS256; validamos a assinatura contra o JWKS público do Clerk
(`CLERK_JWKS_URL`), o `iss` (`CLERK_ISSUER`) e o `exp`. O claim `sub` é o
ID canônico do usuário — é isso que vira `ownerId`/`authorId`/etc. em todo
o resto do sistema.
"""

from __future__ import annotations

import os

import jwt
from fastapi import HTTPException, Request

CLERK_JWKS_URL = os.environ["CLERK_JWKS_URL"]
CLERK_ISSUER = os.environ["CLERK_ISSUER"]

# Client único pro processo inteiro (não um por requisição): ele cacheia as
# chaves públicas por `kid` e só busca de novo no JWKS se aparecer um `kid`
# desconhecido (o que acontece naturalmente quando o Clerk rotaciona as
# chaves de assinatura) — não bate na rede a cada requisição.
_jwks_client = jwt.PyJWKClient(CLERK_JWKS_URL)


def _extract_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header[len("Bearer ") :]


def current_user_id_optional(request: Request) -> str | None:
    """Devolve o `sub` do token se houver um token válido no header
    Authorization, ou `None` se o visitante estiver anônimo/token
    ausente/inválido/expirado. Uso: rotas que funcionam sem login (feed
    público, visualizações) mas que se beneficiam de saber quem é o
    usuário quando ele estiver logado."""
    token = _extract_token(request)
    if not token:
        return None

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=CLERK_ISSUER,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError:
        return None

    return claims.get("sub")


def current_user_id(request: Request) -> str:
    """Exige um token de sessão válido — levanta 401 se não houver (ou se
    estiver expirado/inválido). Uso: qualquer ação que só faz sentido pra
    um usuário logado (upload, comentar, curtir, etc.)."""
    user_id = current_user_id_optional(request)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHENTICATED", "message": "Faça login pra continuar"}},
        )
    return user_id
