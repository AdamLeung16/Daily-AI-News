from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from fetch_sources import collect_sources
from send_email import send_email
from summarize import summarize_daily_news


def main() -> None:
    load_dotenv()
    beijing_now = datetime.now(ZoneInfo("Asia/Shanghai"))
    report_date = beijing_now.date()

    sources = collect_sources()
    body = summarize_daily_news(sources, report_date=report_date)
    subject = f"【每日AI技术速报】{report_date.isoformat()}"
    send_email(subject, body)
    print(f"Sent daily AI news email: {subject}")


if __name__ == "__main__":
    main()
