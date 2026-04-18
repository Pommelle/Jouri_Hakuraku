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

**Jouri Hakuraku** is a next-generation, open-source intelligence platform designed for structured analysis and deep insight into specific topics. It aggregates data from multiple sources, applies a multi-agent LLM pipeline (Triage / Red Team / Blue Team analysis), and delivers structured, topic-focused briefings through a modern web dashboard.

The platform is designed to be **source-agnostic**: a Discord listener ships out of the box, but the architecture is built for extensibility — community contributions can add RSS feeds, Slack connectors, MISP integration, or any other intelligence source.

### Architecture

```
┌─────────────┐    ┌─────────────────┐    ┌──────────────┐
│ Data Source │───▶│ Ingestion Layer │───▶│  Raw Data DB │
│  (Discord,  │    │ (pluggable)     │    │              │
│   RSS, ...) │    └─────────────────┘    └──────┬───────┘
└─────────────┘                                  │
                                                 ▼
                                        ┌─────────────────┐
                                        │   AI Pipeline   │ ◄── Triage (auto-filter)
                                        │                 │ ◄── Red Team Analysis
                                        │                 │ ◄── Blue Team Analysis
                                        └────────┬────────┘ ◄── Synthesis
                                                 │
                                                 ▼
                                        Processed Intel (center)
                                                 │
                                                 ▼
                                       ┌────────────────────────┐
                                       │ Daily Rollup (00:05)   │ ◄── AI Summary
                                       └───────────┬────────────┘
                                                   │
                                                   ▼
                                      Daily Briefings (web dashboard)
```

### Features

- **Multi-Source Ingestion** — Discord listener included by default; pluggable architecture for adding new sources
- **LLM-Powered Analysis** — Multi-provider LLM (configurable) for triage, Red Team, Blue Team, and synthesis stages
- **Batch Chat Aggregation** — Chat messages accumulate to 30 before triggering batch analysis
- **Automated Daily Briefings** — 00:05 daily rollup with old raw entries pruned
- **Modern Web Dashboard** — Streamlit UI, dark theme, timeline view, daily briefing archive
- **Production-Ready Deployment** — Docker + Nginx, BasicAuth access protection out of the box

### Tech Stack

| Layer | Technology |
|---|---|
| LLM | Google Gemini / Anthropic Claude / OpenAI GPT |
| Agent Framework | LangGraph |
| Database | SQLite |
| Web UI | Streamlit |
| Reverse Proxy | Nginx |
| Container | Docker / Docker Compose |

### Quick Start

#### 1. Prerequisites

- Python 3.11+ / Docker & Docker Compose
- A Discord User Token (account must stay logged in)
- A Google Gemini API Key

#### 2. Environment Setup

```bash
cp .env .env.bak && nano .env
# Required: GOOGLE_API_KEY, DISCORD_USER_TOKEN
# Recommended: APP_AUTH_KEY (access password)
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
# Discord Listener starts automatically
```

#### 5. Discord Setup

1. Enable **Developer Mode** in Discord → User Settings → Advanced
2. Right-click your target channel → **Copy Channel ID**
3. Add the channel ID to `DISCORD_CHANNEL_IDS` in `.env`
4. Get your **User Token**: F12 → Network → send a message → find `Authorization` in request headers

### Deployment

See [Deploy to a Server](#deploy-to-a-server) for full production setup.

### Directory Structure

```
jouri_hakuraku/
├── agent/                     # LangGraph multi-agent pipeline
│   ├── graph.py              # Graph builder
│   ├── state.py              # Shared state schema
│   ├── llm_factory.py        # LLM factory (Google / Anthropic / OpenAI)
│   └── nodes/
│       ├── triage.py         # Triage scoring
│       ├── analyze.py         # Red / Blue team analysis
│       ├── synthesize.py     # Synthesis
│       └── summarize.py      # Daily rollup summarization
├── ingestion/                 # Data source connectors (pluggable)
│   ├── discord_listener.py  # Discord self-bot
│   └── chat_batcher.py       # Chat batch + news trigger
├── scheduler/
│   └── daily_rollup.py       # 00:05 daily cron
├── database/
│   ├── init_db.py            # DB schema init
│   └── crud.py               # Database operations
├── frontend/
│   └── app.py                # Streamlit dashboard
├── data/                     # SQLite database (gitignored)
│   └── nexus.db
├── Dockerfile
├── docker-compose.yaml
├── nginx.conf
├── startup.sh                # Container entrypoint
└── requirements.txt
```

### Contributing

This project is open to the community. Interested in adding a new data source? The ingestion layer is designed to be pluggable — open `ingestion/` and implement a new connector that follows the same interface as `discord_listener.py`. Pull requests welcome.

### License

GNU General Public License v3.0 (GPLv3)

---

<!-- ============================================================
     中文
     ============================================================ -->

## 中文

### 什么是常理剥落

**常理剥落**（Jouri Hakuraku）是一款开源的新一代情报洞察平台，专注于对特定议题进行结构化分析与深度挖掘。系统从多个数据源采集原始信息，经由多智能体 LLM 管道（Triage 过滤 / 红队分析 / 蓝队分析）进行处理，最终在多终端看板上呈现议题导向的结构化简报。

目前内置了 Discord 监听器作为默认数据源，但平台架构本身是**数据源无关**的——欢迎社区贡献 RSS、Slack、MISP 等各类数据源连接器，构建更丰富的情报采集网络。

### 架构图

```
┌─────────────┐    ┌─────────────────┐    ┌──────────────┐
│  数据源      │───▶│  采集层(可扩展)   │───▶│  原始数据表    |
│ (Discord,   │    │                 │    │              │
│  RSS, ...)  │    └─────────────────┘    └──────┬───────┘
└─────────────┘                                  │
                                                 ▼
                                        ┌─────────────────┐
                                        │   AI 处理管道    │ ◄── 分类过滤（Triage）
                                        │                 │ ◄── 红队分析（Red Team）
                                        │                 │ ◄── 蓝队分析（Blue Team）
                                        └────────┬────────┘ ◄── 综合摘要（Synthesis）
                                                 │
                                                 ▼
                                           当日情报集散中心
                                                 │
                                                 ▼
                                       ┌────────────────────────┐
                                       │  每日零点汇总 (00:05)    │ ◄── AI 精炼摘要
                                       └───────────┬────────────┘
                                                   │
                                                   ▼
                                      每日简报（Web 仪表板展示）
```

### 核心功能

- **多数据源采集** — 内置 Discord 监听器；架构支持插件化扩展，可接入任意数据源
- **LLM 驱动分析** — 支持多 LLM 提供商（可配置），执行 Triage 过滤、红队分析、蓝队分析、综合摘要
- **闲聊批量聚合** — 闲聊消息攒满 30 条后批量触发 AI 分析，有效节省 token
- **每日自动简报** — 零点零五自动汇总当日情报，清理过期原始数据
- **现代化 Web 仪表板** — Streamlit 深色主题，支持时间线视图与历史简报存档
- **生产级部署** — Docker + Nginx，开箱即用 BasicAuth 访问保护

### 技术栈

| 层级 | 技术 |
|---|---|
| LLM | Google Gemini / Anthropic Claude / OpenAI GPT |
| 智能体框架 | LangGraph |
| 数据库 | SQLite |
| 前端 | Streamlit |
| 反向代理 | Nginx |
| 容器化 | Docker / Docker Compose |

### 快速上手

#### 1. 环境要求

- Python 3.11+ 或 Docker & Docker Compose
- 一个有效的 Discord User Token（账号需保持登录状态）
- 一把 Google Gemini API Key（免费额度足够）

#### 2. 配置环境变量

```bash
cp .env .env.bak && nano .env
# 必填：GOOGLE_API_KEY、DISCORD_USER_TOKEN
# 建议设置：APP_AUTH_KEY（访问密码）
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
# Discord 监听器随主程序自动启动
```

#### 5. Discord 配置步骤

1. 打开 Discord → 用户设置 → 高级 → 开启 **开发者模式**
2. 右键目标频道 → **复制频道 ID**
3. 将频道 ID 填入 `.env` 的 `DISCORD_CHANNEL_IDS`
4. 获取 User Token：按 `F12` → Network → 发送任意消息 → 在请求头中找到 `Authorization` 字段

### 部署到服务器

```bash
# 1. 上传代码到服务器
scp -r jouri_hakuraku user@your-server:/opt/

# 2. 配置环境变量
cd /opt/jouri_hakuraku
cp .env .env.bak && nano .env  # 填入真实 API Key 和 Token

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
├── agent/                     # LangGraph 多智能体处理管道
│   ├── graph.py              # 图构建器
│   ├── state.py              # 共享状态定义
│   ├── llm_factory.py        # LLM 工厂（Google / Anthropic / OpenAI）
│   └── nodes/
│       ├── triage.py         # 分类过滤节点
│       ├── analyze.py         # 红/蓝队分析节点
│       ├── synthesize.py     # 综合摘要节点
│       └── summarize.py      # 每日汇总节点
├── ingestion/                 # 数据源连接器（可扩展）
│   ├── discord_listener.py  # Discord Self-Bot 采集器
│   └── chat_batcher.py       # 闲聊批量聚合
├── scheduler/
│   └── daily_rollup.py       # 每日零点定时任务
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
├── startup.sh                # 容器启动脚本
└── requirements.txt          # Python 依赖
```

### 社区贡献

本项目欢迎社区贡献。目前 `ingestion/` 目录下已预留插件化接口，只需参考 `discord_listener.py` 的接口规范实现新的连接器（RSS、Slack、MISP 等），即可将数据注入处理管道。期待你的 PR。

### 开源协议

GNU General Public License v3.0 (GPLv3)

---

<div align="center">

*常理剥落 · Next-Generation Open Intelligence Platform*

</div>
