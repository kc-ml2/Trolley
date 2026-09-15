"""Compact invitation with plain-text fallback and escaped HTML values."""

from html import escape


def invitation(secret: str, onboarding_url: str) -> tuple[str, str, str]:
    subject = "Trolley — connect your AI client"
    prompt = f"Read {onboarding_url} and help me connect to Trolley."
    safety = "Enter this key in your client’s secret settings—not in chat."
    question = "Trolley, what can you do for me right now?"
    body = f"""Welcome to Trolley
Use your team's data tools with your AI client.

1. Copy this into your agent:
{prompt}

2. Your API key (Bearer authentication):
{secret}
{safety}

3. Reconnect, then ask:
{question}

Connection guide: {onboarding_url}
"""
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#f3f5f8;color:#172033;font-family:Arial,Helvetica,sans-serif;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0"
style="max-width:560px;background:#fff;border:1px solid #e1e6ee;border-radius:12px;">
<tr><td style="padding:28px;">
<p style="color:#3464de;font-weight:bold;letter-spacing:2px;margin:0 0 12px;">TROLLEY</p>
<h1 style="font-size:24px;margin:0 0 12px;">Welcome to Trolley</h1>
<p style="color:#536176;line-height:1.5;">Use your team's data tools with your AI client.</p>
<h2 style="font-size:16px;margin-top:24px;">1. Copy this into your agent</h2>
<div style="padding:14px;background:#edf3ff;border-radius:8px;line-height:1.6;
overflow-wrap:anywhere;">{escape(prompt)}</div>
<h2 style="font-size:16px;margin-top:24px;">2. Your API key</h2>
<div style="padding:14px;background:#f5f7fa;border-radius:8px;font-family:monospace;
word-break:break-all;">{escape(secret)}</div>
<p style="font-size:12px;color:#536176;line-height:1.6;">
{escape(safety)}</p>
<h2 style="font-size:16px;margin-top:24px;">3. Reconnect, then ask</h2>
<p style="line-height:1.5;">{escape(question)}</p>
<a href="{escape(onboarding_url, quote=True)}" style="display:inline-block;margin-top:12px;
background:#3464de;color:#fff;text-decoration:none;padding:12px 18px;
border-radius:8px;">Connection guide</a>
</td></tr></table></td></tr></table></body></html>"""
    return subject, body, html
