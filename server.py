import asyncio
import json
import sqlite3
import hashlib
import uuid
import os
from datetime import datetime
from websockets.server import serve

def init_db():
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            color TEXT NOT NULL,
            created_at TEXT NOT NULL,
            birthdate TEXT
        );
        CREATE TABLE IF NOT EXISTS channels (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'text'
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            channel_id TEXT NOT NULL,
            author_id TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            deleted INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (channel_id) REFERENCES channels(id),
            FOREIGN KEY (author_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS reactions (
            message_id TEXT NOT NULL,
            emoji TEXT NOT NULL,
            user_id TEXT NOT NULL,
            PRIMARY KEY (message_id, emoji, user_id)
        );
    """)
    c.executemany(
        "INSERT OR IGNORE INTO channels (id, name, type) VALUES (?, ?, ?)",
        [("general","général","text"),("gaming","gaming","text"),("musique","musique","text")]
    )
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect("chat.db")
    conn.row_factory = sqlite3.Row
    return conn

COLORS = ["#5865f2","#eb459e","#23a559","#ed4245","#fee75c","#57f287","#9b59b6","#e67e22"]

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

clients = {}

async def broadcast(channel_id, payload, exclude=None):
    msg = json.dumps(payload)
    targets = [ws for ws, info in clients.items() if info.get("channel") == channel_id and ws is not exclude]
    if targets:
        await asyncio.gather(*(ws.send(msg) for ws in targets), return_exceptions=True)

async def broadcast_presence():
    online = [{"user_id": info["user_id"], "username": info["username"], "color": info["color"]} for info in clients.values()]
    msg = json.dumps({"type": "presence", "online": online})
    if clients:
        await asyncio.gather(*(ws.send(msg) for ws in clients), return_exceptions=True)

async def handle_register(ws, data):
    username = data.get("username", "").strip()
    password = data.get("password", "")
    birthdate = data.get("birthdate", "").strip()
    if not username or not password or not birthdate:
        return await ws.send(json.dumps({"type": "error", "msg": "Tous les champs sont requis."}))
    db = get_db()
    color = COLORS[hash(username) % len(COLORS)]
    user_id = str(uuid.uuid4())
    try:
        db.execute(
            "INSERT INTO users (id, username, password_hash, color, created_at, birthdate) VALUES (?,?,?,?,?,?)",
            (user_id, username, hash_pw(password), color, datetime.utcnow().isoformat(), birthdate)
        )
        db.commit()
        await ws.send(json.dumps({"type": "registered", "user_id": user_id, "username": username, "color": color}))
    except sqlite3.IntegrityError:
        await ws.send(json.dumps({"type": "error", "msg": "Ce nom d'utilisateur est déjà pris."}))
    finally:
        db.close()

async def handle_login(ws, data):
    db = get_db()
    row = db.execute(
        "SELECT * FROM users WHERE username=? AND password_hash=?",
        (data.get("username",""), hash_pw(data.get("password","")))
    ).fetchone()
    db.close()
    if not row:
        return await ws.send(json.dumps({"type": "error", "msg": "Identifiants incorrects."}))
    clients[ws] = {"user_id": row["id"], "username": row["username"], "color": row["color"], "channel": "general"}
    await ws.send(json.dumps({"type": "logged_in", "user_id": row["id"], "username": row["username"], "color": row["color"]}))
    await broadcast_presence()

async def handle_reset_password(ws, data):
    username = data.get("username", "").strip()
    birthdate = data.get("birthdate", "").strip()
    new_password = data.get("new_password", "")
    if not username or not birthdate or not new_password:
        return await ws.send(json.dumps({"type": "error", "msg": "Tous les champs sont requis."}))
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE username=? AND birthdate=?", (username, birthdate)).fetchone()
    if not row:
        db.close()
        return await ws.send(json.dumps({"type": "error", "msg": "Pseudo ou date de naissance incorrecte."}))
    db.execute("UPDATE users SET password_hash=? WHERE username=?", (hash_pw(new_password), username))
    db.commit()
    db.close()
    await ws.send(json.dumps({"type": "password_reset_ok"}))

async def handle_join_channel(ws, data):
    if ws not in clients:
        return
    channel_id = data.get("channel_id", "general")
    clients[ws]["channel"] = channel_id
    db = get_db()
    rows = db.execute("""
        SELECT m.id, m.content, m.timestamp, m.deleted, u.username, u.color, u.id as author_id
        FROM messages m JOIN users u ON m.author_id = u.id
        WHERE m.channel_id = ? ORDER BY m.timestamp ASC LIMIT 50
    """, (channel_id,)).fetchall()
    messages = []
    for r in rows:
        reactions = {}
        if not r["deleted"]:
            rxns = db.execute("SELECT emoji, user_id FROM reactions WHERE message_id=?", (r["id"],)).fetchall()
            for rx in rxns:
                reactions.setdefault(rx["emoji"], []).append(rx["user_id"])
        messages.append({"id": r["id"], "author": r["username"], "author_id": r["author_id"], "color": r["color"], "text": r["content"], "time": r["timestamp"], "deleted": bool(r["deleted"]), "reactions": reactions})
    db.close()
    await ws.send(json.dumps({"type": "channel_history", "channel_id": channel_id, "messages": messages}))

async def handle_send_message(ws, data):
    if ws not in clients:
        return
    info = clients[ws]
    channel_id = info["channel"]
    content = data.get("content", "").strip()
    if not content:
        return
    msg_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    db = get_db()
    db.execute("INSERT INTO messages (id, channel_id, author_id, content, timestamp) VALUES (?,?,?,?,?)",
               (msg_id, channel_id, info["user_id"], content, timestamp))
    db.commit()
    db.close()
    payload = {"type": "new_message", "channel_id": channel_id, "message": {"id": msg_id, "author": info["username"], "author_id": info["user_id"], "color": info["color"], "text": content, "time": timestamp, "deleted": False, "reactions": {}}}
    await broadcast(channel_id, payload)

async def handle_delete_message(ws, data):
    if ws not in clients:
        return
    info = clients[ws]
    msg_id = data.get("message_id")
    db = get_db()
    row = db.execute("SELECT author_id FROM messages WHERE id=?", (msg_id,)).fetchone()
    if not row:
        db.close()
        return await ws.send(json.dumps({"type": "error", "msg": "Message introuvable."}))
    db.execute("UPDATE messages SET deleted=1 WHERE id=?", (msg_id,))
    db.commit()
    db.close()
    await broadcast(info["channel"], {"type": "message_deleted", "channel_id": info["channel"], "message_id": msg_id})

async def handle_reaction(ws, data):
    if ws not in clients:
        return
    info = clients[ws]
    msg_id = data.get("message_id")
    emoji = data.get("emoji")
    db = get_db()
    existing = db.execute("SELECT 1 FROM reactions WHERE message_id=? AND emoji=? AND user_id=?", (msg_id, emoji, info["user_id"])).fetchone()
    if existing:
        db.execute("DELETE FROM reactions WHERE message_id=? AND emoji=? AND user_id=?", (msg_id, emoji, info["user_id"]))
    else:
        db.execute("INSERT INTO reactions (message_id, emoji, user_id) VALUES (?,?,?)", (msg_id, emoji, info["user_id"]))
    db.commit()
    rxns = db.execute("SELECT emoji, user_id FROM reactions WHERE message_id=?", (msg_id,)).fetchall()
    db.close()
    reactions = {}
    for rx in rxns:
        reactions.setdefault(rx["emoji"], []).append(rx["user_id"])
    await broadcast(info["channel"], {"type": "reaction_update", "channel_id": info["channel"], "message_id": msg_id, "reactions": reactions})

async def handle_typing(ws, data):
    if ws not in clients:
        return
    info = clients[ws]
    await broadcast(info["channel"], {"type": "typing", "username": info["username"], "channel_id": info["channel"]}, exclude=ws)

async def handle_webrtc_relay(ws, data):
    if ws not in clients:
        return
    info = clients[ws]
    target_id = data.get("target")
    data["from_id"] = info["user_id"]
    data["from_name"] = info["username"]
    target_ws = next((w for w, i in clients.items() if i["user_id"] == target_id), None)
    if target_ws:
        await target_ws.send(json.dumps(data))

async def handle_call_broadcast(ws, data):
    if ws not in clients:
        return
    info = clients[ws]
    channel_id = data.get("channel_id", info["channel"])
    data["caller_id"] = info["user_id"]
    data["caller"] = info["username"]
    await broadcast(channel_id, data, exclude=ws)

HANDLERS = {
    "register":       handle_register,
    "login":          handle_login,
    "reset_password": handle_reset_password,
    "join_channel":   handle_join_channel,
    "send_message":   handle_send_message,
    "delete_message": handle_delete_message,
    "reaction":       handle_reaction,
    "typing":         handle_typing,
    "call_start":     handle_call_broadcast,
    "call_end":       handle_call_broadcast,
    "webrtc_offer":   handle_webrtc_relay,
    "webrtc_answer":  handle_webrtc_relay,
    "ice_candidate":  handle_webrtc_relay,
}

async def handler(ws):
    print(f"[+] Nouvelle connexion : {ws.remote_address}")
    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
                action = data.get("type")
                fn = HANDLERS.get(action)
                if fn:
                    await fn(ws, data)
                else:
                    await ws.send(json.dumps({"type": "error", "msg": f"Action inconnue : {action}"}))
            except json.JSONDecodeError:
                await ws.send(json.dumps({"type": "error", "msg": "JSON invalide."}))
    except Exception as e:
        print(f"[-] Déconnexion : {e}")
    finally:
        if ws in clients:
            print(f"[-] Déconnexion de {clients[ws]['username']}")
            del clients[ws]
            await broadcast_presence()

async def main():
    port = int(os.environ.get("PORT", 8765))
    host = "0.0.0.0"
    init_db()
    print(f"✅ Base de données initialisée.")
    print(f"🚀 Serveur démarré sur ws://{host}:{port}")
    async with serve(handler, host, port):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
