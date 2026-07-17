from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from openai import OpenAI


SYSTEM_PROMPT = """你是资深 AI 产业与技术分析师，负责把当天抓取到的大公司官方技术动态和 AI 行业热点新闻整理成中文邮件。
要求：
1. 只基于输入资料总结，不要编造链接、stars 或不存在的结论。
2. 内容要面向 AI 工程师、产品负责人、创业者、投资/战略观察者，简洁但信息密度高。
3. 重点关注 OpenAI、Google DeepMind/Google、Anthropic、Meta、Microsoft、NVIDIA、Amazon/AWS、Apple，以及阿里 Qwen/通义千问、DeepSeek、Kimi/月之暗面、豆包、智谱、MiniMax、百度文心、腾讯混元等公司的模型、产品、平台、芯片、Agent、多模态、企业 AI 和安全治理动态。
4. 优先选择“大公司推出的新技术成果/产品能力/突破动态”和“当天 AI 圈热点新闻”，不要把研究论文或 GitHub 热门项目作为固定栏目。
5. 输出适合邮件阅读的简洁 Markdown，严格使用用户要求的栏目结构。
6. 不要输出 LaTeX、表格、代码块、脚注或复杂嵌套列表。
7. 链接必须使用 Markdown 链接格式：[标题](https://example.com)，不要裸写成 [url](url) 之外的异常格式。
8. 小标题最多使用二级标题，不要使用三级及更深标题。
9. 每条动态都要说明“发生了什么”和“为什么值得关注”，避免只罗列标题。
"""


def _compact_sources(sources: dict[str, Any]) -> str:
    payload = {
        "company_updates": sources.get("company_updates", [])[:36],
        "hot_news": sources.get("hot_news", [])[:30],
        "generated_at": sources.get("generated_at"),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def summarize_daily_news(sources: dict[str, Any], report_date: date | None = None) -> str:
    client = OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    report_date = report_date or date.today()

    user_prompt = f"""请根据以下抓取数据，生成 {report_date.isoformat()} 的中文 AI 技术与产业日报邮件正文。

请严格包含这些栏目：

# 今日 AI 技术总览
# 大公司技术成果与突破动态
选 6–10 条，覆盖 OpenAI、Google/DeepMind、Anthropic、Meta、Microsoft、NVIDIA、Amazon/AWS、Apple、阿里 Qwen、DeepSeek、Kimi/月之暗面等国内外公司。每条包含：公司/来源、标题链接、发生了什么、为什么重要。
# 今日 AI 热点新闻
选 5–8 条，覆盖产品、模型、资本、监管、安全、产业竞争、应用落地等。每条包含：标题链接、核心事实、影响判断。
# 大模型 / Agent / 多模态 / AI 基础设施趋势
基于今日动态提炼 3–5 个趋势观察。
# 今日最值得关注的 1–2 件事
给出推荐理由和原文链接。

抓取数据：
{_compact_sources(sources)}
"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )
    content = response.choices[0].message.content
    return (content or "").strip()
