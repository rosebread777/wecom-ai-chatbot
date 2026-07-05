#!/usr/bin/env python3
"""
WeCom AI Group Chat Topic Engine
=================================
Generates scheduled push topics and random engagement hooks
for keeping customer groups active and driving conversions.
"""
import json, random, urllib.request

# ====== Time-based Topic Pools ======
TIME_TOPICS = {
    "breakfast": [
        "🌅 Good morning! Fresh croissants just out of the oven — grab one with coffee ☕️!",
        "🍞 Morning! Hot soft European bread right here, stop by on your way?",
        "🥐 Rush hour warriors — grab breakfast at our store! Sea salt roll + latte only ¥25!",
        "☀️ A new day starts with good bread — matcha red bean toast fresh out today!",
    ],
    "lunch": [
        "🍱 Lunch break! How about planning your afternoon tea? Matcha lava cake available today~",
        "☕ Dessert time after lunch! Chocolate Mango House ¥19, Blueberry House ¥19 — 3.0 new arrivals!",
        "🥪 Done with lunch? Come grab a latte with croissant, a working person's little joy 💪",
    ],
    "afternoon": [
        "☕️ 3 PM! Need a coffee pick-me-up? ABC afternoon tea sets now available~",
        "🍰 Afternoon tea time! Matcha Lava Cake ¥28, cut it open and the matcha sauce flows — group members are raving!",
        "🧁 Lazy afternoon — a mini cream cake + latte, this is the life~",
    ],
    "evening": [
        "🌙 After dinner — stock up on tomorrow's breakfast? Soft Euro, croissants, toast — save morning time!",
        "🥖 Good evening! If tomorrow's breakfast isn't sorted yet, order in the group and pick up in the morning!",
        "🍞 Bedtime recommendation: our milk soft cake is a signature item, come try it tomorrow morning?",
    ],
    "weekend": [
        "🎉 Happy weekend! Sleep in, then swing by for coffee and cake~",
        "📷 Weekend shop tour! Our 3.0 new products are out — Instagram-worthy photos!",
    ],
}

# ====== Engagement Hooks (for dead group revival) ======
ENGAGEMENT_TOPICS = [
    "Moms in the group — stocking up bread and milk for the kids this summer? So convenient and nutritious!",
    "Anyone else need coffee every morning just to boot up? ☕️",
    "Summer heat — iced americano or iced latte? I'm voting latte!",
    "Any matcha fans in the group? 🙋 Our matcha lava cake is really something!",
    "What songs are you listening to on your commute? Share one with me 🎵",
    "Honestly, do you prefer savory or sweet sea salt rolls? Let's battle in the comments!",
]

# ====== Conversion Hooks (3+ chat rounds → add WeChat + coupon) ======
CONVERSION_HOOKS = [
    "Add me on WeChat and I'll send you a ¥5 coupon! We're having such a great chat!",
    "You're hilarious haha, let's be friends — I'll notify you first about new products!",
    "Love chatting with you! Add my WeChat, I'll send you a croissant coupon~",
    "Can't share coupons in the group — add me on WeChat for your exclusive perk!",
]


def get_topic_by_time(hour, weekday):
    """Return appropriate topic based on time and day of week"""
    if weekday >= 5:  # Weekend
        pool = TIME_TOPICS["weekend"] + TIME_TOPICS.get("breakfast", [])
    elif 6 <= hour < 8:
        pool = TIME_TOPICS["breakfast"]
    elif 11 <= hour < 13:
        pool = TIME_TOPICS["lunch"]
    elif 14 <= hour < 16:
        pool = TIME_TOPICS["afternoon"]
    elif 18 <= hour < 21:
        pool = TIME_TOPICS["evening"]
    else:
        pool = TIME_TOPICS["afternoon"]
    return random.choice(pool)


def get_engagement_topic():
    """Random engagement topic for reviving inactive groups"""
    return random.choice(ENGAGEMENT_TOPICS)


def get_conversion_hook():
    """Random conversion message (add WeChat + coupon)"""
    return random.choice(CONVERSION_HOOKS)


def generate_ai_topic(api_key, prompt_hint=""):
    """
    Generate a contextual topic using DeepSeek API (fallback).
    This demonstrates the core DeepSeek API integration pattern.
    """
    base = "You are a bakery's community operations assistant. Generate a friendly group message."
    rules = "Rules: ① Under 30 words ② Conversational with emojis ③ No politics/sensitive topics ④ Only bakery/food/life/weather/trending topics."
    context = f"Context: {prompt_hint}" if prompt_hint else "Generate a spontaneous topic."

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": base + rules},
            {"role": "user", "content": context},
        ],
        "max_tokens": 200,
    }
    try:
        req = urllib.request.Request(
            "https://api.deepseek.com/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        return resp["choices"][0]["message"]["content"].strip()
    except Exception:
        return None
