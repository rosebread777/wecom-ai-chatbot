#!/usr/bin/env python3
"""
WeCom AI Group Chat Scheduler
==============================
Manages timed topic pushing, dead group detection & revival,
and time-window control for customer engagement.
"""
import json, time, urllib.request, datetime, random


class GroupScheduler:
    """
    Orchestrates group chat operations:
    - Timed topic pushes (breakfast/lunch/afternoon tea/evening)
    - Dead group detection (30min inactivity threshold)
    - Conversion tracking (3+ chat rounds → add WeChat + coupon)
    """

    def __init__(self, topics_module, access_token_func, send_func):
        self.topics = topics_module
        self.get_token = access_token_func
        self.send_msg = send_func
        self.group_timers = {}
        self.active_hours = (6, 23)  # 6 AM to 11 PM

    def is_active_hours(self):
        """Check if we're within active messaging hours"""
        h = datetime.datetime.now().hour
        return self.active_hours[0] <= h < self.active_hours[1]

    def record_human_message(self, group_id):
        """Log timestamp of latest human message in group"""
        self.group_timers[group_id] = {
            **self.group_timers.get(group_id, {}),
            "last_human_msg": time.time(),
        }

    def record_bot_message(self, group_id):
        """Log timestamp of latest bot message in group"""
        self.group_timers[group_id] = {
            **self.group_timers.get(group_id, {}),
            "last_bot_msg": time.time(),
        }

    def should_push_timed_topic(self, group_id, current_hour):
        """Check if timed topic should be pushed (once per slot per group)"""
        g = self.group_timers.get(group_id, {})
        last_topic_hour = g.get("topic_hour", -1)

        # Time slots: breakfast 7-8 / lunch 11-12 / tea 15-16 / evening 19-20
        for slot_start, slot_end in [(7, 9), (11, 13), (15, 17), (19, 21)]:
            if slot_start <= current_hour < slot_end:
                if last_topic_hour < slot_start:
                    return True, self.topics.get_topic_by_time(
                        current_hour, datetime.datetime.now().weekday()
                    )
        return False, None

    def mark_topic_sent(self, group_id, current_hour):
        """Mark current time slot as pushed"""
        self.group_timers[group_id] = {
            **self.group_timers.get(group_id, {}),
            "topic_hour": current_hour,
        }

    def should_revive(self, group_id):
        """
        Check if group needs revival:
        - >30min since last human message
        - >30min since last bot message (avoid spam)
        """
        g = self.group_timers.get(group_id, {})
        now = time.time()
        last_human = g.get("last_human_msg", 0)
        last_bot = g.get("last_bot_msg", 0)

        if now - last_human < 1800:
            return False
        if now - last_bot < 1800:
            return False
        return True

    def get_revive_topic(self):
        """Get a random engagement topic for revival"""
        return self.topics.get_engagement_topic()

    def should_send_conversion(self, user_id, reply_count):
        """Check if user qualifies for conversion message (3+ interactions)"""
        return reply_count >= 3

    def get_conversion_msg(self):
        """Get a random conversion hook"""
        return self.topics.get_conversion_hook()

    def send_to_group(self, group_id, content):
        """Send message to external WeCom group via appchat API"""
        token = self.get_token()
        if not token:
            return False
        body = {
            "chatid": group_id,
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
            if resp.get("errcode") == 0:
                self.record_bot_message(group_id)
                return True
        except Exception as e:
            print(f"[Scheduler] Group send failed: {e}")
        return False

    def send_private(self, user_id, content):
        """Send private message to user"""
        return self.send_msg(user_id, content)
