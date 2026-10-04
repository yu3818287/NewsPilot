# NewsPilot

NewsPilot is an AI-powered news aggregation and reading platform built with Vue 3 and FastAPI.

Its core idea is:

> Let the news find you — retrieve live stories, store them locally, filter them, and answer questions using the local news database.

## Features

### AI News Agent

- DeepSeek-powered server-side AI assistant
- LangGraph-based Agent workflow
- Detects requests for “latest,” “today,” and “real-time” news
- Searches public news sources automatically
- Stores newly discovered articles in the local database
- Uses BM25 RAG to answer questions from locally stored news
- Returns article references and Agent execution steps
- Filters advertisements, gambling content, download pages, and low-quality sources

### Conversation History

- Saves every question and AI response for authenticated users
- Stores referenced news articles and Agent execution traces
- Supports creating, switching, restoring, and deleting conversations
- Automatically restores the current conversation after a page refresh
- Keeps conversation data isolated between users
- Guest users can still use the AI assistant without persistent history

### News Collection

- Collects domestic and international news
- Only treats 2026 articles as current news
- Extracts article metadata and original source links
- Downloads and caches source images locally
- Generates original Chinese summaries and local reading content
- Prevents duplicate articles using URLs and titles
- Runs scheduled background synchronization
- Immediately synchronizes news when users ask for the latest stories

### Reading Experience

- Three-line summaries on news cards
- “Read in 30 Seconds” summary card on detail pages
- Full local article content without mandatory external redirects
- Optional original-source link at the end of each article
- Related news recommendations
- Reading history
- Favorites
- User comments
- Local fallback placeholders for missing images

### AI Recommendations

- Dedicated AI recommendation category
- Prioritizes domestic and international news
- Uses 24-hour views, total views, publication time, and image availability
- Only recommends recent articles
- Supports filtering news through natural-language questions

### User Features

- Registration and login
- Custom profile image upload
- Personal profile editing
- Password management
- User-specific favorites
- User-specific reading history
- User-specific AI conversations
- User comments

## Technology Stack

### Backend

- Python
- FastAPI
- SQLAlchemy 2
- MySQL
- LangGraph
- BM25 RAG
- DeepSeek API
- Uvicorn

### Frontend

- Vue 3
- Vite
- Pinia
- Vue Router
- Vant UI
- Axios
- Marked
- DOMPurify

## Project Structure

```text
Fast_API_project/
├── TouTiao_backend/
│   ├── config/
│   ├── crud/
│   ├── migrations/
│   ├── models/
│   ├── routers/
│   ├── schemas/
│   ├── scripts/
│   ├── services/
│   ├── uploads/
│   │   ├── avatars/
│   │   └── news/
│   ├── .env.example
│   ├── main.py
│   └── requirements.txt
├── xwzx-news/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   ├── config/
│   │   ├── router/
│   │   ├── store/
│   │   └── views/
│   ├── package.json
│   └── vite.config.js
├── tests/
├── database.sql
└── README.md

#Chinese

# NewsPilot

这是一个 Vue 3 + FastAPI 新闻项目。AI 能力已从浏览器迁移到服务端，并升级为 DeepSeek + LangGraph + 本地新闻 RAG。

## 主要能力

- DeepSeek `deepseek-flash` 服务端问答，密钥不再下发给浏览器。
- LangGraph 新闻 Agent：识别“最新/今日/实时”需求，先搜索公开新闻源，再提取来源页、去重入库，并用 BM25 RAG 从本地库生成带来源回答。
- AI 新闻会保存来源配图和 600–1000 字左右的中文本地导读；详情页留在站内阅读，原始来源只作为文末可选链接。
- 登录用户的每轮 AI 问答、新闻来源和 Agent 执行轨迹都会按会话保存；支持新建、切换、恢复和删除对话。
- 新闻列表展示三行 AI 摘要，详情页提供独立的“30 秒读完”要点卡片。
- 后台启动 60 秒后同步国内、国际、AI 科技新闻，之后默认每 6 小时同步一次；用户询问最新新闻时会立即触发同步。
- 仅把 2026 年内容作为“最新新闻”；当前本地数据库已经同步了真实 2026 新闻。
- 首页“AI 今日热榜”按国内/国际、近 24 小时浏览量、总浏览量和发布时间推荐。
- 新闻评论按登录用户隔离，支持发布、查看和删除自己的评论。
- 头像支持 PNG/JPEG/WebP 本地上传，最大 2MB。

## 启动

启动前需要体检创建数据库 可直接运行本地SQL代码

后端配置位于 `TouTiao_backend/.env`，示例见 `.env.example`。

```powershell
cd .\Fast_API_project\TouTiao_backend
venv\Scripts\python.exe -m uvicorn main:app --reload --port 8001
```

首次启动会自动执行幂等数据库升级。也可以手动同步新闻：

```powershell
venv\Scripts\python.exe scripts\sync_news.py
```

前端：

```powershell
cd .\Fast_API_project\xwzx-news
npm run dev
```

打开 `http://127.0.0.1:5173`。FastAPI 文档位于 `http://127.0.0.1:8001/docs`。

## 新增接口

- `POST /api/ai/chat`：新闻 Agent 问答，可匿名使用；登录后保存会话记录。
- `POST /api/ai/conversations`：为当前登录用户新建对话。
- `GET /api/ai/conversations`：读取当前用户的对话列表。
- `GET /api/ai/conversations/{conversation_id}`：恢复一条对话的完整消息、来源与执行轨迹。
- `DELETE /api/ai/conversations/{conversation_id}`：删除当前用户自己的指定对话。
- `POST /api/ai/sync-news`：登录后手动触发指定主题的实时新闻同步。
- `GET /api/ai/status`：检查模型和 Agent 配置。
- `GET/POST /api/news/{news_id}/comments`：读取或发布评论。
- `DELETE /api/news/comments/{comment_id}`：删除自己的评论。
- `POST /api/user/avatar`：上传头像 data URL。

