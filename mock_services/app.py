"""
In-memory mock of the platform behind one API gateway.

  POST   /api/users                 create user          {name, email, accountType}
  GET    /api/users/:id             get user
  PUT    /api/users/:id             update user (name, accountType)      [extension: completes CRUD]
  DELETE /api/users/:id             delete user                           [extension: CRUD + test cleanup]
  POST   /api/transactions          create transaction   {userId, amount, type, recipientId}
  GET    /api/transactions/:userId  list a user's transactions (sent or received)
  GET    /api/notifications/:userId notifications (async, eventually consistent)

Auth:  Authorization: Bearer admin-token     -> full access
       Authorization: Bearer readonly-token  -> GET only (403 otherwise)
       anything else / missing               -> 401
Errors: {"error": {"code", "message", "details": [{"field", "message"}]}}
"""
from __future__ import annotations

import os
import re
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

STATIC = Path(__file__).parent / "static"
ADMIN_TOKEN, READONLY_TOKEN = "admin-token", "readonly-token"
ACCOUNT_TYPES = {"basic": Decimal("1000"), "premium": Decimal("10000"), "business": Decimal("50000")}
TX_TYPES = {"transfer", "deposit", "withdrawal"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    lock = threading.RLock()
    users: dict[str, dict] = {}
    txns: dict[str, dict] = {}
    notifications: list[dict] = []

    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def err(status: int, code: str, message: str, details: list[dict] | None = None):
        body = {"error": {"code": code, "message": message}}
        if details:
            body["error"]["details"] = details
        return jsonify(body), status

    def invalid(*pairs: tuple[str, str]):
        return err(400, "VALIDATION", "Validation failed", [{"field": f, "message": m} for f, m in pairs])

    def body_or_error():
        try:
            data = request.get_json(force=True)
        except Exception:  # noqa: BLE001
            return None, err(400, "INVALID_JSON", "Request body is not valid JSON")
        if not isinstance(data, dict):
            return None, err(400, "INVALID_JSON", "Request body must be a JSON object")
        return data, None

    def secured(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            header = request.headers.get("Authorization", "")
            token = header[7:] if header.startswith("Bearer ") else None
            if token not in (ADMIN_TOKEN, READONLY_TOKEN):
                return err(401, "UNAUTHORIZED", "Missing or invalid credentials")
            if token == READONLY_TOKEN and request.method != "GET":
                return err(403, "FORBIDDEN", "Token does not permit write operations")
            return fn(*a, **kw)
        return wrapper

    # ---------- static mock frontend ----------
    @app.get("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.get("/transactions.html")
    def transactions_page():
        return send_from_directory(STATIC, "transactions.html")

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    # ---------- user validation ----------
    def validate_user(data: dict, *, partial: bool = False) -> list[tuple[str, str]]:
        problems = []
        if "name" in data or not partial:
            name = data.get("name")
            if not isinstance(name, str) or not name.strip():
                problems.append(("name", "Name is required"))
            elif len(name) > 100:
                problems.append(("name", "Name must be at most 100 characters"))
        if not partial:
            email = data.get("email")
            if not isinstance(email, str) or not EMAIL_RE.match(email):
                problems.append(("email", "A valid email is required"))
        if "accountType" in data and data["accountType"] not in ACCOUNT_TYPES:
            problems.append(("accountType", f"accountType must be one of {sorted(ACCOUNT_TYPES)}"))
        return problems

    # ---------- User Service ----------
    @app.post("/api/users")
    @secured
    def create_user():
        data, bad = body_or_error()
        if bad:
            return bad
        problems = validate_user(data)
        if problems:
            return invalid(*problems)
        with lock:
            email = data["email"].strip().lower()
            if any(u["email"] == email for u in users.values()):
                return err(409, "DUPLICATE_EMAIL", "Email already registered")
            user = {"id": str(uuid.uuid4()), "name": data["name"].strip(), "email": email,
                    "accountType": data.get("accountType", "basic"), "createdAt": now()}
            users[user["id"]] = user
        return jsonify(user), 201

    @app.get("/api/users/<uid>")
    @secured
    def get_user(uid):
        user = users.get(uid)
        return jsonify(user) if user else err(404, "USER_NOT_FOUND", "User not found")

    @app.put("/api/users/<uid>")
    @secured
    def update_user(uid):
        data, bad = body_or_error()
        if bad:
            return bad
        if "email" in data:
            return invalid(("email", "Email cannot be changed"))
        problems = validate_user(data, partial=True)
        if problems:
            return invalid(*problems)
        with lock:
            user = users.get(uid)
            if not user:
                return err(404, "USER_NOT_FOUND", "User not found")
            if "name" in data:
                user["name"] = data["name"].strip()
            if "accountType" in data:
                user["accountType"] = data["accountType"]
            return jsonify(user)

    @app.delete("/api/users/<uid>")
    @secured
    def delete_user(uid):
        with lock:
            if users.pop(uid, None) is None:
                return err(404, "USER_NOT_FOUND", "User not found")
            for tid in [t for t, x in txns.items() if uid in (x["userId"], x.get("recipientId"))]:
                del txns[tid]
            notifications[:] = [n for n in notifications if n["userId"] != uid]
        return "", 204

    # ---------- Transaction Service ----------
    @app.post("/api/transactions")
    @secured
    def create_txn():
        data, bad = body_or_error()
        if bad:
            return bad
        user_id, recipient_id = data.get("userId"), data.get("recipientId")
        amount, tx_type = data.get("amount"), data.get("type")

        problems = []
        if not isinstance(user_id, str) or not user_id:
            problems.append(("userId", "userId is required"))
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            problems.append(("amount", "amount must be a number"))
        elif amount <= 0:
            problems.append(("amount", "amount must be greater than 0"))
        elif Decimal(str(amount)).as_tuple().exponent < -2:
            problems.append(("amount", "amount supports at most 2 decimal places"))
        if tx_type not in TX_TYPES:
            problems.append(("type", f"type must be one of {sorted(TX_TYPES)}"))
        elif tx_type == "transfer":
            if not isinstance(recipient_id, str) or not recipient_id:
                problems.append(("recipientId", "recipientId is required for transfers"))
            elif recipient_id == user_id:
                problems.append(("recipientId", "Cannot transfer to yourself"))
        elif recipient_id is not None:
            problems.append(("recipientId", f"recipientId is not allowed for {tx_type}"))
        if problems:
            return invalid(*problems)

        with lock:
            user = users.get(user_id)
            if not user:
                return err(404, "USER_NOT_FOUND", "User not found")
            recipient = users.get(recipient_id) if tx_type == "transfer" else None
            if tx_type == "transfer" and not recipient:
                return err(404, "RECIPIENT_NOT_FOUND", "Recipient not found")
            if Decimal(str(amount)) > ACCOUNT_TYPES[user["accountType"]]:
                return err(422, "LIMIT_EXCEEDED",
                           f"Amount exceeds the transaction limit for {user['accountType']} accounts")
            txn = {"id": str(uuid.uuid4()), "userId": user_id, "amount": amount, "type": tx_type,
                   "recipientId": recipient_id, "status": "completed", "createdAt": now()}
            txns[txn["id"]] = txn

        if tx_type == "transfer":  # async event consumed by the Notification Service
            def publish():
                with lock:
                    notifications.extend([
                        {"id": str(uuid.uuid4()), "userId": user_id, "type": "TRANSACTION_SENT",
                         "transactionId": txn["id"], "createdAt": now()},
                        {"id": str(uuid.uuid4()), "userId": recipient_id, "type": "TRANSACTION_RECEIVED",
                         "transactionId": txn["id"], "createdAt": now()}])
            timer = threading.Timer(0.15, publish)
            timer.daemon = True
            timer.start()
        return jsonify(txn), 201

    @app.get("/api/transactions/<uid>")
    @secured
    def list_txns(uid):
        if uid not in users:
            return err(404, "USER_NOT_FOUND", "User not found")
        mine = [t for t in txns.values() if uid in (t["userId"], t.get("recipientId"))]
        return jsonify(sorted(mine, key=lambda t: t["createdAt"], reverse=True))

    # ---------- Notification Service ----------
    @app.get("/api/notifications/<uid>")
    @secured
    def list_notifications(uid):
        if uid not in users:
            return err(404, "USER_NOT_FOUND", "User not found")
        return jsonify([n for n in notifications if n["userId"] == uid])

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.getenv("PORT", "4000")))
