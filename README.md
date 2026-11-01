# SpiceScript Compiler

## Run

Backend (terminal 1):

    cd backend
    pip install -r requirements.txt
    uvicorn app.main:app --reload        # http://127.0.0.1:8000/docs
    python -m unittest discover -s tests -t . -v

The first registered user becomes admin (can see everyone's logs).

## Endpoints
| Method | Path | Notes |
|---|---|---|
| POST | /api/auth/register, /api/auth/login | {username, password} -> {token, user} |
| POST | /api/auth/logout, GET /api/auth/me | Bearer token |
| GET  | /api/grammar | EBNF, keyword/operator tables, sample programs (public) |
| POST | /api/lex | {source} -> {ok, tokens, errors} |
| POST | /api/parse | {source} -> {ok, ast, errors} |
| POST | /api/semantic | {source} -> {ok, symbol_table, errors} |
| POST | /api/icg | {source} -> {ok, instructions (three-address code), errors} |
| POST | /api/run | {source} -> {ok, output, errors}  final program output |
| POST | /api/run-all | {source} -> every stage + final output; stops at the first failing stage |
| GET  | /api/logs?all=true | own logs; all=true for admin |

Every stage returns {stage, ok, errors[...]} so the UI can treat them the same way.
Every login and stage run is stored in `action_logs` (user, action, stage, status, input snapshot, time).

## Design
Each engine (`lexer`, `parser`, `semantic`, `icg`, `interpreter`) is its own module with one
public function and never imports another engine. `pipeline.py` is the only place they meet:
it feeds one stage's output to the next and reports when a stage is blocked by an earlier error.

## Run the frontend (terminal 2)
    cd frontend
    npm install
    npm run dev          # open http://localhost:5173

Register an account on the login page (the first account is the admin), pick a sample from
the Grammar panel, and press Run all, or click a single stage to run just that engine.

## How to test it (for the examiner)
1. Start the backend and the frontend (see above) and open http://localhost:5173.
2. Register an account, then sign in. The first account is the admin.
3. Open the **Grammar** panel on the left. It shows the language rules, the keyword and operator tables, and sample programs.
4. Load a sample (or type your own program in the **Program** box) and press **Run all**, or click one stage to run only that engine.

| Sample | What to expect |
|---|---|
| Arithmetic | all five stages pass; output `13` and `30` |
| If / else | all stages pass; output `x is bigger` |
| Loop | all stages pass; output `3`, `2`, `1` |
| Nested blocks | all stages pass; output `1`, `two`, `3` |
| Lexical error | Lexical stage fails and marks the bad character; later stages are skipped |
| Semantic error | Lexical and Syntax pass; Semantic reports 3 errors (undeclared variable, redeclaration, type mismatch) |

Try your own errors too: `mix x 5` (missing `into`) fails at Syntax, and a loop with no `done` fails at Syntax with the line it was opened on.

Each engine is independent. `/api/lex`, `/api/parse`, `/api/semantic`, `/api/icg` and `/api/run` each work on their own, and the **Activity log** page shows every action with the user, stage, result and program. Interactive API docs: http://127.0.0.1:8000/docs

Unit tests (71): `cd backend && python -m unittest discover -s tests -t . -v`
