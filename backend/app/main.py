"""
SpiceScript compiler backend.

Each compiler stage is its own endpoint and runs independently.
Every login and stage run is written to action_logs.
"""
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import db
from .grammar import GRAMMAR_EBNF, KEYWORD_TABLE, OPERATOR_TABLE, SAMPLES
from . import pipeline
from .lexer import lex


@asynccontextmanager
async def lifespan(_app):
    db.init_db()
    yield


app = FastAPI(title="SpiceScript Compiler", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- models -----------------------------------------------------------------

class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=128)


class SourceIn(BaseModel):
    source: str = Field(max_length=50_000)


# ---- auth helpers -----------------------------------------------------------

def current_user(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.get_user_by_token(authorization.split(" ", 1)[1].strip())
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


def public_user(user) -> dict:
    return {"id": user["id"], "username": user["username"], "role": user["role"]}


# ---- auth routes ------------------------------------------------------------

@app.post("/api/auth/register")
def register(creds: Credentials):
    user = db.create_user(creds.username, creds.password)
    if not user:
        raise HTTPException(status_code=409, detail="Username already taken")
    db.add_log(user["id"], user["username"], "register", status="success")
    token = db.create_session(user["id"])
    return {"token": token, "user": public_user(user)}


@app.post("/api/auth/login")
def login(creds: Credentials):
    user = db.get_user_by_name(creds.username)
    if not user or not db.verify_password(creds.password, user["salt"], user["password_hash"]):
        db.add_log(user["id"] if user else None, creds.username, "login", status="error",
                   detail="Invalid credentials")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    db.add_log(user["id"], user["username"], "login", status="success")
    return {"token": db.create_session(user["id"]), "user": public_user(user)}


@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(default=None), user=Depends(current_user)):
    db.delete_session(authorization.split(" ", 1)[1].strip())
    db.add_log(user["id"], user["username"], "logout", status="success")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return public_user(user)


# ---- public info (grammar panel) -------------------------------------------

@app.get("/api/grammar")
def grammar():
    return {
        "language": "SpiceScript",
        "ebnf": GRAMMAR_EBNF,
        "keywords": KEYWORD_TABLE,
        "operators": OPERATOR_TABLE,
        "samples": SAMPLES,
    }


# ---- compiler stages --------------------------------------------------------
# Each endpoint runs its stage on its own (earlier stages are run only to feed it) and
# every result has the same {stage, ok, errors, ...} shape.

def run_stage(stage: str, user, source: str, runner) -> dict:
    result = runner(source)
    status = "success" if result.get("ok") else "error"
    detail = None
    if status == "error":
        detail = f'{len(result.get("errors", []))} error(s)'
        if result.get("stopped_at"):
            detail = f'stopped at {result["stopped_at"]}: {detail}'
        elif result.get("blocked_by"):
            detail = f'blocked by {result["blocked_by"]}: {detail}'
    db.add_log(user["id"], user["username"], "run_stage", stage=stage, status=status,
               input_snapshot=source, detail=detail)
    return result


@app.post("/api/lex")
def api_lex(body: SourceIn, user=Depends(current_user)):
    return run_stage("lexical", user, body.source, lex)


@app.post("/api/parse")
def api_parse(body: SourceIn, user=Depends(current_user)):
    return run_stage("syntax", user, body.source, lambda src: pipeline.run_single(src, "syntax"))


@app.post("/api/semantic")
def api_semantic(body: SourceIn, user=Depends(current_user)):
    return run_stage("semantic", user, body.source, lambda src: pipeline.run_single(src, "semantic"))


@app.post("/api/icg")
def api_icg(body: SourceIn, user=Depends(current_user)):
    return run_stage("icg", user, body.source, lambda src: pipeline.run_single(src, "icg"))


@app.post("/api/run")
def api_run(body: SourceIn, user=Depends(current_user)):
    """Final output of the program (runs every earlier stage first)."""
    return run_stage("run", user, body.source, lambda src: pipeline.run_single(src, "run"))


@app.post("/api/run-all")
def api_run_all(body: SourceIn, user=Depends(current_user)):
    """The complete compilation process in one call, logged as a single 'full' action."""
    return run_stage("full", user, body.source, pipeline.run_all)


# ---- logs -------------------------------------------------------------------

@app.get("/api/logs")
def logs(all: bool = False, limit: int = 200, user=Depends(current_user)):
    limit = max(1, min(limit, 1000))
    if all:
        if user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Admins only")
        return db.get_logs(None, limit)
    return db.get_logs(user["id"], limit)
