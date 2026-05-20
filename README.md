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

### 部署架构

```
公网用户
    │
    ▼
┌──────────────────────┐
│  Nginx (:80 / :443)  │  ← 唯一对外入口，反向代理
│  deploy/nginx/       │
│  nginx.conf          │
└──────┬───────────────┘
       │
       ├─→ 前端静态文件 (frontend/dist/)
       │   /var/www/campusask-rag
       │
       └─→ /api/* → Backend (:8000)
                        │
                        └─→ Internal 网络（外部隔离）
                            MySQL / Redis / RabbitMQ
                            Milvus / MinIO / etcd
```

### 方式一：Docker 一键部署（推荐）

```bash
# 1. 配置环境变量
cp .env.example .env
nano .env
# 必须修改：
#   DASHSCOPE_API_KEY=sk-xxx     通义千问 API 密钥（必填）
#   SECRET_KEY=xxx               openssl rand -hex 32 生成
#   MYSQL_ROOT_PASSWORD=xxx      MySQL root 密码
#   REDIS_PASSWORD=xxx           Redis 密码
#   RABBITMQ_PASSWORD=xxx        RabbitMQ 密码

# 2. 配置 Nginx 域名（将 yourdomain.com 改为你的域名或服务器 IP）
nano deploy/nginx/nginx.conf

# 3. 一键启动所有服务
chmod +x start.sh
./start.sh
```

启动脚本自动执行以下流程：
1. 检测 Docker 环境
2. 检查并初始化 `.env` 配置文件
3. 构建前端 → 构建后端镜像 → 启动所有容器
4. 依次等待 MySQL、Redis、RabbitMQ、Milvus、Nginx 健康检查通过
5. 显示访问地址

**启动的服务清单：**

| 服务 | 容器名 | 对外端口 | 说明 |
|------|--------|---------|------|
| Nginx | campusask-nginx | **80 / 443** | 唯一对外入口，反向代理 |
| Backend | campusask-backend | 无 | FastAPI 后端 |
| Celery | campusask-celery | 无 | 异步任务 Worker |
| MySQL | campusask-mysql | 无 | 关系数据库 |
| Redis | campusask-redis | 无 | 缓存 |
| RabbitMQ | campusask-rabbitmq | 无 | 消息队列 |
| Milvus | campusask-milvus | 无 | 向量数据库 |
| MinIO | campusask-minio | 无 | 对象存储 |
| etcd | campusask-etcd | 无 | Milvus 依赖 |

启动完成后访问：
- **前端页面**：http://服务器IP
- **API 健康检查**：http://服务器IP/api/health

> ⚠️ **安全说明**：生产环境仅暴露 80/443 端口（Nginx），
> 所有数据库和中间件端口（3306/6379/19530/5672/9001 等）均隐藏在内网，
> 外部无法直接访问。

### 配置 HTTPS（可选，推荐生产环境开启）

HTTPS 不是必须的。首次部署直接通过 HTTP 即可访问，需要 HTTPS 时再按以下步骤配置。

由于 Nginx 运行在 Docker 容器内，需要使用 certbot 的 standalone 模式获取证书：

```bash
# 1. 安装 certbot
apt install certbot -y

# 2. 先确保 80 端口未被占用（临时停止 Docker Nginx）
docker stop campusask-nginx 2>/dev/null || true

# 3. 申请 SSL 证书（替换为你的域名）
certbot certonly --standalone -d yourdomain.com

# 4. 将证书复制到 Nginx 配置目录
cp -r /etc/letsencrypt/live/yourdomain.com deploy/nginx/ssl/

# 5. 修改 Nginx 配置启用 HTTPS
nano deploy/nginx/nginx.conf
# - 取消 HTTPS server 段的注释
# - 取消 HTTP server 中 return 301 的注释
# - 将 yourdomain.com 替换为你的域名

# 6. 重启 Nginx 容器
docker start campusask-nginx
```

> ✅ 证书有效期 90 天，建议设置自动续期：
> ```bash
> crontab -e
> # 添加：0 0 1 * * certbot renew --standalone --pre-hook "docker stop campusask-nginx" --post-hook "docker start campusask-nginx"
> ```

### 方式二：本地开发

```bash
# 1. 启动基础服务（MySQL、Redis、RabbitMQ、Milvus）
docker compose -f docker-compose.services.yml up -d

# 2. 启动 Milvus 向量数据库（需单独启动）
# 方式 A：使用 Docker 命令直接启动
docker run -d --name campusask-milvus \
  -p 19530:19530 -p 9091:9091 \
  -e ETCD_ENDPOINTS=host.docker.internal:2379 \
  -e MINIO_ADDRESS=host.docker.internal:9000 \
  milvusdb/milvus:v2.4.0 milvus run standalone

# 方式 B：使用完整编排文件启动所有依赖
# docker compose -f docker-compose.full.yml up -d etcd minio milvus

# 3. 配置后端环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env，配置 DASHSCOPE_API_KEY

# 4. 启动后端
cd backend && pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. 启动前端
cd frontend && npm install && npm run dev
```

> 💡 `docker-compose.full.yml` 包含所有服务的完整编排（含 Milvus/etcd/MinIO），
> 适合不想单独启动 Milvus 的开发者。

> 💡 **停止服务**：`./stop.sh`（保留数据）或 `./stop.sh --clean`（清除所有数据）

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
├── deploy/                    # 部署配置
│   ├── nginx/
│   │   ├── nginx.conf         # Nginx 反向代理配置（唯一对外入口）
│   │   └── ssl/               # SSL 证书目录（.gitkeep）
│   ├── init_database.sql      # 数据库初始化脚本
│   └── firewall/              # 防火墙规则
├── milvus-config/             # Milvus 向量库配置
├── start.sh                   # 一键启动脚本（生产环境）
├── stop.sh                    # 一键停止脚本
├── docker-compose.full.yml    # 全服务编排（含 Milvus，开发用）
├── docker-compose.prod.yml    # 生产环境编排（网络隔离 + Nginx）
├── docker-compose.services.yml # 基础服务编排（MySQL/Redis/RabbitMQ）
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
