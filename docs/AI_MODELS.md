# AI 模型使用说明

> 本文档说明项目中实际使用的 AI 模型，以及未使用外部模型但通过算法实现的替代方案。

---

## 实际使用的 AI 模型

### 1. 通义千问 LLM（语言模型）

**用途**：生成问答回答

**调用位置**：`backend/app/services/qa_service.py`

```python
from dashscope import Generation

response = Generation.call(
    model=model_name,        # 如 qwen-plus, qwen-max
    messages=messages,
    stream=stream,
    timeout=timeout,
)
```

**配置方式**：
- 在管理后台「网站管理 > 模型管理」中配置
- 支持动态切换模型（qwen-plus / qwen-max / qwen-turbo 等）
- API Key 从数据库读取，支持热更新

**重试机制**：
- 指数退避重试（最多 3 次）
- 基础延迟 1 秒，每次翻倍
- 超时控制（默认 30 秒）

---

### 2. 通义千问 Embedding（向量化模型）

**用途**：将文本转换为向量，用于语义检索

**调用位置**：`backend/app/services/embedding_service.py`

```python
from dashscope import TextEmbedding

response = TextEmbedding.call(
    model=model_name,        # 如 text-embedding-v3
    input=texts,
)
```

**配置方式**：
- 在管理后台「网站管理 > 模型管理」中配置
- 支持配置向量维度（1024 / 1536 等）
- 与 LLM 可独立配置不同的 API Key

**优化策略**：
- Redis 缓存（7 天 TTL），相同文本不重复调用
- 批量处理（batch_size=10）
- 指数退避重试

---

### 3. 通义千问 Reranker（重排序模型）

**用途**：对检索结果进行重排序，提升最终结果质量

**调用位置**：`backend/app/services/reranker_service.py`

```python
import dashscope

response = dashscope.TextReRank.call(
    model=model_name,        # 如 gte-rerank
    query=query,
    documents=documents,
    top_n=len(documents)
)
```

**配置方式**：
- 在管理后台「网站管理 > 模型管理」中配置
- 模型类型选择 `reranker`
- 支持动态切换模型
- 未配置时自动降级到启发式重排序

**推荐模型**：
- `gte-rerank`（推荐，阿里云百炼平台提供）

---

## 使用 LLM 的辅助功能

以下功能使用通义千问 LLM API，无需额外配置模型：

### 1. 查询扩展

**实现文件**：`backend/app/services/query_expansion.py`

**AI 模式**：调用 LLM 生成语义相似的变体问题
```python
# 示例：输入 "怎么办理休学"
# 输出：["如何办理休学", "休学申请流程", "休学怎么办"]
```

**Fallback**：内置同义词表扩展（零成本）

---

### 2. 对话摘要

**实现文件**：`backend/app/services/summary_service.py`

**AI 模式**：调用 LLM 将长对话历史压缩为简洁摘要
```python
# 输入：10 条对话历史
# 输出：1 条系统消息 "[对话历史摘要] 用户询问了休学流程..."
```

**Fallback**：基于 Token 估算的截断策略（零成本）

---

### 3. 答案验证

**实现文件**：`backend/app/services/answer_verifier.py`

**AI 模式**：调用 LLM 判断答案是否基于检索上下文
```python
# 输入：问题 + 上下文 + 答案
# 输出：是否基于上下文、是否有额外信息、理由
```

**Fallback**：基于关键词匹配和上下文覆盖率的规则验证（零成本）

---

## 总结

### AI 模型使用情况

| 功能 | 模型类型 | 实现方式 | 配置位置 |
|------|---------|---------|---------|
| **回答生成** | LLM | 通义千问 API | 模型管理 > 语言模型 |
| **文本向量化** | Embedding | 通义千问 API | 模型管理 > 向量模型 |
| **重排序** | Reranker | 通义千问 API | 模型管理 > 重排序模型 |
| **查询扩展** | LLM | 与回答生成共用 LLM 模型 | 无需额外配置 |
| **对话摘要** | LLM | 与回答生成共用 LLM 模型 | 无需额外配置 |
| **答案验证** | LLM | 与回答生成共用 LLM 模型 | 无需额外配置 |

### 设计理念

项目采用**"核心 AI + 轻量算法"**的混合架构：

- **核心 AI**：回答生成、向量化和重排序使用通义千问 API，保证质量
- **辅助 AI**：查询扩展、对话摘要、答案验证复用 LLM API，无需额外部署

这种设计在**效果**和**成本**之间取得了良好平衡，适合校园场景的部署和运维。

### 降级策略

所有 AI 功能都实现了 fallback 机制：

| 功能 | AI 模式 | Fallback 模式 |
|------|---------|--------------|
| 重排序 | Reranker API | 向量分数 70% + 关键词匹配 30% |
| 查询扩展 | LLM 生成变体 | 内置同义词表 |
| 对话摘要 | LLM 生成摘要 | Token 估算 + 截断 |
| 答案验证 | LLM 判断准确性 | 关键词匹配 + 覆盖率计算 |

当 AI 服务不可用时，系统会自动降级到 fallback 模式，确保核心功能不受影响。
