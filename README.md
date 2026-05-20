# CampusAsk-RAG 校园知识库智能问答系统

> 基于 RAG（检索增强生成）技术的校园知识库智能问答平台，为师生提供精准、可靠的校园信息服务。

---

## 项目简介

CampusAsk-RAG 是一个面向高校校园场景的智能问答系统，通过 RAG 技术将校园规章制度、办事流程、通知公告等文档转化为可检索的知识库，结合大语言模型实现自然语言问答。

### 核心功能

- **RAG 智能问答**：基于混合检索的精准回答，支持流式输出
- **文档管理**：支持 PDF/Word/TXT 文档上传、审核、向量化入库
- **多角色权限**：学生、教师、管理员三级权限体系
- **对话历史**：完整的会话记录、搜索和管理
- **管理后台**：数据统计、用户管理、公告管理、模型配置
- **语义缓存**：相似问题直接返回缓存答案，大幅降低响应时间

---

## 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Vue 3 + TypeScript + Element Plus + Pinia + Vite |
| **后端** | FastAPI + SQLAlchemy + Pydantic |
| **AI** | 通义千问 LLM + 通义千问 Embedding |
| **数据库** | MySQL 8.0 + Milvus 2.x + Redis |
| **部署** | Docker + Nginx |

---

## 快速开始

### 环境要求

- Docker 20.10+ / Docker Compose 2.0+
- Python 3.10+（本地开发）
- Node.js 18+（本地开发）

### 一键启动

```bash
# 1. 配置环境变量（Docker Compose 密码等）
cp backend/.env.example backend/.env
# 编辑 backend/.env，配置 DASHSCOPE_API_KEY 及各服务密码

# 2. 启动基础设施
docker-compose -f docker-compose.services.yml up -d

# 3. 初始化数据库
docker exec -i mysql mysql -uroot -p<YOUR_MYSQL_PASSWORD> campus_ask_rag < deploy/init_database.sql

# 4. 启动后端
cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. 启动前端
cd frontend && npm install && npm run dev
```

> 💡 **Docker 全栈部署**：使用 `docker-compose up -d` 一键启动所有服务。  
> Docker Compose 会从根目录 `.env` 读取密码等变量（`cp .env.example .env` 后编辑）。

### 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | 请查看环境变量 `DEFAULT_ADMIN_PASSWORD` 或启动日志 |

> ⚠️ **安全提示**：首次登录后请立即修改默认密码！

---

## 项目结构

```
CampusAsk-RAG/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── api/               # API 路由（auth/chat/documents/admin）
│   │   ├── core/              # 核心配置（数据库/安全/中间件）
│   │   ├── models/            # 数据模型
│   │   ├── schemas/           # Pydantic 模式
│   │   ├── services/          # 业务服务（RAG 核心）
│   │   ├── tasks/             # Celery 异步任务
│   │   └── main.py            # FastAPI 入口
│   ├── scripts/               # 维护脚本
│   ├── tests/                 # 测试文件
│   ── requirements.txt
├── frontend/                  # 前端应用
│   ├── src/
│   │   ├── api/               # API 请求封装
│   │   ├── layouts/           # 布局组件
│   │   ├── router/            # 路由配置
│   │   ├── stores/            # Pinia 状态管理
│   │   └── views/             # 页面组件
│   └── package.json
├── deploy/                    # 部署配置（Nginx/数据库）
├── milvus-config/             # Milvus 配置
└── docker-compose*.yml        # Docker 编排
```

---

## API 接口

### 认证
- `POST /api/v1/auth/register` - 注册
- `POST /api/v1/auth/login` - 登录
- `POST /api/v1/auth/refresh` - 刷新 Token
- `POST /api/v1/auth/logout` - 登出

### 问答
- `POST /api/v1/chat/ask` - RAG 智能问答
- `POST /api/v1/chat/ask/stream` - 流式问答
- `GET /api/v1/chat/sessions` - 会话列表
- `GET /api/v1/chat/sessions/{id}/messages` - 会话消息

### 文档
- `POST /api/v1/documents/upload` - 上传文档
- `GET /api/v1/documents/my` - 我的文档
- `GET /api/v1/documents/pending` - 待审核文档
- `POST /api/v1/documents/{id}/review` - 审核文档

### 管理
- `GET /api/v1/admin/stats` - 系统统计
- `GET /api/v1/admin/users` - 用户列表
- `POST /api/v1/admin/users/{id}/ban` - 封禁用户
- `GET/POST/PUT/DELETE /api/v1/admin/announcements` - 公告管理
- `GET/POST/PUT /api/v1/admin/model-configs` - 模型配置

---

## 详细文档

- [技术架构与实现详解](docs/TECHNICAL.md) - 核心功能实现原理、RAG 流程、服务详解
- [AI 模型使用说明](docs/AI_MODELS.md) - 项目中使用的 AI 模型及替代方案说明

---

## 许可证

本项目仅供学习和研究使用。
