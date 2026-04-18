jouri_hakuraku/
│
├── .env                        # 核心私密配置（LLM API Keys, Discord Token, Twitter Auth 等）
├── requirements.txt            # 项目依赖 (langgraph, streamlit, discord.py, etc.)
│
├── data/                       # 本地存储层 (不需要配置额外数据库，极简至上)
│   ├── nexus.db                # SQLite 数据库文件 (包含 raw_data, processed_intel, memory 三张表)
│   └── logs/                   # 运行日志
│
├── database/                   # 数据库交互层
│   ├── init_db.py              # 初始化建表脚本 (运行一次即可)
│   └── crud.py                 # 封装增删改查函数 (给抓取端和前端复用)
│
├── ingestion/                  # 信息泵（数据抓取层）
│   ├── discord_listener.py     # Discord bot 监听频道消息，存入 raw_data 表
│   └── twitter_scraper.py      # 定时抓取 Twitter 特定博主，存入 raw_data 表
│
├── agent/                      # AI 核心大脑（LangGraph 编排层）
│   ├── graph.py                # 组装 LangGraph 的节点和边，定义工作流
│   ├── state.py                # 定义图在流转时的状态 (TypedDict: 比如包含情报内容、红方观点、蓝方观点)
│   ├── nodes/                  # 具体的业务处理节点
│   │   ├── triage.py           # 初筛节点：判断信息是否有价值
│   │   ├── analyze.py          # 红蓝对抗节点：并发执行红/蓝分析
│   │   └── synthesize.py       # 融合节点：读取短期记忆，生成最终综述
│   ├── memory_manager.py       # 负责把 data/nexus.db 里的记忆拉取出来喂给 LLM
│   └── prompts.py              # 集中管理所有 System Prompts
│
├── frontend/                   # 你的私人指挥台（Streamlit 展示层）
│   ├── app.py                  # Streamlit 主入口文件
│   ├── components/
│   │   ├── sidebar.py          # 侧边栏：展示和编辑你的“短期记忆库”
│   │   └── feed.py             # 主界面：卡片式展示分析好的情报流
│   └── style.css               # (可选) 让界面看起来更像黑客帝国或情报局的暗黑风格
│
└── run_nexus.py                # 全局调度脚本 (可以用 subprocess 同时拉起爬虫和前端)