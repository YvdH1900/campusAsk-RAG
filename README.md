# CampusAsk-RAG 校园知识库智能问答系统

> 基于 RAG（检索增强生成）技术的校园知识库智能问答平台，为师生提供精准、可靠的校园信息服务。

---

## 系统截图

### 智能问答界面

![智能问答](screenshots/chat.png)

### 数据概览后台

![数据概览](screenshots/dashboard.png)

### 模型配置管理

![模型配置](screenshots/model-config.png)

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
- **Token 追踪**：精确统计每次问答的输入/输出 Token 消耗，支持流式模式估算
- **答案验证**：多级置信度评估（AI 验证 + 规则验证），确保回答准确性

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

## 测试与评测

项目包含完整的测试体系，覆盖单元测试、集成测试和检索质量评测。

### 测试文件结构

| 文件 | 类型 | 覆盖内容 |
|------|------|---------|
| `test_vector_store.py` | 单元测试 | 向量库初始化、插入/搜索/删除、索引管理、孤本清理 |
| `test_retrieval_services.py` | 单元测试 | Embedding、BM25、查询扩展、质量过滤、Reranker、多路召回 |
| `test_qa_service.py` | 单元测试 | 问答初始化、缓存、重试、流式、意图分类、Prompt 模板 |
| `test_document_services.py` | 单元测试 | 文档解析验证、文本分割、语言检测 |
| `test_validators.py` | 单元测试 | 输入校验、XSS 过滤、敏感数据脱敏、密码校验 |
| `test_api_integration.py` | 集成测试 | Chat/Document/Auth/Admin API、性能测试 |
| `evaluation/test_retrieval_evaluation.py` | 检索评测 | 金标准数据集、Mock/Real 模式评测 |
| `evaluation/test_generation_evaluation.py` | 生成评测 | 扎根度/关键词/内容覆盖/延迟/拒答/多轮对话/流式输出 |
| `test_vector_consistency.py` | 真实环境测试 | MySQL-Milvus 数据一致性、孤儿向量清理、文档向量重建 |
| `test_answer_verifier.py` | 真实环境测试 | 答案质量验证（扎根度/免责声明/覆盖率/AI 验证） |
| `test_permission_filter.py` | 单元测试 | 学生/教师/管理员三级权限过滤 |
| `test_summary_service.py` | 单元测试 | 对话摘要截断模式 + AI 模式 + 降级处理 |
| `test_document_processor.py` | 真实环境测试 | 文档上传→解析→分块→向量化→入库完整流程 |

### 常用测试命令

```bash
# ===== 在项目根目录 (CampusAsk-RAG/) 或 backend/ 下执行 =====

# ============================================================
# ★ 全链路真实环境测试（重点，需 uvicorn 运行中 + Milvus + API）
# ============================================================

# 生成层全链路质量评测（pytest 格式，CI 兼容）
#   L1 系统健康 / L2 检索 / L3 生成质量 / L4 拒答 / L5 边界条件 / L6 多轮对话 / L7 流式 SSE
pytest tests/evaluation/test_generation_evaluation.py -m generation -v -s --no-cov

# 生成层全链路质量评测（旧版独立脚本，功能相同）
python run_generation.py

# 检索层全链路质量评测（6 层）
#   文档状态 / 分块质量 / BM25 / 意图+扩展 / 全链路检索 / 金标准
python run_pipeline.py

# ============================================================
# pytest 真实环境测试
# ============================================================

# 检索质量评测 — 金标准数据集 29 题，输出 MRR / 召回率 / 精准率
pytest tests/evaluation/ -m real -v -s --no-cov

# 向量一致性测试 — MySQL-Milvus 数据一致性、孤儿清理、文档重建
pytest tests/test_vector_consistency.py -m real -v -s --no-cov

# 答案验证器测试 — 答案质量验证（扎根度/免责声明/覆盖率/AI 验证）
pytest tests/test_answer_verifier.py -m real -v -s --no-cov

# 文档处理器测试 — 文档上传→解析→分块→向量化→入库完整流程
pytest tests/test_document_processor.py -m real -v -s --no-cov

# API 集成测试 — FastAPI TestClient + SQLite 测试库，全链路
pytest tests/test_api_integration.py -v --no-cov

# 文档解析真实文件 — 项目根目录 2025学生手册.pdf
pytest tests/test_document_services.py -v --no-cov

# ============================================================
# 单元测试（全部 mock，离线可跑）
# ============================================================

# 权限过滤 — 学生/教师/管理员三级权限
pytest tests/test_permission_filter.py -v --no-cov

# 对话摘要 — 截断模式 + AI 模式 + 降级处理
pytest tests/test_summary_service.py -v --no-cov

# 检索层（Embedding / BM25 / 多路召回 / Reranker / 质量过滤）
pytest tests/test_retrieval_services.py tests/test_vector_store.py -v --no-cov

# 生成层（问答 / 缓存 / 流式 / 意图分类 / Prompt 模板）
pytest tests/test_qa_service.py -v --no-cov

# 验证器（输入校验 / XSS / 脱敏 / 密码）
pytest tests/test_validators.py -v --no-cov

# 评测框架逻辑验证（Mock 模式）
pytest tests/evaluation/ -m mock -v --no-cov

# ============================================================
# 覆盖率报告（产物 → tests/tmp_test/，已 gitignore）
# ============================================================
pytest --cov=app --cov-report=html:tests/tmp_test/htmlcov --cov-report=term-missing --cov-fail-under=0
```

> **`run_generation.py` 评测指标说明**：
> | 指标 | 含义 | 通过阈值 |
> |------|------|---------|
> | grounded | 答案分词与检索上下文 token 重叠率（过滤停用词） | ≥ 0.50 |
> | kw_acc | 期望关键词在答案中的命中率 | ≥ 0.30 |
> | content_acc | 期望内容片段在答案中的覆盖率 | ≥ 0.20 |
> | latency | /ask 接口响应时间 | ≤ 30s |
> | rejection | 知识库无结果时是否正确拒答 | 全部通过 |
>
> **注意**：
> - `pyproject.toml` 默认 `addopts` 含 `--cov=app` 且 `fail_under=70`，当前覆盖率约 38%。pytest 命令均需加 `--no-cov`。
> - 所有测试运行时产物（`test.db`、`.coverage`、`htmlcov`）统一收纳在 `backend/tests/tmp_test/` 下，已加入 `.gitignore`。

### 检索质量评测结果

基于上海交通大学本科生学生手册（2025版）构建的金标准数据集（29 题），评测条件：`top_k=5`，`model=text-embedding-v4`，`dimension=1024`。

| 指标 | 数值 | 说明 |
|------|------|------|
| **总体通过率** | 96.6% (28/29) | 至少命中 1 条预期关键词 |
| **EASY（9 题）** | 100.0% (9/9) | 校训、注册、作弊处分等常识性问题 |
| **MEDIUM（12 题）** | 100.0% (12/12) | 奖学金、缓考、转专业等流程性问题 |
| **HARD（8 题）** | 87.5% (7/8) | 退学试读、双学位、最长学制等细节性问题 |
| **关键词召回率** | 0.700 | 命中的关键词数 / 预期关键词总数 |
| **MRR@k** | 0.983 | 首个相关结果的平均倒数排名 |
| **Top-K 精准率** | 0.496 | 含关键词的 chunk 数 / 返回的 chunk 总数 |

> MRR@5 达到 0.983 表明在绝大多数情况下，相关文档排在前 1~2 位，检索排序质量优秀。

### 生成质量评测结果

基于金标准数据集（12 题）的生成质量评测，评测条件：`top_k=5`。

| 指标 | 数值 | 说明 |
|------|------|------|
| **总体通过率** | 91.7% (11/12) | 满足所有评测维度阈值 |
| **扎根度(Jaccard)** | avg=0.511 | 答案与检索上下文的词重叠度 |
| **扎根度(Embedding)** | avg=0.750 | 答案与检索上下文的语义相似度 |
| **平均延迟** | 5.8s | 端到端响应时间 |

**各维度通过率：**
| 维度 | 通过率 | 说明 |
|------|--------|------|
| 扎根度 | 100% (12/12) | 答案基于检索上下文 |
| 关键词 | 100% (12/12) | 命中预期关键词 |
| 内容覆盖 | 92% (11/12) | 覆盖预期内容片段 |
| 延迟 | 100% (12/12) | 响应时间 ≤ 30s |
| 来源引用 | 100% (12/12) | 正确标注信息来源 |

**分难度统计：**
| 难度 | 通过/总数 | 扎根度(avg) | Embedding(avg) |
|------|-----------|-------------|----------------|
| Easy | 4/4 | 0.542 | 0.725 |
| Medium | 4/4 | 0.622 | 0.772 |
| Hard | 3/4 | 0.367 | 0.753 |

---

## 最新改进

### Token 使用量追踪

- **三层防御机制**：
  1. 优先从 LLM 流式响应的最后一个 chunk 提取真实 usage 数据
  2. 如果失败，使用基于中英文字符比例的精确估算（中文 ~1.5 token/字，英文 ~0.25 token/字）
  3. 最终兜底确保 `token_usage` 永远不会是空对象
- **前端显示**：在每条 AI 回答下方显示 Token 消耗（输入/输出/总计）

### 答案验证优化

- **多级置信度评估**：不再使用二元"是/否"判断，而是基于置信度分数（0.2~0.9）
  - 0.9：完全基于上下文，无额外信息
  - 0.7：基于上下文但有额外信息
  - 0.4：不基于上下文但无额外信息
  - 0.2：不基于上下文且有额外信息
- **企业级判断标准**：只有当 AI 置信度 **且** 规则置信度都低于 0.4 时才标记为无效
- **解析失败处理**：AI 验证解析失败时默认答案无效（`is_based=False`），确保系统准确性优先
- **阈值优化**：无 AI 验证时，规则判断阈值从 0.5 降至 0.35，避免过度拦截正常答案

---

## 详细文档

- [技术架构与实现详解](docs/TECHNICAL.md) - 核心功能实现原理、RAG 流程、服务详解
- [AI 模型使用说明](docs/AI_MODELS.md) - 项目中使用的 AI 模型及替代方案说明
---

## 许可证

本项目仅供学习和研究使用。
