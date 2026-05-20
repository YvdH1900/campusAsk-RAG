# ================================================
# CampusAsk-RAG 生产环境服务安全配置指南
# ================================================
# 目标：确保所有服务只监听内网，用户只能访问前端网站
# ================================================

## 📋 一、网络架构原则

### ✅ 正确架构
```
用户 → 防火墙 (80/443) → Nginx (反向代理) → 后端服务 (内网)
                                              ↓
                                      数据库/中间件 (内网)
```

### ❌ 错误架构
```
用户 → 直接访问后端端口 (8000, 3306, 6379, etc.) ❌
```

---

## 🔧 二、各服务安全配置

### 1️⃣ **MySQL 数据库**

**配置文件**：`/etc/mysql/mysql.conf.d/mysqld.cnf`

```ini
[mysqld]
# 只允许本地连接（关键！）
bind-address = 127.0.0.1

# 或者绑定到内网 IP（如果是多服务器部署）
# bind-address = 192.168.1.100

# 禁用远程 root 登录
skip-networking = 0
local-infile = 0

# 设置最大连接数
max_connections = 100
```

**重启服务**：
```bash
sudo systemctl restart mysql
```

**验证**：
```bash
# 应该看到只监听 127.0.0.1
netstat -tlnp | grep mysql
# 输出：127.0.0.1:3306  ✅ 正确
# 不是：0.0.0.0:3306  ❌ 错误
```

---

### 2️⃣ **Redis 缓存**

**配置文件**：`/etc/redis/redis.conf`

```ini
# 只允许本地连接（关键！）
bind 127.0.0.1

# 设置强密码（必须！）
requirepass YourStrongPassword123!@#

# 禁用危险命令
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command DEBUG ""
rename-command CONFIG ""

# 设置最大内存
maxmemory 256mb
maxmemory-policy allkeys-lru
```

**重启服务**：
```bash
sudo systemctl restart redis
```

**验证**：
```bash
netstat -tlnp | grep redis
# 应该看到：127.0.0.1:6379
```

---

### 3️⃣ **RabbitMQ 消息队列**

**配置文件**：`/etc/rabbitmq/rabbitmq.conf`

```ini
# 只监听内网
listeners.tcp.default = 5672
listeners.tcp.ip = 127.0.0.1

# 修改默认密码（必须！guest/guest 太弱）
# 通过命令行修改：
# sudo rabbitmqctl change_password guest YourStrongPassword123!@#

# 禁用管理界面（生产环境建议）
# management.listener.port = 15672  # 注释掉这行
```

**或者通过环境变量配置**（Docker 部署）：
```bash
RABBITMQ_DEFAULT_USER=admin
RABBITMQ_DEFAULT_PASS=YourStrongPassword123!@#
RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS="-kernel inet_dist_listen_min 25672 -kernel inet_dist_listen_max 25672"
```

**重启服务**：
```bash
sudo systemctl restart rabbitmq-server
```

---

### 4️⃣ **Milvus 向量数据库**

**配置文件**：`milvus.yaml`

```yaml
# 只监听内网
etcd:
  endpoints:
    - localhost:2379  # 使用 localhost 而不是 0.0.0.0

minio:
  address: localhost  # 使用 localhost
  port: 9000

# 禁用外部访问
common:
  security:
    tlsMode: 0  # 禁用 TLS（内网不需要）
```

**Docker 部署时**：
```yaml
# docker-compose.yml
services:
  milvus:
    image: milvusdb/milvus:v2.3.0
    # 不要暴露端口到宿主机
    # ports:
    #   - "19530:19530"  # ❌ 错误
    networks:
      - internal  # ✅ 正确：只在内部网络
```

---

### 5️⃣ **MinIO 对象存储**

**启动命令**（只监听内网）：
```bash
# ❌ 错误：监听所有接口
minio server /data --console-address :9001

# ✅ 正确：只监听内网
minio server /data --address 127.0.0.1:9000 --console-address 127.0.0.1:9001
```

**Docker 部署**：
```yaml
# docker-compose.yml
services:
  minio:
    image: minio/minio
    # 不要暴露端口
    # ports:
    #   - "9000:9000"
    #   - "9001:9001"
    networks:
      - internal
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: admin
      MINIO_ROOT_PASSWORD: YourStrongPassword123!@#
```

---

### 6️⃣ **FastAPI 后端服务**

**启动配置**：
```bash
# ❌ 错误：监听所有接口
uvicorn app.main:app --host 0.0.0.0 --port 8000

# ✅ 正确：只监听内网
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Systemd 服务配置**：`/etc/systemd/system/campusask-rag.service`
```ini
[Unit]
Description=CampusAsk-RAG Backend
After=network.target mysql.service redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/campusask-rag/backend
Environment="PATH=/var/www/campusask-rag/backend/venv/bin"
# 只监听内网
ExecStart=/var/www/campusask-rag/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

---

### 7️⃣ **Nginx 反向代理（关键！）**

这是**用户唯一能访问的入口**：

**配置文件**：`/etc/nginx/sites-available/campusask-rag`

```nginx
server {
    listen 80;
    listen 443 ssl;
    server_name yourdomain.com;

    # SSL 证书
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # 前端静态文件
    location / {
        root /var/www/campusask-rag/frontend;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理（唯一入口）
    location /api/ {
        proxy_pass http://127.0.0.1:8000;  # 只转发到内网
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 流式输出支持
        proxy_buffering off;
        proxy_cache off;
    }

    # 禁止访问其他路径
    location ~ ^/(docs|redoc|openapi\.json) {
        return 403;
    }
}
```

**启用配置**：
```bash
sudo ln -s /etc/nginx/sites-available/campusask-rag /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 🔒 三、防火墙最终配置

**执行防火墙脚本**：
```bash
cd /path/to/CampusAsk-RAG/deploy/firewall
sudo chmod +x setup_firewall.sh
sudo ./setup_firewall.sh
```

**验证规则**：
```bash
sudo ufw status verbose

# 应该看到：
# Status: active
# To                         Action      From
# --                         ------       ----
# 22/tcp                     ALLOW        Anywhere
# 80/tcp                     ALLOW        Anywhere
# 443/tcp                    ALLOW        Anywhere
# 3306/tcp                   DENY         Anywhere  ✅
# 6379/tcp                   DENY         Anywhere  ✅
# 8000/tcp                   DENY         Anywhere  ✅
```

---

## ✅ 四、安全检查清单

### 部署前检查
- [ ] 所有数据库绑定到 `127.0.0.1`
- [ ] 所有服务使用强密码
- [ ] 防火墙只开放 80/443/22
- [ ] Nginx 配置正确
- [ ] 禁用 API 文档（`ENABLE_API_DOCS=false`）

### 验证测试
```bash
# 1. 检查端口监听
sudo netstat -tlnp | grep -E 'mysql|redis|rabbitmq|minio|milvus|8000|5173'
# 应该都显示 127.0.0.1:PORT ✅

# 2. 从外部测试（在另一台机器）
telnet yourdomain.com 3306  # 应该连接失败 ✅
telnet yourdomain.com 80    # 应该成功 ✅
telnet yourdomain.com 443   # 应该成功 ✅

# 3. 浏览器访问
# https://yourdomain.com     ✅ 应该能访问
# https://yourdomain.com:8000  ❌ 应该无法访问
# https://yourdomain.com/docs  ❌ 应该返回 403
```

---

## 🎯 五、最终效果

### ✅ 用户视角
```
用户只能看到：
- https://yourdomain.com（前端网站）
- https://yourdomain.com/api/*（API 接口）

其他所有端口都无法访问！
```

### 🔒 安全架构
```
公网用户
    ↓
防火墙（只开放 80/443）
    ↓
Nginx（反向代理）
    ├─→ 前端静态文件（直接服务）
    └─→ 后端 API（127.0.0.1:8000）
            ↓
        数据库/中间件（127.0.0.1:*）
        
所有内部服务都对外部不可见！
```

---

## 📝 六、常见问题

### Q1: 后端如何访问数据库？
**A**: 通过 `localhost` 或 `127.0.0.1` 连接，因为都在同一台服务器上。

### Q2: 多服务器部署怎么办？
**A**: 使用内网 IP（如 `192.168.1.x`），并在防火墙中只允许内网通信。

### Q3: 如何监控服务状态？
**A**: 使用 `systemctl status <service>` 或配置 Prometheus + Grafana（通过内网访问）。

### Q4: 需要开放其他端口吗？
**A**: 不需要！所有服务都应该通过 Nginx 的 80/443 端口统一对外。

---

## 🚀 七、一键部署脚本（可选）

创建自动化部署脚本：

```bash
#!/bin/bash
# deploy.sh

echo "🚀 开始部署 CampusAsk-RAG..."

# 1. 配置服务绑定内网
echo "📝 配置服务绑定内网..."
# （配置 MySQL、Redis 等）

# 2. 安装 Nginx
echo "📦 安装 Nginx..."
apt-get install -y nginx

# 3. 配置防火墙
echo "🔥 配置防火墙..."
./deploy/firewall/setup_firewall.sh

# 4. 安装 SSL 证书
echo "🔒 安装 SSL 证书..."
certbot --nginx -d yourdomain.com

# 5. 启动服务
echo "✅ 启动服务..."
systemctl restart nginx
systemctl restart campusask-rag

echo "✅ 部署完成！"
echo "访问：https://yourdomain.com"
```

---


