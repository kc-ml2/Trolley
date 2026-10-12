"""Key-first invitation with plain-text fallback and escaped HTML values."""

from html import escape
from urllib.parse import urljoin


def invitation(secret: str, onboarding_url: str) -> tuple[str, str, str]:
    # Keep the existing invitation API; the guide and MCP share the same base path.
    mcp_url = urljoin(onboarding_url, "mcp/")
    subject = "Trolley — your API key"
    safety = "Enter this key in your client’s secret settings—not in chat."
    privacy = "This key grants access to your account. Do not forward it or commit it to a repository."
    body = f"""Welcome to Trolley
Use your team's data tools with your AI client.

Your API key (Bearer authentication):
{secret}

MCP server URL:
{mcp_url}

Add the server URL and API key in your AI client's MCP connection settings.
{safety}
{privacy}
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
<h2 style="font-size:16px;margin-top:24px;">Your API key</h2>
<div style="padding:16px;background:#edf3ff;border:1px solid #dce6ff;border-radius:8px;
font-family:monospace;font-size:15px;word-break:break-all;">{escape(secret)}</div>
<p style="font-size:12px;color:#536176;">Bearer authentication</p>
<h2 style="font-size:16px;margin-top:24px;">MCP server URL</h2>
<div style="padding:14px;background:#f5f7fa;border-radius:8px;font-family:monospace;
word-break:break-all;">{escape(mcp_url)}</div>
<p style="color:#536176;line-height:1.6;">Add the server URL and API key in your AI client's
MCP connection settings.</p>
<p style="font-size:12px;color:#536176;line-height:1.6;border-top:1px solid #e1e6ee;
padding-top:16px;">{escape(safety)}<br>{escape(privacy)}</p>
</td></tr></table></td></tr></table></body></html>"""
    return subject, body, html
