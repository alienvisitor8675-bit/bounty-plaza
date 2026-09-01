#!/usr/bin/env python3
"""hunt_bounties.py — 自动索引 GitHub 真实赏金任务并发布到 bounty-plaza"""

import json, os, re, sys, urllib.request
from datetime import datetime, timezone

GH_TOKEN = os.environ.get("GH_TOKEN", "")
REPO = "zhangjiayang6835-cyber/bounty-plaza"
SEARCH_QUERY = "label:bounty state:open is:issue sort:created -user:zhangjiayang6835-cyber"

# 真实赏金正则
# Pattern 1: $100, $1,000
# Pattern 2: 100 USDT, 1500 Coins
# Pattern 3: bounty $500
REAL_MONEY = re.compile(
    r"\$\s?[\d,]+(?:\.\d{1,2})?|"  # Pattern 1: $amount (e.g. $1,200)
    r"\d+[\s,]*(?:USDT|USDC|DAI|ETH|BTC|USD|BUSD|COINS|TOKENS)?"  # Pattern 2: amount + optional word
    r"bounty\s*(?::|of)?\s*\$\s*\d+",  # Pattern 3: bounty $amount
    re.IGNORECASE | re.VERBOSE
)

# 虚拟代币关键词 (filtering out fake points)
VIRTUAL_KEYWORDS = re.compile(
    r"token|point|credit|xp\b|reputation|rank|level\b|badge|achievement",
    re.IGNORECASE
)

def extract_amounts(text):
    """从文本中获取所有符合钱模式的最低金额"""
    amounts = []
    
    # Pattern 1: $100, $1,000
    for m in re.finditer(r"\$\s?(\d[\d,]*)", text):
        try:
            amounts.append(int(m.group(1).replace(',', '')))
        except ValueError:
            pass
            
    # Pattern 2: 100 USDT, 1500 Coins
    for m in re.finditer(r"(\d+)\s*(?:USDT|USDC|DAI|ETH|BTC|USD|BUSD|COINS|TOKENS|DOLLAR)?", text, re.IGNORECASE):
        try:
            val = int(m.group(1))
            if val > 0:
                amounts.append(val)
        except ValueError:
            pass
            
    # Pattern 3: bounty $500
    for m in re.finditer(r"bounty\s*(?::|of)?\s*\$\s*(\d[\d,]*)", text, re.IGNORECASE):
        try:
            val = int(m.group(1).replace(',', ''))
            if val > 0:
                amounts.append(val)
        except ValueError:
            pass
    return amounts

def search_github():
    """索引最近 30 天的 bounty Issue"""
    since = (datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    # Construct query string safely
    q = f"{SEARCH_QUERY} created:>2026-05-20"
    url = f"https://api.github.com/search/issues?q={urllib.request.quote(q)}&sort=created&order=desc&per_page=50"
    req = urllib.request.Request(url, headers={"Authorization": f"token {GH_TOKEN}"})
    try:
        data = json.loads(urllib.request.urlopen(req).read())
        return data.get("items", [])
    except urllib.error.URLError as e:
        print(f"FATAL: Error fetching GitHub: {e}", file=sys.stderr)
        return []

def is_real_money(item):
    body = (item.get("title", "") + "\n" + (item.get("body") or ""))
    
    # Must contain a real money pattern somewhere
    if not REAL_MONEY.search(body):
        return False
        
    # Filter out virtual tokens (e.g., 100 points) if real money isn't in the first 200 chars
    if VIRTUAL_KEYWORDS.search(body) and not REAL_MONEY.search(body[:200]):
        return False
        
    # Parse actual amounts
    amounts = extract_amounts(body)
    if not amounts or all(a == 0 for a in amounts):
        return False
        
    return max(amounts) >= 25

def get_existing_sources():
    """获取 bounty-plaza 已有的 source_url"""
    url = f"https://api.github.com/repos/{REPO}/issues?labels=bounty&state=open&per_page=100"
    req = urllib.request.Request(url, headers={"Authorization": f"token {GH_TOKEN}"})
    try:
        data = json.loads(urllib.request.urlopen(req).read())
        sources = set()
        for issue in data:
            body = issue.get("body", "")
            # Matches either Chinese '原始链接' or 'source.url'
            m = re.search(r"(?:原始链接|source.?url)[:\s]+(https?://[^\s\n]+)", body, re.IGNORECASE)
            if m:
                sources.add(m.group(1).rstrip("/"))
        return sources
    except urllib.error.URLError as e:
        print(f"WARNING: Error fetching existing sources: {e}", file=sys.stderr)
        return sources

def create_issue(item, amount):
    title = f"[Bounty] {item['title'][:80]}"
    
    # Format the amount nicely in the body
    formatted_amount = f"${amount:,}" if isinstance(amount, (int, float)) else str(amount)

    body_template = f"""### 赏金平台 / Platform
GitHub

### 原始链接 / Source URL
{item['html_url']}

### 漏洞描述 / Description
{item.get('title', '')}

{item.get('body', '')[:2000]}

### 积分币奖励 / Coin Reward
{int(amount * 1.25)} coins

### 真实赏金（USD）/ Real Reward
{formatted_amount}

### 难度 / Difficulty
Medium

### 认领方式
评论 `/claim` 锁定任务 24h

### 兑换说明
> 查看 [REWARD_POLICY.md](REWARD_POLICY.md) 了解兑换规则
"""
        
    url = f"https://api.github.com/repos/{REPO}/issues"
    data = json.dumps({
        "title": title[:100],
        "body": body_template,
        "labels": ["bounty", "real"]
    })
    req = urllib.request.Request(url, data=data, method="POST",
        headers={"Authorization": f"token {GH_TOKEN}", "Content-Type": "application/json"})
    try:
        result = json.loads(urllib.request.urlopen(req).read())
        return result.get("number", "?")
    except urllib.error.HTTPError as e:
        # If 409 Conflict (already open), or 422 (bad request), handle gracefully
        if e.code == 409:
            print(f"WARNING: Issue might exist: {item['title']}", file=sys.stderr)
            return "?"
        raise

def main():
    items = search_github()
    existing = get_existing_sources()
    
    for item in items:
        # Basic title filter to avoid duplicate titles
        if item.get("title") in existing and "bounty" in item.get("labels", []):
            continue
            
        if is_real_money(item):
            body = (item.get("title", "") + "\n" + (item.get("body") or ""))
            # Get parsed amount
            parsed_amount = max(extract_amounts(body)) if extract_amounts(body) else 100
            
            issue_num = create_issue(item, parsed_amount)
            print(f"Posted #{issue_num} for: {item['title']}")
            
    # Optionally, handle 'sources' logic here if needed

if __name__ == "__main__":
    main()