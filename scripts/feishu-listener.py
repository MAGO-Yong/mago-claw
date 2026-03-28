#!/usr/bin/env python3
"""
飞书群消息监听器
定时检查"牛马-MAGO通讯室"群的新消息
"""

import requests
import json
import time
from datetime import datetime

APP_ID = "cli_a92452ddae385bde"
APP_SECRET = "OsOP1MZKyS0oCTuUagngNgsQHOQSfApa"
CHAT_ID = "oc_fa5970fba6c6d743744b67a7b7c99f52"

# 状态文件（记录上次读取的消息ID）
STATE_FILE = "/home/node/.openclaw/workspace/.feishu-state"

def get_token():
    """获取飞书token"""
    response = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET}
    )
    return response.json()["tenant_access_token"]

def get_messages(token, limit=20):
    """获取群消息"""
    url = f"https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=chat_id&container_id={CHAT_ID}&page_size={limit}"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get("data", {}).get("items", [])
        else:
            print(f"❌ 获取消息失败: {response.status_code}")
            print(response.text)
            return []
    except Exception as e:
        print(f"❌ 错误: {e}")
        return []

def get_last_seen_msg_id():
    """获取上次读取的消息ID"""
    try:
        with open(STATE_FILE, 'r') as f:
            return f.read().strip()
    except:
        return None

def save_last_seen_msg_id(msg_id):
    """保存最后读取的消息ID"""
    try:
        with open(STATE_FILE, 'w') as f:
            f.write(msg_id)
    except:
        pass

def process_messages(messages):
    """处理新消息"""
    if not messages:
        print(f"[{datetime.now().isoformat()}] 没有新消息")
        return
    
    last_seen = get_last_seen_msg_id()
    new_messages = []
    
    for msg in messages:
        msg_id = msg.get("message_id")
        if last_seen and msg_id == last_seen:
            break
        new_messages.append(msg)
    
    if new_messages:
        # 保存最新的消息ID
        save_last_seen_msg_id(new_messages[0].get("message_id"))
        
        print(f"\n[{datetime.now().isoformat()}] 发现 {len(new_messages)} 条新消息:")
        for msg in reversed(new_messages):
            msg_id = msg.get("message_id")
            sender = msg.get("sender", {}).get("id", "unknown")
            msg_type = msg.get("msg_type")
            
            if msg_type == "text":
                content = json.loads(msg.get("body", {}).get("content", "{}"))
                text = content.get("text", "")
                print(f"  [{msg_id[:20]}...] {sender}: {text[:100]}")
            else:
                print(f"  [{msg_id[:20]}...] {sender}: [{msg_type}]")
    else:
        print(f"[{datetime.now().isoformat()}] 没有新消息")

def send_message(token, text):
    """发送消息到群"""
    url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    payload = {
        "receive_id": CHAT_ID,
        "msg_type": "text",
        "content": json.dumps({"text": text})
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ 消息已发送")
            return True
        else:
            print(f"❌ 发送失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False

def main():
    """主循环"""
    print("🚀 飞书群消息监听器启动")
    print(f"群ID: {CHAT_ID}")
    print("按 Ctrl+C 停止\n")
    
    try:
        while True:
            token = get_token()
            messages = get_messages(token)
            process_messages(messages)
            
            # 每30秒检查一次
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n⏹️  监听器已停止")

if __name__ == "__main__":
    main()
