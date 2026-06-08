from __future__ import annotations

import os
import re
import smtplib
from html import escape
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _format_inline_markdown(text: str) -> str:
    escaped = escape(text)

    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
        escaped,
    )
    escaped = re.sub(
        r"(?<!href=\")(?<!\">)(https?://[^\s<]+)",
        r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>',
        escaped,
    )
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\$\$?([^$]+)\$\$?", r"\1", escaped)
    return escaped


def markdown_to_plain_text(markdown: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1：\2", markdown)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\$\$?([^$]+)\$\$?", r"\1", text)
    return text.strip()


def markdown_to_email_html(markdown: str) -> str:
    html_lines: list[str] = []
    list_type: str | None = None

    def close_list() -> None:
        nonlocal list_type
        if list_type:
            html_lines.append(f"</{list_type}>")
            list_type = None

    def open_list(tag: str) -> None:
        nonlocal list_type
        if list_type != tag:
            close_list()
            html_lines.append(f"<{tag}>")
            list_type = tag

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            close_list()
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        unordered_match = re.match(r"^[-*]\s+(.+)$", line)
        ordered_match = re.match(r"^\d+\.\s+(.+)$", line)

        if heading_match:
            close_list()
            level = min(len(heading_match.group(1)), 3)
            html_lines.append(f"<h{level}>{_format_inline_markdown(heading_match.group(2))}</h{level}>")
        elif unordered_match:
            open_list("ul")
            html_lines.append(f"<li>{_format_inline_markdown(unordered_match.group(1))}</li>")
        elif ordered_match:
            open_list("ol")
            html_lines.append(f"<li>{_format_inline_markdown(ordered_match.group(1))}</li>")
        else:
            close_list()
            html_lines.append(f"<p>{_format_inline_markdown(line)}</p>")
    close_list()

    body = "\n".join(html_lines)
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ margin: 0; padding: 0; background: #f6f7f9; color: #111827; }}
    .container {{ max-width: 760px; margin: 0 auto; padding: 28px 20px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; line-height: 1.72; }}
    .card {{ background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 28px; }}
    h1 {{ font-size: 22px; line-height: 1.35; margin: 0 0 18px; padding-bottom: 10px; border-bottom: 1px solid #e5e7eb; }}
    h2 {{ font-size: 18px; line-height: 1.45; margin: 26px 0 10px; color: #0f172a; }}
    h3 {{ font-size: 16px; line-height: 1.45; margin: 20px 0 8px; color: #1f2937; }}
    p {{ margin: 8px 0 12px; font-size: 15px; }}
    ul, ol {{ margin: 8px 0 14px 22px; padding: 0; }}
    li {{ margin: 6px 0; font-size: 15px; }}
    a {{ color: #2563eb; text-decoration: none; word-break: break-word; }}
    strong {{ font-weight: 700; color: #111827; }}
    code {{ background: #f3f4f6; border-radius: 4px; padding: 1px 4px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="card">
      {body}
    </div>
  </div>
</body>
</html>"""


def send_email(subject: str, markdown_body: str) -> None:
    sender = os.environ["EMAIL_SENDER"]
    password = os.environ["EMAIL_PASSWORD"]
    receiver = os.environ["EMAIL_RECEIVER"]
    smtp_server = os.environ["SMTP_SERVER"]
    smtp_port = int(os.getenv("SMTP_PORT", "465"))

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = receiver
    message.attach(MIMEText(markdown_to_plain_text(markdown_body), "plain", "utf-8"))
    message.attach(MIMEText(markdown_to_email_html(markdown_body), "html", "utf-8"))

    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
                server.login(sender, password)
                server.sendmail(sender, [receiver], message.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender, password)
                server.sendmail(sender, [receiver], message.as_string())
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError(
            "SMTP authentication failed. Check EMAIL_SENDER and EMAIL_PASSWORD. "
            "For Gmail, use a Google App Password instead of your normal account password."
        ) from exc
