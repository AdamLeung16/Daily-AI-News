from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from openai import OpenAI


SYSTEM_PROMPT = """你是资深 AI 技术分析师，负责把当天抓取到的论文、开源项目和技术动态整理成中文邮件。
要求：
1. 只基于输入资料总结，不要编造链接、stars 或不存在的结论。
2. 内容要面向 AI 工程师、研究员和技术管理者，简洁但信息密度高。
3. 重点突出 LLM、Agent、RAG、多模态、推理、训练/推理效率、模型产品化。
4. 对每篇重点论文说明核心贡献和适合关注的原因。
5. 输出适合邮件阅读的简洁 Markdown，严格使用用户要求的栏目结构。
6. 不要输出 LaTeX、表格、代码块、脚注或复杂嵌套列表。
7. 链接必须使用 Markdown 链接格式：[标题](https://example.com)，不要裸写成 [url](url) 之外的异常格式。
8. 小标题最多使用二级标题，不要使用三级及更深标题。
"""


def _compact_sources(sources: dict[str, Any]) -> str:
    payload = {
        "papers": sources.get("papers", [])[:30],
        "projects": sources.get("projects", [])[:20],
        "updates": sources.get("updates", [])[:20],
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

    user_prompt = f"""请根据以下抓取数据，生成 {report_date.isoformat()} 的中文 AI 技术日报邮件正文。

请严格包含这些栏目：

# 今日 AI 技术总览
# 重点论文 5 篇
每篇包含：标题、链接、核心贡献、适合关注的原因
# 热门开源项目 3 个
每个包含：GitHub 链接、stars、主要功能、应用场景
# 大模型 / Agent / RAG / 多模态 相关技术动态
# 今日最值得深入阅读的 1–2 个推荐

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
