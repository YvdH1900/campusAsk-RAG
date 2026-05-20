# CampusAsk-RAG 技术架构与实现详解

> 本文档详细说明项目的核心功能实现原理、RAG 流程、各服务模块的设计与实现。

---

## 目录

1. [RAG 问答流程](#1-rag-问答流程)
2. [核心服务模块](#2-核心服务模块)
3. [文档处理流程](#3-文档处理流程)
4. [用户与权限系统](#4-用户与权限系统)
5. [缓存策略](#5-缓存策略)
6. [数据库设计](#6-数据库设计)
7. [前端架构](#7-前端架构)
8. [安全机制](#8-安全机制)

---

## 1. RAG 问答流程

### 1.1 完整问答链路

```
用户提问
    │
    ▼
┌─────────────────┐
│  1. 意图识别     │ ← 判断问题类型（事实/流程/政策/闲聊）
└────────────────┘
         │
         ▼
┌─────────────────┐
│  2. 语义缓存检查  │ ← 相似度 > 0.95 直接返回缓存答案
└────────┬────────┘
         │ (未命中)
         ▼
┌─────────────────┐
│  3. 查询扩展     │ ← 同义词扩展，生成多个变体问题
└────────┬────────
         │
         ▼
┌─────────────────┐
│  4. 多路召回     │ ← 三路检索 + RRF 融合
│  ├─ 路径1       │   原始问题向量检索
│  ├─ 路径2       │   扩展问题向量检索
│  └─ 路径3       │   BM25 关键词检索
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  5. 重排序       │ ← 向量分数 70% + 关键词匹配 30%
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  6. 质量过滤     │ ← 自适应阈值 + 去重
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  7. 权限过滤     │ ← 根据用户角色过滤文档
────────┬────────┘
         │
         ▼
┌─────────────────┐
│  8. 提示词构建   │ ← 组装上下文 + 对话历史 + 系统提示
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  9. LLM 调用    │ ← 通义千问生成回答（指数退避重试）
└────────┬────────
         │
         ▼
┌─────────────────┐
│  10. 答案验证    │ ← 检查事实准确性和上下文覆盖率
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  11. 缓存结果    │ ← 存入语义缓存供后续使用
└────────┬────────┘
         │
         ▼
      返回回答
```

### 1.2 意图识别

**实现文件**：`backend/app/services/intent_classifier.py`

基于规则和关键词的轻量级分类器，无需额外 AI 模型：

| 意图类型 | 识别关键词 | 处理策略 |
|---------|-----------|---------|
| **事实型** | 什么时候、在哪里、是谁、多少、电话 | 精确向量检索，快速定位 |
| **流程型** | 怎么、如何、办理流程、步骤、怎么办 | 扩展检索 + 多路召回 |
| **政策型** | 规定、要求、条件、能不能、限制 | 多路召回 + 重排序 |
| **闲聊型** | 你好、谢谢、再见、哈哈 | 直接回复，跳过检索 |

### 1.3 多路召回（Multi-Path Retrieval）

**实现文件**：`backend/app/services/multi_path_retrieval.py`

使用三种检索路径提高召回率，通过 RRF（Reciprocal Rank Fusion）算法融合：

```python
# 路径1：原始问题向量检索
embedding = embedder.embed(question)
results1 = vector_store.search(embedding, top_k=10)

# 路径2：扩展问题向量检索（同义词扩展）
expanded = query_expansion.expand(question)  # "怎么办理休学" → ["如何办理休学", ...]
embedding2 = embedder.expand(embedding2, top_k=10)

# 路径3：BM25 关键词检索
results3 = bm25_service.search(question, top_k=10)

# RRF 融合：score(d) = Σ 1/(k + rank_i(d))，k=60
fused = rrf_fusion([results1, results2, results3], top_k=5)
```

### 1.4 重排序（Reranking）

**实现文件**：`backend/app/services/reranker_service.py`

采用**DashScope Reranker API 优先 + 启发式降级**的双模式策略：

```python
# 优先使用 DashScope Reranker API（如 gte-rerank）
response = dashscope.TextReRank.call(
    model=model_name,
    query=query,
    documents=documents,
    top_n=len(documents)
)

# API 不可用时自动降级到启发式重排序
combined_score = 0.7 * vector_score + 0.3 * keyword_overlap
```

这种方式在保证重排序精度的同时，通过降级机制确保服务高可用。

### 1.5 答案验证

**实现文件**：`backend/app/services/answer_verifier.py`

对 LLM 生成的答案进行质量检查：

1. **空答案检测**
2. **免责声明检测**：检测"我不确定"、"可能"、"也许"等不确定表述
3. **上下文覆盖率**：计算答案中有多少内容来自检索上下文（最低要求 30%）
4. **验证失败处理**：触发重新生成或降级策略

---

## 2. 核心服务模块

### 2.1 检索服务（RetrievalService）

**实现文件**：`backend/app/services/retrieval_service.py`

整合所有检索优化技术的核心服务：

```python
class RetrievalService:
    def retrieve(self, question, top_k=5, db=None, user=None):
        # 1. 语义缓存检查
        # 2. 意图识别
        # 3. 查询扩展
        # 4. 多路召回
        # 5. 重排序
        # 6. 质量过滤
        # 7. 权限过滤
        # 8. 缓存结果
```

### 2.2 向量化服务（EmbeddingService）

**实现文件**：`backend/app/services/embedding_service.py`

- 调用通义千问 Embedding API
- Redis 缓存（7 天 TTL），相同文本不重复调用
- 指数退避重试机制（最多 3 次）
- 批量处理优化（batch_size=10）
- 动态模型选择（从数据库读取激活配置）

### 2.3 语义缓存（SemanticCache）

**实现文件**：`backend/app/services/semantic_cache.py`

- 将问题向量化后存入 Redis
- 新问题时计算余弦相似度
- 相似度 > 0.95 直接返回缓存答案
- 最大缓存 1000 条
- **效果**：相似问题响应时间从 ~3s 降至 ~50ms

### 2.4 查询扩展（QueryExpansion）

**实现文件**：`backend/app/services/query_expansion.py`

- 内置教育领域同义词库
- 替换关键词为同义词，生成多个扩展问题
- 示例：`"怎么办理休学"` → `["如何办理休学", "休学申请流程", "休学怎么办"]`

### 2.5 BM25 关键词检索

**实现文件**：`backend/app/services/bm25_service.py`

- 基于 BM25 算法的关键词检索
- 惰性构建索引（首次检索时构建）
- 与向量检索互补，提高关键词匹配精度

### 2.6 质量过滤器（RetrievalQualityFilter）

**实现文件**：`backend/app/services/retrieval_quality.py`

- **自适应阈值策略**：
  - 第一遍：高阈值（0.45）过滤
  - 结果充足（≥3 条）直接返回
  - 结果不足：降级到低阈值（0.15）
- **去重**：基于 Jaccard 相似度（阈值 0.9）
- **内容长度过滤**：最低 20 字符

### 2.7 权限过滤器（PermissionFilter）

**实现文件**：`backend/app/services/permission_filter.py`

- 根据用户角色过滤文档
- 学生只能访问公开文档
- 教师可访问公开 + 内部文档
- 管理员可访问全部文档

### 2.8 对话摘要服务（SummaryService）

**实现文件**：`backend/app/services/summary_service.py`

- **AI 模式**：调用 LLM 将对话历史压缩为语义摘要，保留关键上下文
- **截断模式（Fallback）**：基于 Token 估算自动截断，保留最近的消息
- 两种模式结合，优先使用 AI 摘要，失败时自动降级
- 超阈值（1500 tokens）时触发压缩

---

## 3. 文档处理流程

### 3.1 完整处理链路

```
上传文件
    │
    ▼
┌─────────────────┐
│  格式校验        │ ← PDF/DOC/DOCX/TXT/MD
└────────────────┘
         │
         ▼
┌─────────────────┐
│  临时存储        │ ← uploads/temp_documents/
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  文本提取        │ ← PyMuPDF (PDF) + python-docx (Word)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  文本分块        │ ← 最大 500 字，重叠 50 字
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  向量化          │ ← 通义千问 Embedding（批量 + 缓存）
└────────┬────────┘
         │
         ▼
┌─────────────────
│  存入 Milvus     │ ← 向量 + 元数据（父子块机制）
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  更新 BM25 索引  │ ← 关键词索引
└────────────────┘
         │
         ▼
      处理完成
```

### 3.2 文本分块策略

**实现文件**：`backend/app/services/text_splitter.py`

- **分块大小**：最大 500 字符
- **重叠大小**：50 字符
- **分块策略**：优先按段落、标题分块
- **父子块机制**：父块包含完整段落，子块用于精确检索

### 3.3 文档审核流程

| 角色 | 上传行为 | 审核要求 |
|------|---------|---------|
| **管理员** | 直接入库 | 无需审核 |
| **教师** | 待审核状态 | 需管理员审核通过后才入库 |
| **学生** | 不可上传 | - |

---

## 4. 用户与权限系统

### 4.1 三级权限体系

| 角色 | 权限 | 默认限制 |
|------|------|---------|
| **学生** | 提问、查看历史、查看公告 | 每日提问 100 次 |
| **教师** | 学生权限 + 上传文档 | 每日上传 10 次 |
| **管理员** | 全部权限 + 用户管理、文档审核、系统设置 | 无限制 |

### 4.2 用户管理功能

- **用户列表**：分页查看所有用户
- **限制管理**：设置用户每日提问/上传次数上限
- **封禁/解封**：临时封禁违规用户（支持设置截止时间）
- **教师审核**：审核教师注册申请（通过/驳回）
- **每日计数重置**：跨天自动重置提问/上传计数

### 4.3 认证机制

- **JWT Token**：基于 python-jose 的 JWT 认证
- **密码加密**：bcrypt 哈希存储
- **会话管理**：记录登录 IP、时间、会话 ID
- **多设备登录**：支持多设备同时在线

---

## 5. 缓存策略

### 5.1 三级缓存体系

| 缓存类型 | 存储位置 | TTL | 用途 |
|---------|---------|-----|------|
| **检索缓存** | Redis | 1 小时 | 相同问题的检索结果 |
| **回答缓存** | Redis | 24 小时 | 相同问题的 LLM 回答 |
| **语义缓存** | Redis | 永久 | 相似问题的向量 + 答案 |
| **向量化缓存** | Redis | 7 天 | 相同文本的向量结果 |

### 5.2 缓存键设计

```
embedding:{model_name}:{md5(text)}     # 向量化缓存
search:{md5(question)}                  # 检索缓存
answer:{md5(question)}                  # 回答缓存
semantic_cache:{md5(question)}          # 语义缓存
```

---

## 6. 数据库设计

### 6.1 核心表

| 表名 | 说明 | 关键字段 |
|------|------|---------|
| **users** | 用户表 | role, is_active, pending_approval, ban_until, max_questions_per_day |
| **chat_sessions** | 会话表 | user_id, title |
| **messages** | 消息表 | session_id, role, content, sources, feedback |
| **documents** | 文档表 | title, file_path, status, category, uploaded_by, reviewed_by |
| **announcements** | 公告表 | title, content, is_active, is_popup |
| **system_settings** | 系统设置表 | key, value |
| **login_records** | 登录记录表 | user_id, login_time, ip_address, success |
| **model_configs** | 模型配置表 | model_type, model_name, api_key, is_active, dimension |
| **question_stats** | 问题统计表 | content, count |

---

## 7. 前端架构

### 7.1 页面结构

```
├── layouts/
│   ├── MainLayout.vue      # 用户端布局（侧边栏 + 主内容区）
│   ├── AdminLayout.vue     # 管理端布局
│   └── ProfileLayout.vue   # 个人中心布局
├── views/
│   ├── Home.vue            # 首页/智能问答
│   ├── History.vue         # 对话历史
│   ├── Login.vue           # 登录
│   ├── Profile.vue         # 个人中心
│   ├── TeacherDocuments.vue # 教师文档管理
│   └── Admin/              # 管理后台
│       ├── Dashboard.vue   # 数据概览
│       ├── Documents.vue   # 文档管理
│       ├── SiteManagement.vue # 网站管理
│       └── ...
```

### 7.2 性能优化

- **路由懒加载**：按需加载页面组件
- **Tab 懒渲染**：管理页面 Tab 按需渲染（v-if）
- **请求拦截**：Axios 统一处理认证和错误
- **全局状态**：Pinia 管理用户状态

---

## 8. 安全机制

| 安全特性 | 实现方式 |
|---------|---------|
| **认证** | JWT Token + bcrypt 密码哈希 |
| **授权** | 基于角色的访问控制（RBAC） |
| **Rate Limiting** | 200 请求/分钟 |
| **输入校验** | Pydantic 数据验证 |
| **安全响应头** | X-Frame-Options, X-Content-Type-Options, CSP |
| **CORS** | 可配置允许源 |
| **SQL 注入防护** | SQLAlchemy ORM 参数化查询 |
| **API 文档保护** | 生产环境可禁用 Swagger/ReDoc |

---

## 9. 部署架构

```
┌─────────────────────────────────────────────────┐
│                  Docker Host                     │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  Nginx   │  │ Frontend │  │ Backend  │      │
│  │ :80/:443 │  │  :5173   │  │  :8000   │      │
│  └────┬─────┘  └──────────┘  └────┬─────┘      │
│       │                            │              │
│       └────────────┬───────────────┘              │
│                    │                              │
│  ┌──────────┐  ┌──────────  ┌──────────┐      │
│  │  MySQL   │  │  Milvus  │  │  Redis   │      │
│  │  :3306   │  │  :19530  │  │  :6379   │      │
│  └──────────┘  └──────────  └──────────┘      │
─────────────────────────────────────────────────┘
```
