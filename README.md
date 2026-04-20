# 常理剥落 / Jouri Hakuraku

<div align="center">

![Logo](logo.png)

**[English](#english) · [中文](#中文)**

</div>

---

<!-- ============================================================
     ENGLISH
     ============================================================ -->

## English

### Overview

**Jouri Hakuraku** is a next-generation, open-source intelligence platform designed for structured analysis and deep insight into specific topics. It aggregates data from multiple sources, applies LLM-powered triage filtering and rollup pipelines, and delivers structured briefings through a modern web dashboard.

The platform ships with a **Discord self-bot listener** out of the box. The architecture is source-agnostic and extensible — community contributions can add RSS feeds, Slack connectors, MISP integration, or any other intelligence source.

### Architecture

```
┌─────────────┐    ┌─────────────────┐    ┌──────────────┐
│ Data Source │───▶│ Ingestion Layer │───▶│  Raw Data DB │
│  (Discord,  │    │  (pluggable)    │    │              │
│   RSS, ...) │    └─────────────────┘    └──────┬───────┘
└─────────────┘                                  │
                                                 ▼
                                        ┌─────────────────┐
                                        │   Triage Node   │ ◄── LLM: score & filter
                                        │  (LangGraph)    │     (>= 60 passes)
                                        └────────┬────────┘
                                                 │ passed intel
                                                 ▼
                                        ┌─────────────────┐
                                        │  Center Intel   │ ◄── News: immediate
                                        │  (raw content)  │     Chat: batch of 30
                                        └────────┬────────┘
                                                 │
                                                 ▼
                                       ┌────────────────────────┐
                                       │  Daily Rollup (00:05)  │ ◄── LLM: chunk → daily brief
                                       │  Joint Red + Blue      │     (red dossier + blue brief)
                                       └───────────┬────────────┘
                                                   │
                                                   ▼
                                       ┌────────────────────────┐
                                       │  Weekly Rollup         │ ◄── LLM: 7-day rollup
                                       │  (overall summary)     │     → overall_summary table
                                       └───────────┬────────────┘
                                                   │
                                                   ▼
                                      Daily Briefings + Overall
                                         (web dashboard)
```

### Features

- **Discord Self-Bot Listener** — listens to configured channels; trusted channels bypass AI and ingest directly
- **LLM-Powered Triage** — scores each item against `TRACKING_TOPIC`; score >= 60 passes, else dropped
- **Batch Chat Aggregation** — chat messages accumulate to 30 before triggering batch AI analysis
- **Trusted Channel Bypass** — specific channel IDs can skip the AI pipeline entirely (rule-based parsing + direct ingest)
- **Automated Daily Rollup** — 00:05: drain all center intel → chunk summaries → red dossier + blue brief
- **Weekly / Overall Rollup** — every day: roll up last 7 days of red+blue into a single overall summary; purge old daily summaries
- **Sidebar Memory Bank** — manually curated intel entries in the sidebar; auto-summarized when 50 entries accumulate
- **Source Confidence Overrides** — per-source confidence anchors (high/medium/low) configurable via the UI
- **Multi-LLM Support** — configurable LLM for triage + separate LLM for rollup operations
- **Modern Web Dashboard** — Streamlit UI, dark theme, language toggle (EN/ZH), collapsible sections

### Tech Stack

| Layer | Technology |
|---|---|
| LLM | Google Gemini / Anthropic Claude / OpenAI GPT |
| Agent Framework | LangGraph |
| Database | SQLite |
| Web UI | Streamlit |
| Reverse Proxy | Nginx |
| Container | Docker / Docker Compose |
| Discord | discord.py-self |

### Quick Start

#### 1. Prerequisites

- Python 3.11+ / Docker & Docker Compose
- A **Discord User Token** (account must stay logged in) — obtained via Developer Mode
- An LLM API Key (Google Gemini recommended, free tier is sufficient)

#### 2. Environment Setup

```bash
cp .env.example .env
nano .env
# Required: GOOGLE_API_KEY, DISCORD_USER_TOKEN
# Recommended: APP_AUTH_KEY (access password), TRACKING_TOPIC
```

#### 3. Docker (Recommended)

```bash
docker compose up -d --build
# Access at http://your-server-ip:8000
```

#### 4. Run Locally

```bash
pip install -r requirements.txt
python run_nexus.py
# Frontend: http://localhost:8501
# Discord Listener + Scheduler start automatically
```

#### 5. Discord Setup

1. Enable **Developer Mode** in Discord → User Settings → Advanced
2. Right-click your target channel → **Copy Channel ID**
3. Add the channel ID to `DISCORD_CHANNEL_IDS` in `.env`
4. Add trusted channel IDs to `TRUSTED_CHANNEL_IDS` (these bypass AI scoring and ingest directly)
5. Get your **User Token**: Discord app window → F12 → Network tab → send any message → find `Authorization` in request headers

### Deployment

```bash
# 1. Upload code to server
scp -r jouri_hakuraku user@your-server:/opt/

# 2. Configure environment
cd /opt/jouri_hakuraku
cp .env.example .env
nano .env  # fill in API keys and token

# 3. Build and start
docker compose up -d --build

# 4. View logs
docker logs -f jouri_nexus

# 5. Check status
docker compose ps
```

> **Access Password:** Set `APP_AUTH_KEY` in `.env`. After setting, browsing to `http://IP:8000` will prompt for credentials (username: `admin`). Leave empty to disable authentication.

### Directory Structure

```
jouri_hakuraku/
├── agent/                     # LangGraph pipeline + LLM nodes
│   ├── graph.py              # Graph builder (single triage node)
│   ├── state.py              # Shared AgentState schema
│   ├── llm_factory.py        # LLM factory (Google / Anthropic / OpenAI)
│   └── nodes/
│       ├── triage.py         # Triage scoring node
│       ├── summarize.py      # Daily rollup: chunk summaries + red/blue briefs
│       └── weekly_rollup.py  # Weekly overall summary rollup
├── ingestion/                 # Data source connectors (pluggable)
│   ├── discord_listener.py  # Discord self-bot listener
│   └── chat_batcher.py       # Chat batch aggregator (30-item flush)
├── scheduler/
│   ├── daily_rollup.py       # 00:05 daily rollup orchestrator
│   └── weekly_rollup.py      # Weekly overall rollup scheduler
├── database/
│   ├── init_db.py            # DB schema initialization
│   └── crud.py               # All database read/write operations
├── frontend/
│   └── app.py                # Streamlit web dashboard
├── data/                     # SQLite database (gitignored)
│   └── nexus.db
├── Dockerfile
├── docker-compose.yaml
├── nginx.conf
├── startup.sh                # Container entrypoint (nginx + discord + scheduler + streamlit)
├── run_nexus.py             # Local dev entrypoint (threads + subprocess)
├── requirements.txt
└── .env.example             # Environment variables template
```

### Contributing

This project welcomes community contributions. The ingestion layer is designed to be pluggable — implement a new connector following the same interface as `discord_listener.py` (RSS, Slack, MISP, etc.) and inject data into the processing pipeline. Pull requests welcome.

### License

GNU General Public License v3.0 (GPLv3)

---

<!-- ============================================================
     中文
     ============================================================ -->

## 中文

### 什么是常理剥落

**常理剥落**（Jouri Hakuraku）是一款开源的新一代情报洞察平台，专注于对特定议题进行结构化分析与深度挖掘。系统从多个数据源采集原始信息，经 LLM 驱动管道（Triage 过滤 → 每日汇总 → 周度总体）进行处理，最终在现代化网页看板上呈现结构化简报。

平台默认内置 **Discord Self-Bot 监听**作为数据采集器，但架构本身是**数据源无关**的——欢迎社区贡献 RSS、Slack、MISP 等各类数据源连接器，构建更丰富的情报采集网络。

### 架构图

```
┌─────────────┐    ┌─────────────────┐    ┌──────────────┐
│  数据源      │───▶│  采集层(可扩展）  │───▶│  原始数据表    │
│ (Discord,   │    │                 │    │              │
│  RSS, ...)  │    └─────────────────┘    └──────┬───────┘
└─────────────┘                                  │
                                                 ▼
                                        ┌─────────────────┐
                                        │  分类过滤节点     │ ◄── LLM：评分与过滤
                                        │  (LangGraph)    │     (分数 >= 60 通过)
                                        └────────┬────────┘
                                                 │ 通过的情报
                                                 ▼
                                        ┌─────────────────┐
                                        │  情报集散中心     │ ◄── 新闻：实时处理
                                        │  (center intel) │     闲聊：攒满 30 条触发
                                        └────────┬────────┘
                                                 │
                                                 ▼
                                       ┌────────────────────────┐
                                       │  每日汇总 (00:05)       │ ◄── LLM：分块 → 红队蓝队简报
                                       │  红队 + 蓝队联合汇总     │
                                       └───────────┬────────────┘
                                                   │
                                                   ▼
                                       ┌────────────────────────┐
                                       │  周度总体汇总            │ ◄── LLM：7日滚动 → 总体摘要
                                       │  (overall summary)     │     删除 7 天前的日报
                                       └───────────┬────────────┘
                                                   │
                                                   ▼
                                      每日简报 + 总体摘要
                                        （网页看板展示）
```

### 核心功能

- **Discord Self-Bot 监听器** — 监听指定频道；可信频道跳过 AI 直接入库
- **LLM 驱动 Triage 过滤** — 根据 `TRACKING_TOPIC` 评分，低于 60 分直接丢弃
- **闲聊批量聚合** — 闲聊消息攒满 30 条后批量触发 AI 分析，有效节省 token
- **可信频道 bypass** — 特定频道 ID 可完全跳过 AI 评分（规则解析 + 直接入库）
- **每日自动简报** — 00:05 自动汇总：原始情报 → 分块摘要 → 红队报告 + 蓝队报告
- **周度总体汇总** — 每日滚动合并过去 7 天红蓝报告为单一总体摘要；清理过期日报
- **侧边栏情报流** — 手动录入情报条目；满 50 条自动触发 AI 汇总
- **来源置信度配置** — 逐来源配置置信度锚点（高/中/低），前端 UI 可视化管理
- **多 LLM 支持** — Triage 和 Rollup 均可独立配置不同 provider 和模型
- **现代化 Web 仪表板** — Streamlit 深色主题，支持中英文切换，区块可折叠

### 技术栈

| 层级 | 技术 |
|---|---|
| LLM | Google Gemini / Anthropic Claude / OpenAI GPT |
| 智能体框架 | LangGraph |
| 数据库 | SQLite |
| 前端 | Streamlit |
| 反向代理 | Nginx |
| 容器化 | Docker / Docker Compose |
| Discord | discord.py-self |

### 快速上手

#### 1. 环境要求

- Python 3.11+ 或 Docker & Docker Compose
- 一个有效的 **Discord User Token**（账号需保持登录状态）
- 一把 LLM API Key（推荐 Google Gemini，免费额度足够）

#### 2. 配置环境变量

```bash
cp .env.example .env
nano .env
# 必填：GOOGLE_API_KEY、DISCORD_USER_TOKEN
# 建议设置：APP_AUTH_KEY（访问密码）、TRACKING_TOPIC（追踪话题）
```

#### 3. Docker 部署（推荐）

```bash
docker compose up -d --build
# 访问地址：http://服务器IP:8000
```

#### 4. 本地运行

```bash
pip install -r requirements.txt
python run_nexus.py
# 前端：http://localhost:8501
# Discord 监听器 + 定时调度器自动启动
```

#### 5. Discord 配置步骤

1. 打开 Discord → 用户设置 → 高级 → 开启 **开发者模式**
2. 右键目标频道 → **复制频道 ID**
3. 将频道 ID 填入 `.env` 的 `DISCORD_CHANNEL_IDS`
4. 在 `TRUSTED_CHANNEL_IDS` 中标记可信频道（这些频道的消息跳过 AI 评分直接入库）
5. 获取 User Token：Discord 窗口 → 按 `F12` → Network 选项卡 → 发送任意消息 → 在请求头中找到 `Authorization` 字段

### 部署到服务器

```bash
# 1. 上传代码到服务器
scp -r jouri_hakuraku user@your-server:/opt/

# 2. 配置环境变量
cd /opt/jouri_hakuraku
cp .env.example .env
nano .env  # 填入真实 API Key 和 Token

# 3. 构建并启动
docker compose up -d --build

# 4. 查看日志
docker logs -f jouri_nexus

# 5. 确认服务状态
docker compose ps
```

> **访问密码说明：** 设置 `APP_AUTH_KEY` 后，浏览器访问 `http://IP:8000` 会弹出账号密码框（用户名为 `admin`）。留空则跳过认证。

### 目录结构

```
jouri_hakuraku/
├── agent/                     # LangGraph 管道 + LLM 节点
│   ├── graph.py              # 图构建器（单一 triage 节点）
│   ├── state.py              # 共享 AgentState 定义
│   ├── llm_factory.py        # LLM 工厂（Google / Anthropic / OpenAI）
│   └── nodes/
│       ├── triage.py         # 分类过滤节点
│       ├── summarize.py      # 每日汇总：分块摘要 + 红/蓝队简报
│       └── weekly_rollup.py  # 周度总体汇总节点
├── ingestion/                 # 数据源连接器（可扩展）
│   ├── discord_listener.py  # Discord Self-Bot 采集器
│   └── chat_batcher.py       # 闲聊批量聚合器（30条触发）
├── scheduler/
│   ├── daily_rollup.py       # 每日 00:05 汇总调度器
│   └── weekly_rollup.py      # 周度总体汇总调度器
├── database/
│   ├── init_db.py            # 数据库 Schema 初始化
│   └── crud.py               # 数据库读写操作
├── frontend/
│   └── app.py                # Streamlit Web 仪表板
├── data/                     # SQLite 数据库（已 gitignored）
│   └── nexus.db
├── Dockerfile                # 容器镜像定义
├── docker-compose.yaml        # 容器编排配置
├── nginx.conf                # Nginx 反向代理配置
├── startup.sh                # 容器启动脚本（nginx + discord + scheduler + streamlit）
├── run_nexus.py             # 本地开发入口（线程 + 子进程）
├── requirements.txt          # Python 依赖
└── .env.example             # 环境变量模板
```

### 社区贡献

本项目欢迎社区贡献。`ingestion/` 目录下已预留插件化接口，只需参考 `discord_listener.py` 的接口规范实现新的连接器（RSS、Slack、MISP 等），即可将数据注入处理管道。期待你的 PR。

### 开源协议

GNU General Public License v3.0 (GPLv3)

---

<div align="center">

*常理剥落 · Next-Generation Open Intelligence Platform*

</div>
