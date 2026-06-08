# 每日 AI 技术速报

这个项目会在每天北京时间 8:30 自动抓取最新 AI 论文、开源项目和官方技术动态，调用 DeepSeek API 生成中文摘要，并发送到指定邮箱。

## 数据来源

- arXiv：`cs.AI`、`cs.LG`、`cs.CL`、`cs.CV`
- GitHub Trending 与 GitHub Search：AI、LLM、Agent、RAG、多模态相关项目
- Papers with Code RSS
- Hugging Face Papers / Models
- OpenAI、Google DeepMind、Anthropic、Meta AI 官方博客 RSS

## 项目结构

```text
.
├── .github/workflows/daily-ai-news.yml
├── .env.example
├── fetch_sources.py
├── summarize.py
├── send_email.py
├── main.py
├── requirements.txt
└── README.md
```

## 本地运行

1. 创建虚拟环境并安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. 创建 `.env`：

```bash
cp .env.example .env
```

3. 编辑 `.env`：

```bash
DEEPSEEK_API_KEY=sk-your-deepseek-api-key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
EMAIL_SENDER=your_email@example.com
EMAIL_PASSWORD=your_email_password_or_smtp_authorization_code
EMAIL_RECEIVER=receiver@example.com
SMTP_SERVER=smtp.example.com
SMTP_PORT=465
GH_TOKEN=
```

4. 手动运行：

```bash
python main.py
```

邮件标题格式为：

```text
【每日AI技术速报】YYYY-MM-DD
```

## 邮箱配置说明

常见 SMTP 配置：

- QQ 邮箱：`SMTP_SERVER=smtp.qq.com`，`SMTP_PORT=465`，密码使用 SMTP 授权码
- 163 邮箱：`SMTP_SERVER=smtp.163.com`，`SMTP_PORT=465`，密码使用授权码
- Gmail：`SMTP_SERVER=smtp.gmail.com`，`SMTP_PORT=465`，密码使用 App Password

不要把真实 `.env` 提交到 Git 仓库。

## GitHub Actions 部署

GitHub Actions 使用 UTC 时间。北京时间是 UTC+8，所以北京时间每天 8:30 对应 UTC 每天 0:30。

本项目的 workflow 使用：

```yaml
cron: "30 0 * * *"
```

部署步骤：

1. 将项目推送到 GitHub 仓库。
2. 打开仓库 `Settings -> Secrets and variables -> Actions`。
3. 添加以下 Repository secrets：

```text
DEEPSEEK_API_KEY
EMAIL_SENDER
EMAIL_PASSWORD
EMAIL_RECEIVER
SMTP_SERVER
SMTP_PORT
GH_TOKEN
```

`GH_TOKEN` 可选。添加后 GitHub Search API 额度更稳定。

可选添加以下 Repository variables：

```text
DEEPSEEK_MODEL
DEEPSEEK_BASE_URL
MAX_PAPERS
MAX_PROJECTS
```

4. 打开 `Actions` 页面，启用 workflow。
5. 可点击 `Run workflow` 手动测试一次。

## 本地 cron 配置

编辑 crontab：

```bash
crontab -e
```

添加以下任务。请把路径替换为你的实际项目路径：

```cron
30 8 * * * cd /path/to/DailyAINews && /path/to/DailyAINews/.venv/bin/python main.py >> /path/to/DailyAINews/cron.log 2>&1
```

如果服务器不是北京时间，建议显式设置时区：

```cron
TZ=Asia/Shanghai
30 8 * * * cd /path/to/DailyAINews && /path/to/DailyAINews/.venv/bin/python main.py >> /path/to/DailyAINews/cron.log 2>&1
```

## 自定义

- `DEEPSEEK_MODEL`：修改总结使用的模型，默认 `deepseek-chat`
- `DEEPSEEK_BASE_URL`：DeepSeek OpenAI-compatible API 地址，默认 `https://api.deepseek.com`
- `MAX_PAPERS`：控制论文抓取数量，默认 `20`
- `MAX_PROJECTS`：控制项目抓取数量，默认 `10`

抓取逻辑在 `fetch_sources.py`，总结提示词在 `summarize.py`，邮件样式和 SMTP 发送逻辑在 `send_email.py`。
