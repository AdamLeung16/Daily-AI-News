# 每日 AI 技术速报

这个项目会在每天北京时间 7:47 自动抓取大公司最新 AI 技术成果、产品发布、突破动态和 AI 行业热点新闻，调用 DeepSeek API 生成中文摘要，并发送到指定邮箱。

## 数据来源

- 大公司官方动态：OpenAI、Google DeepMind、Google AI、Anthropic、Meta AI、Microsoft AI、NVIDIA AI、AWS Machine Learning、Apple Machine Learning、阿里 Qwen/通义千问、DeepSeek、Kimi/月之暗面等
- AI 热点新闻：Google News AI、Google News China AI、TechCrunch AI、The Verge AI、VentureBeat AI、MIT Technology Review
- 重点关注：大模型、Agent、多模态、AI 基础设施、芯片、企业 AI、安全治理、产业竞争和应用落地

## 邮件内容

- 今日 AI 技术总览
- 大公司技术成果与突破动态
- 今日 AI 热点新闻
- 大模型 / Agent / 多模态 / AI 基础设施趋势
- 今日最值得关注的 1–2 件事

## 示例邮件

GitHub README 不能直接渲染 `.eml` 邮件文件，但可以下载后用邮件客户端打开：

- [示例邮件 EML](examples/%E3%80%90%E6%AF%8F%E6%97%A5AI%E6%8A%80%E6%9C%AF%E9%80%9F%E6%8A%A5%E3%80%912026-07-17.eml)
- [示例邮件 HTML 预览](examples/daily-ai-news-example.html)

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
MAX_COMPANY_UPDATES=36
MAX_HOT_NEWS=24
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

GitHub Actions 使用 UTC 时间。北京时间是 UTC+8，所以北京时间每天 7:47 对应 UTC 每天 23:47。（GitHub Actions定时任务受到负载影响有延迟，经测试约9点-9点半之间收到，刚好在上班前地铁上可以阅读新闻）

本项目的 workflow 使用：

```yaml
cron: "47 23 * * *"
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
```

可选添加以下 Repository variables：

```text
DEEPSEEK_MODEL
DEEPSEEK_BASE_URL
MAX_COMPANY_UPDATES
MAX_HOT_NEWS
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
47 7 * * * cd /path/to/DailyAINews && /path/to/DailyAINews/.venv/bin/python main.py >> /path/to/DailyAINews/cron.log 2>&1
```

如果服务器不是北京时间，建议显式设置时区：

```cron
TZ=Asia/Shanghai
47 7 * * * cd /path/to/DailyAINews && /path/to/DailyAINews/.venv/bin/python main.py >> /path/to/DailyAINews/cron.log 2>&1
```

## 自定义

- `DEEPSEEK_MODEL`：修改总结使用的模型，默认 `deepseek-chat`
- `DEEPSEEK_BASE_URL`：DeepSeek OpenAI-compatible API 地址，默认 `https://api.deepseek.com`
- `MAX_COMPANY_UPDATES`：控制大公司官方动态抓取数量，默认 `36`
- `MAX_HOT_NEWS`：控制 AI 热点新闻抓取数量，默认 `24`

抓取逻辑在 `fetch_sources.py`，总结提示词在 `summarize.py`，邮件样式和 SMTP 发送逻辑在 `send_email.py`。
