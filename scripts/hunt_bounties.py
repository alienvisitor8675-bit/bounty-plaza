#!/usr/bin/env python3
"""hunt_bounties.py — 自动搜索 GitHub 真实赏金任务并发布到 bounty-plaza"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

# GitHub Config
GH_TOKEN = os.environ.get("GH_TOKEN", "")
REPO = "zhangjiayang6835-cyber/bounty-plaza"
SEARCH_QUERY = "label:bounty state:open is:issue sort:created"

# Regex: Matches currency symbols or raw numbers + keywords
REAL_MONEY = re.compile(
    r"\$\s?[\d,]+(?:\.\d{1,2})?|"
    r"\d+[\s,]*(?:USDT|USDC|DAI|ETH|BTC|USD|BUSD)|"
    r"(?:bounty\s*(?::|of)?\s*)?\$\s*(\d[\d,]*)",
    re.IGNORECASE
)

# Regex: Matches common 'virtual' keywords to filter out generic labels
VIRTUAL_KEYWORDS = re.compile(
    r"token|point|credit|xp\b|reputation|rank|level\b|badge|achievement",
    re.IGNORECASE
)

def extract_amounts(text):
    """从文本中提取所有符合货币模式的数字"""
    amounts = []
    if not text:
        return amounts

    # 1. Look for $ prefixed numbers (e.g. $50, $500)
    for m in re.finditer(r"\$\s?(\d[\d,]*)", text):
        try:
            val = int(m.group(1).replace(',', ''))
            if val:
                amounts.append(val)
        except ValueError:
            pass

    # 2. Look for numbers with explicit currency names
    for m in re.finditer(r'(\d+)\s*(?:USDT|USDC|DAI|ETH|BTC|USD|BUSD)', text, re.IGNORECASE):
        try:
            val = int(m.group(1))
            if val and val not in amounts:
                amounts.append(val)
        except ValueError:
            pass
    return amounts

def is_real_money(item):
    """判断是否为真实赏金（非纯虚拟积分）"""
    if not item:
        return False
    
    # Combine Title and Body
    body = (item.get("title", "") + "\n" + (item.get("body", "") or ""))
    
    # 1. Must contain some 'money' pattern
    if not REAL_MONEY.search(body):
        return False
    
    # 2. Filter out 'virtual' keywords if they dominate the text
    # This logic assumes that if 'token' is mentioned, there must be real money too
    # to count as a 'Real' bounty
    if VIRTUAL_KEYWORDS.search(body):
        # Check if the money appears in the first 200 chars (avoiding body pollution)
        if not REAL_MONEY.search(body[:200]):
            return False
            
    return True

def get_existing_sources():
    """获取 bounty-plaza 已有的 source_url (for avoiding duplicates)"""
    if not GH_TOKEN:
        return set()
    
    url = f"https://api.github.com/repos/{REPO}/issues?labels=bounty&state=open&per_page=100"
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"token {GH_TOKEN}"})
        data = json.loads(urllib.request.urlopen(req).read())
        sources = set()
        for issue in data:
            url_text = f"{issue.get('title', '')}\n{issue.get('body', '')}"
            m = re.search(r"(?:source|original)[:\s]+(https?://[^\s\n]+)", url_text, re.IGNORECASE)
            if m:
                sources.add(m.group(1).rstrip("/"))
        return sources
    except Exception as e:
        print(f"Warning: get_existing_sources failed: {e}", file=sys.stderr)
        return set()

def create_issue(item, amount):
    """向 bounty-plaza 创建新 Issue"""
    title = f"[Bounty] {item['title'][:80]}"
    
    body_template = f"""### Platform
GitHub

### Source URL
{item['html_url']}

### Description
{item.get('title')}

{item.get('body', '')[:2000]}

### Coin Reward
{int(amount * 1.25)} coins

### Real Reward
${{amount:,}}

### Difficulty
Medium

### Claim Method
Comment `/claim` to lock the task for 24h

### Instructions
> Check [REWARD_POLICY.md](REWARD_POLICY.md) for redemption rules
"""
    
    url = f"https://api.github.com/repos/{REPO}/issues"
    
    try:
        # Ensure body is UTF-8 encoded
        data = json.dumps({
            "title": title[:100],
            "body": body_template,
            "labels": ["bounty", "real"]
        }).encode("utf-8")
        
        req = urllib.request.Request(
            url, 
            data=data, 
            method="POST",
            headers={"Authorization": f"token {GH_TOKEN}", "Content-Type": "application/json"}
        )
        resp = json.loads(urllib.request.urlopen(req).read())
        
        return {
            "id": resp.get("number"), 
            "title": resp.get("title"), 
            "html_url": resp.get("html_url")
        }
    except urllib.error.HTTPError as e:
        if e.code == 422: # Unprocessable (Duplicate title?)
            return {"error": "Potential duplicate", "url": item['html_url']}
        return {"error": str(e)}

def main():
    """Entry point"""
    if not GH_TOKEN:
        print("FATAL: Set GH_TOKEN environment variable", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {REPO} for real bounty tasks...")
    
    # Calculate 'since' date
    now = datetime.now(timezone.utc)
    since = (now - __import__("datetime").timedelta(days=30)).strftime("%Y-%m-%d")
    
    q = f"{SEARCH_QUERY} created:>{since}"
    
    url = f"https://api.github.com/search/issues?q={urllib.request.quote(q)}&sort=created&order=desc&per_page=50"
    print(f"Querying URL: {url}")
    
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"token {GH_TOKEN}"})
        data = json.loads(urllib.request.urlopen(req).read())
        items = data.get("items", [])
        
        if not items:
            print("No items found.")
            return

        for item in items:
            body = (item.get("title", "") + "\n" + (item.get("body", "") or ""))
            
            if is_real_money(item):
                amounts = extract_amounts(body)
                if amounts:
                    # Determine which amount to pick (max is usually safest)
                    amount = max(amounts) if amounts else 1
                    
                    result = create_issue(item, amount)
                    
                    if result and "error" not in result:
                        print(f"Created Issue #{result['id']} for amount: ${amount}")
                        print(f"  URL: {result['html_url']}")
                    else:
                        print(f"Failed to create for #{item.get('number')}: {result}")
                        
            else:
                print(f"Skipped #{item.get('number')} - Not enough money: {body[:100]}")

    except Exception as e:
        print(f"Error during search: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()