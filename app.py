#!/usr/bin/env python3
"""
WeCom AI Customer Service Bot V4.0
====================================
Enterprise WeChat (企业微信) AI chatbot powered by DeepSeek API.

Architecture:
- Flask callback: real-time private chat reply
- Session archive polling: group chat monitoring + smart interjection
- Scheduled topic pushing: breakfast/lunch/afternoon tea/evening
- Dead group revival: auto-detect inactive groups + engagement hooks

DeepSeek Integration:
- Uses deepseek-chat model for intelligent replies
- Keyword-based knowledge base for instant FAQ matching
- Session memory with 30-min TTL for contextual conversation

GitHub: https://github.com/YOUR_USERNAME/wecom-deepseek-bot
Powered by DeepSeek API
"""

from flask import Flask, request
import hashlib, base64, struct, os, json, time, re, random, urllib.request, threading, datetime
import xml.etree.ElementTree as ET
from Crypto.Cipher import AES

# Topic engine & scheduler
from topics import get_topic_by_time, get_engagement_topic, get_conversion_hook, generate_ai_topic
from scheduler import GroupScheduler

app = Flask(__name__)

# ====== Configuration (set via environment variables) ======
TOKEN = os.environ.get("WECOM_TOKEN", "your_wecom_token_here")
AES_KEY = os.environ.get("WECOM_AES_KEY", "your_aes_key_here")
CORP_ID = os.environ.get("WECOM_CORP_ID", "your_corp_id_here")
SECRET = os.environ.get("WECOM_SECRET", "your_app_secret_here")

# DeepSeek API Configuration
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-your-deepseek-api-key")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# Session Archive (requires WeCom approval, ~3 working days)
ARCHIVE_SECRET = os.environ.get("WECOM_ARCHIVE_SECRET", "")
ARCHIVE_ENABLED = bool(ARCHIVE_SECRET)

# Runtime state
ACCESS_TOKEN = None
TOKEN_EXPIRY = 0
ARCHIVE_TOKEN = None
ARCHIVE_TOKEN_EXPIRY = 0
LAST_ARCHIVE_SEQ = 0

# ====== Knowledge Base (customizable per business) ======
KNOWLEDGE_BASE = {
    "membership|member|会员": "Our membership day is the 9th of every month! Top up ¥300 → get ¥330 balance + gift pack + coupons!",
    "cake|birthday|蛋糕|生日": "7-inch cake ¥199, 9-inch ¥299, 11-inch ¥399. Last day & 1st of month: buy 7-inch get 5-inch mini cake FREE!",
    "new|新品|3.0": "New 3.0 products are here! Matcha Lava Cake ¥28, Chocolate Mango House ¥19, Blueberry House ¥19.",
    "hours|营业时间": "Open daily 7:00 AM - 10:00 PM. Hours may vary by location.",
    "delivery|外卖|配送": "We deliver via Meituan & Ele.me! Search our brand name in the app.",
    "complaint|投诉|problem": "So sorry for the inconvenience! Please tell me the details and I'll help resolve it right away.",
}

SYSTEM_PROMPT = """You are a friendly bakery customer service AI assistant.
Personality: warm, helpful, knows your products well, conversational.

Rules:
1. Keep replies short and friendly (10-40 words)
2. Use emojis naturally
3. Never promise refunds/compensation amounts - say "Let me check with the store manager"
4. After 3 rounds of chat, naturally invite: "Add me on WeChat, I'll send you a coupon!"
5. Don't make up prices or policies you're not sure about
"""

# Sensitive keyword blocklist
BLOCKED_KEYWORDS = ["lawsuit", "refund", "sue", "attorney", "315"]

# Session memory (30-min TTL)
SESSIONS = {}

# ====== WeCom API Helpers ======

def get_access_token():
    """Get WeCom access token with caching"""
    global ACCESS_TOKEN, TOKEN_EXPIRY
    now = time.time()
    if ACCESS_TOKEN and now < TOKEN_EXPIRY - 300:
        return ACCESS_TOKEN
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={CORP_ID}&corpsecret={SECRET}"
    try:
        resp = json.loads(urllib.request.urlopen(url, timeout=10).read())
        if resp.get("errcode") == 0:
            ACCESS_TOKEN = resp["access_token"]
            TOKEN_EXPIRY = now + resp.get("expires_in", 7200)
            return ACCESS_TOKEN
    except Exception as e:
        print(f"[Token] Failed: {e}")
    return None


def get_archive_token():
    """Get session archive token"""
    global ARCHIVE_TOKEN, ARCHIVE_TOKEN_EXPIRY
    if not ARCHIVE_ENABLED:
        return None
    now = time.time()
    if ARCHIVE_TOKEN and now < ARCHIVE_TOKEN_EXPIRY - 300:
        return ARCHIVE_TOKEN
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={CORP_ID}&corpsecret={ARCHIVE_SECRET}"
    try:
        resp = json.loads(urllib.request.urlopen(url, timeout=10).read())
        if resp.get("errcode") == 0:
            ARCHIVE_TOKEN = resp["access_token"]
            ARCHIVE_TOKEN_EXPIRY = now + resp.get("expires_in", 7200)
            return ARCHIVE_TOKEN
    except Exception as e:
        print(f"[Archive Token] Failed: {e}")
    return None


def decrypt_msg(encrypted_xml):
    """Decrypt WeCom callback message (AES-256-CBC)"""
    try:
        root = ET.fromstring(encrypted_xml)
        encrypt = root.find("Encrypt")
        if encrypt is None:
            return None
        cipher_text = base64.b64decode(encrypt.text)
        key = base64.b64decode(AES_KEY + "=")
        cipher = AES.new(key, AES.MODE_CBC, iv=key[:16])
        raw = cipher.decrypt(cipher_text)
        pad = raw[-1]
        raw = raw[:-pad]
        xml_len = struct.unpack(">I", raw[16:20])[0]
        return raw[20:20 + xml_len].decode("utf-8")
    except Exception as e:
        print(f"[Decrypt] Failed: {e}")
        return None


def send_text_msg(user_id, content):
    """Send text message to a WeCom user"""
    token = get_access_token()
    if not token:
        return False
    body = {
        "touser": user_id,
        "msgtype": "text",
        "agentid": 1000039,  # Your app's agent ID
        "text": {"content": content}
    }
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode(),
            headers={"Content-Type": "application/json"}
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        return resp.get("errcode") == 0
    except Exception as e:
        print(f"[Send] Failed: {e}")
        return False


def send_group_msg(roomid, content):
    """Send message to a WeCom group chat"""
    token = get_access_token()
    if not token:
        return False
    body = {
        "chatid": roomid,
        "msgtype": "text",
        "text": {"content": content},
    }
    url = f"https://qyapi.weixin.qq.com/cgi-bin/appchat/send?access_token={token}"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode(),
            headers={"Content-Type": "application/json"},
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        return resp.get("errcode") == 0
    except Exception as e:
        print(f"[Group Send] Failed: {e}")
        return False


# ====== AI Reply Engine (DeepSeek API) ======

def match_knowledge(user_msg):
    """Fast keyword matching against knowledge base"""
    for pattern, answer in KNOWLEDGE_BASE.items():
        for keyword in pattern.split("|"):
            if keyword.lower() in user_msg.lower():
                return answer
    return None


def check_blocked(text):
    """Check for sensitive keywords that should not be auto-replied"""
    for kw in BLOCKED_KEYWORDS:
        if kw.lower() in text.lower():
            return kw
    return None


def get_session(user_id):
    """Get or create a user session with 30-min TTL"""
    now = time.time()
    expired = [u for u, s in SESSIONS.items() if now - s["last_time"] > 1800]
    for uid in expired:
        del SESSIONS[uid]
    if user_id not in SESSIONS:
        SESSIONS[user_id] = {"messages": [], "turns": 0, "last_time": now}
    else:
        SESSIONS[user_id]["last_time"] = now
        SESSIONS[user_id]["turns"] += 1
    return SESSIONS[user_id]


def ai_reply(user_msg, user_name="", user_id=""):
    """
    Generate AI reply using DeepSeek API.
    First checks knowledge base for instant match, falls back to AI generation.
    Includes session context for conversational continuity.
    """
    # Fast path: knowledge base match
    kb_answer = match_knowledge(user_msg)
    if kb_answer:
        return kb_answer

    # AI generation via DeepSeek API
    try:
        session = get_session(user_id)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        # Include last 6 messages for context
        for m in session["messages"][-6:]:
            messages.append(m)
        messages.append({"role": "user", "content": user_msg})

        # Call DeepSeek Chat API
        url = "https://api.deepseek.com/v1/chat/completions"
        body = {
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "max_tokens": 150,
            "temperature": 0.7
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {DEEPSEEK_KEY}"
            }
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        ai_text = resp["choices"][0]["message"]["content"].strip()

        # Save to session memory
        session["messages"].append({"role": "user", "content": user_msg})
        session["messages"].append({"role": "assistant", "content": ai_text})
        return ai_text
    except Exception as e:
        print(f"[AI] Error: {e}")
        return None


# ====== Group Chat Intelligence ======

ACTIVE_GROUPS = {}
CONVERSATION_TRACKER = {}  # user_id → {"turns": int, "last_time": float}
LAST_TOPIC_HOURS = {}


def should_interject(text):
    """Smart interjection detection: should we reply in the group?"""
    text_lower = text.lower().strip()

    # Direct mention → must reply in group
    if "@bot" in text_lower or "@assistant" in text_lower:
        return True, "group"

    # Product/price questions → reply in group (benefits everyone)
    product_keywords = ["cake", "bread", "price", "menu", "recommend",
                        "new", "promotion", "hours", "delivery", "coffee"]
    for kw in product_keywords:
        if kw in text_lower:
            return True, "group"

    # Food/meal chat → worth engaging
    food_keywords = ["breakfast", "lunch", "dinner", "tea", "coffee",
                     "bread", "dessert", "bakery", "matcha", "chocolate"]
    if any(kw in text_lower for kw in food_keywords):
        return True, "group"

    return False, None


def poll_archive():
    """
    Session archive polling loop (every 60s).
    Pulls new messages → interjection + conversion tracking + group activity logging.
    """
    global LAST_ARCHIVE_SEQ
    while True:
        time.sleep(60)
        if not ARCHIVE_ENABLED:
            continue
        now_hour = datetime.datetime.now().hour
        if now_hour >= 23 or now_hour < 6:
            continue

        token = get_archive_token()
        if not token:
            continue
        try:
            url = "https://qyapi.weixin.qq.com/cgi-bin/msgaudit/groupchat/get"
            body = {"seq": LAST_ARCHIVE_SEQ, "limit": 50}
            req = urllib.request.Request(
                url, data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"}
            )
            resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
            if resp.get("errcode") != 0:
                continue

            for msg in resp.get("chatdata", []):
                seq = msg.get("seq", 0)
                if seq > LAST_ARCHIVE_SEQ:
                    LAST_ARCHIVE_SEQ = seq

                roomid = msg.get("roomid", "")
                sender = msg.get("from", "")
                msg_type = msg.get("msgtype", "")

                if roomid:
                    ACTIVE_GROUPS[roomid] = {
                        "last_human": time.time(),
                        "last_bot": ACTIVE_GROUPS.get(roomid, {}).get("last_bot", 0)
                    }

                if "bot" in sender.lower():
                    continue

                if msg_type == "text":
                    content = msg.get("text", {}).get("content", "")
                    if not content:
                        continue

                    print(f"[Group] {roomid}/{sender}: {content[:60]}", flush=True)
                    blocked = check_blocked(content)
                    if blocked:
                        print(f"[BLOCKED] keyword={blocked}")
                        continue

                    should_reply, reply_method = should_interject(content)
                    if should_reply:
                        reply = ai_reply(content, user_id=sender)
                        if reply:
                            if reply_method == "group" and roomid:
                                send_group_msg(roomid, reply)
                            else:
                                send_text_msg(sender, reply)
                            print(f"[Interject] → {sender}: {reply[:60]}")

                            # Conversion tracking
                            track = CONVERSATION_TRACKER.get(sender, {"turns": 0, "last_time": 0})
                            if time.time() - track["last_time"] < 3600:
                                track["turns"] += 1
                            else:
                                track["turns"] = 1
                            track["last_time"] = time.time()
                            CONVERSATION_TRACKER[sender] = track

                            if track["turns"] >= 3:
                                hook = get_conversion_hook()
                                send_text_msg(sender, hook)
                                print(f"[Conversion] → {sender}")
                                del CONVERSATION_TRACKER[sender]

        except Exception as e:
            print(f"[Archive Poll] {e}")


def timer_tick():
    """Scheduled topic pusher + dead group revival (every 120s)"""
    while True:
        time.sleep(120)
        if not ARCHIVE_ENABLED:
            continue
        now = datetime.datetime.now()
        h = now.hour
        wd = now.weekday()

        if h >= 23 or h < 6:
            continue

        for gid in list(ACTIVE_GROUPS.keys()):
            g = ACTIVE_GROUPS.get(gid, {})
            now_ts = time.time()

            # Timed topics (one per time slot per group)
            slot_key = None
            if 6 <= h < 8: slot_key = "breakfast"
            elif 11 <= h < 13: slot_key = "lunch"
            elif 14 <= h < 16: slot_key = "afternoon"
            elif 18 <= h < 20: slot_key = "evening"

            if slot_key and LAST_TOPIC_HOURS.get(gid) != slot_key:
                topic = get_topic_by_time(h, wd)
                if send_group_msg(gid, topic):
                    LAST_TOPIC_HOURS[gid] = slot_key
                    ACTIVE_GROUPS[gid] = {**g, "last_bot": now_ts}
                    print(f"[Scheduled] → {gid}: {topic[:60]}")

            # Dead group revival (30min no activity)
            last_human = g.get("last_human", 0)
            last_bot = g.get("last_bot", 0)
            if (now_ts - last_human > 1800 and
                now_ts - last_bot > 1800 and
                random.random() < 0.3):
                revive = get_engagement_topic()
                if send_group_msg(gid, revive):
                    ACTIVE_GROUPS[gid] = {**g, "last_bot": now_ts}
                    print(f"[Revive] → {gid}: {revive[:60]}")


# ====== Flask Routes ======

@app.route("/callback", methods=["GET", "POST"])
def callback():
    """WeCom callback endpoint: URL verification (GET) + message handling (POST)"""
    if request.method == "GET":
        # URL verification
        msg_signature = request.args.get("msg_signature", "")
        timestamp = request.args.get("timestamp", "")
        nonce = request.args.get("nonce", "")
        echostr = request.args.get("echostr", "")
        if not echostr:
            return "OK"
        sorted_list = sorted([TOKEN, timestamp, nonce, echostr])
        expected = hashlib.sha1("".join(sorted_list).encode()).hexdigest()
        if msg_signature != expected:
            return "signature failed", 403
        try:
            key = base64.b64decode(AES_KEY + "=")
            cipher = AES.new(key, AES.MODE_CBC, iv=key[:16])
            raw = cipher.decrypt(base64.b64decode(echostr))
            pad = raw[-1]
            raw = raw[:-pad]
            msg_len = struct.unpack(">I", raw[16:20])[0]
            return raw[20:20 + msg_len].decode("utf-8")
        except Exception as e:
            return f"decrypt error: {e}", 500

    else:
        # Message handling
        try:
            raw_xml = request.data.decode("utf-8")
            plain_xml = decrypt_msg(raw_xml)
            if not plain_xml:
                return "decrypt failed", 500

            root = ET.fromstring(plain_xml)
            msg_type_elem = root.find("MsgType")
            from_user = root.find("FromUserName")
            if msg_type_elem is None or from_user is None:
                return "OK"

            user = from_user.text
            msg_type = msg_type_elem.text or ""

            if msg_type == "text":
                content_elem = root.find("Content")
                if content_elem is None:
                    return "OK"
                text = content_elem.text.strip()
                print(f"[Message] {user}: {text}", flush=True)
            elif msg_type == "voice":
                recognition = root.find("Recognition")
                if recognition is None or not recognition.text:
                    send_text_msg(user, "I can't hear voice messages yet 😊 Please type it out!")
                    return "OK"
                text = recognition.text.strip()
                print(f"[Voice] {user}: {text}", flush=True)
            else:
                return "OK"

            blocked = check_blocked(text)
            if blocked:
                send_text_msg(user, "I'm not sure about this one — let me ask the store manager!")
                return "OK"
            if not text or len(text) < 1:
                return "OK"

            reply = ai_reply(text, user_id=user)
            if reply:
                send_text_msg(user, reply)
            else:
                send_text_msg(user, "Got it! I'm still learning — want to check out our new products? 🎂")
        except Exception as e:
            print(f"[Error] {e}")
        return "OK"


@app.route("/health")
def health():
    """Health check endpoint"""
    return json.dumps({
        "version": "4.0",
        "status": "ok",
        "archive_enabled": ARCHIVE_ENABLED,
        "last_seq": LAST_ARCHIVE_SEQ,
        "active_groups": len(ACTIVE_GROUPS),
        "conversation_tracks": len(CONVERSATION_TRACKER)
    })


# ====== Startup ======
if ARCHIVE_ENABLED:
    threading.Thread(target=poll_archive, daemon=True).start()
    threading.Thread(target=timer_tick, daemon=True).start()
    print("[System] Archive polling + scheduled pushing started (120s heartbeat)")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
