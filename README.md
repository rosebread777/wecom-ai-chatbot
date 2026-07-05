# WeCom DeepSeek AI Chatbot 🤖🍰

> 企业微信 AI 智能客服机器人 — 基于 DeepSeek API 的全自动顾客互动系统

**Powered by DeepSeek API**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![DeepSeek](https://img.shields.io/badge/AI-DeepSeek%20Chat-purple.svg)](https://platform.deepseek.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A production-ready AI customer service bot for Enterprise WeChat (企业微信), powering a 59-store bakery chain's customer engagement across 200+ group chats.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🤖 **AI-Powered Replies** | DeepSeek Chat API for natural, contextual conversations |
| 📚 **Knowledge Base** | Instant keyword matching for FAQs + AI fallback |
| 💬 **Private Chat** | Real-time callback-based reply for 1-on-1 messages |
| 👥 **Group Chat** | Session archive polling + smart interjection |
| ⏰ **Scheduled Topics** | Auto-push breakfast/lunch/tea/evening content |
| 🔄 **Dead Group Revival** | Auto-detect inactive groups + engagement hooks |
| 🎯 **Conversion Engine** | 3+ chat rounds → auto-invite to add WeChat + coupon |
| 🔒 **Content Safety** | Sensitive keyword blocklist + escalation routing |
| 🧠 **Session Memory** | 30-min TTL context window for coherent conversations |

---

## 🏗️ Architecture

```
                    ┌─────────────────────┐
                    │   Enterprise WeChat   │
                    │   (企业微信)           │
                    └──────┬──────┬────────┘
                           │      │
              Callback    │      │  Archive Polling
              (Private)   │      │  (Groups)
                           ▼      ▼
                    ┌─────────────────────┐
                    │   Flask App :8080    │
                    │  ┌───────────────┐   │
                    │  │ AI Reply Engine│   │
                    │  │  ┌──────────┐ │   │
                    │  │  │Knowledge │ │   │
                    │  │  │  Base    │ │   │
                    │  │  └────┬─────┘ │   │
                    │  │       ▼       │   │
                    │  │  ┌──────────┐ │   │
                    │  │  │ DeepSeek │ │   │
                    │  │  │   API    │ │   │
                    │  │  └──────────┘ │   │
                    │  └───────────────┘   │
                    │  ┌───────────────┐   │
                    │  │   Scheduler   │   │
                    │  │  ┌──────────┐ │   │
                    │  │  │  Topics  │ │   │
                    │  │  │  Engine  │ │   │
                    │  │  └──────────┘ │   │
                    │  └───────────────┘   │
                    └─────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Enterprise WeChat admin account (企业微信管理员)
- DeepSeek API key ([Get one free](https://platform.deepseek.com/))
- A server with public IP (for WeCom callback)

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/wecom-deepseek-bot.git
cd wecom-deepseek-bot
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required environment variables:

| Variable | Description |
|----------|-------------|
| `WECOM_TOKEN` | WeCom callback verification token |
| `WECOM_AES_KEY` | WeCom message encryption key (43 chars) |
| `WECOM_CORP_ID` | Your WeCom Corp ID |
| `WECOM_SECRET` | App Secret from WeCom admin panel |
| `DEEPSEEK_API_KEY` | DeepSeek API key (starts with `sk-`) |
| `WECOM_ARCHIVE_SECRET` | Session archive secret (optional, for group chat features) |

### 3. Run

```bash
# Development
python app.py

# Production (with gunicorn)
gunicorn -w 4 -b 0.0.0.0:8080 app:app

# Docker
docker build -t wecom-bot .
docker run -p 8080:8080 --env-file .env wecom-bot
```

### 4. Configure WeCom Callback

1. Go to WeCom Admin → Apps → Your App → Receive Message
2. Set callback URL: `https://your-domain.com/callback`
3. Set Token and EncodingAESKey to match your `.env`

---

## 🔌 DeepSeek API Integration

This project showcases best practices for DeepSeek API integration:

### Chat Completion (app.py)

```python
# Core AI reply function
def ai_reply(user_msg, user_name="", user_id=""):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg}
    ]
    
    response = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
        json={
            "model": "deepseek-chat",
            "messages": messages,
            "max_tokens": 150,
            "temperature": 0.7
        }
    )
    return response.json()["choices"][0]["message"]["content"]
```

### Topic Generation (topics.py)

```python
# AI-generated contextual topics
def generate_ai_topic(api_key, prompt_hint=""):
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a bakery operations assistant..."},
            {"role": "user", "content": "Generate an engaging group topic."}
        ],
        "max_tokens": 200,
    }
    # ... API call
```

### Key Design Decisions

1. **Hybrid approach**: Knowledge base for instant FAQ matches + DeepSeek for open-ended conversations
2. **Session context**: Last 6 messages fed as context for coherent multi-turn dialogue
3. **Token efficiency**: `max_tokens=150` for replies, `max_tokens=200` for topics — cost-optimized
4. **Fallback chain**: KB match → DeepSeek → canned response (never leaves user hanging)

---

## 📊 Performance & Cost

| Metric | Value |
|--------|-------|
| Avg reply latency | ~1.2s |
| Daily messages (200 groups) | ~500-800 |
| Token usage per reply | ~100-200 tokens |
| Monthly API cost | ~¥300-500 |
| Concurrent capacity | 500+ connections |

---

## 🛠️ Customization

### Modify Knowledge Base

Edit `KNOWLEDGE_BASE` dict in `app.py`:

```python
KNOWLEDGE_BASE = {
    "your_keyword|synonym": "Your auto-reply text here",
}
```

### Change AI Personality

Edit `SYSTEM_PROMPT` in `app.py`:

```python
SYSTEM_PROMPT = """You are a [your business] customer service AI.
Personality: [describe your brand voice]
Rules:
1. [your rules here]
"""
```

### Add Custom Topics

Edit `TIME_TOPICS` and `ENGAGEMENT_TOPICS` in `topics.py`.

---

## 📝 License

MIT License — see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **DeepSeek API** — for powering the AI conversation engine
- **Enterprise WeChat (企业微信)** — for the messaging platform and APIs
- **Flask** — lightweight and reliable web framework

---

**Built with ❤️ for bakeries everywhere | Powered by DeepSeek API**
