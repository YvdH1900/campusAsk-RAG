#!/bin/bash

# ================================================
# CampusAsk-RAG 生产环境防火墙配置脚本
# ================================================
# 作用：
# 1. 只开放必要的端口（80/443）
# 2. 阻止所有数据库和中间件端口的对外访问
# 3. 保护服务器安全
# ================================================

set -e

echo "========================================"
echo "  CampusAsk-RAG 防火墙配置"
echo "========================================"
echo ""

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then 
  echo "❌ 请使用 sudo 运行此脚本"
  echo "   sudo ./setup_firewall.sh"
  exit 1
fi

# 检查 UFW 是否安装
if ! command -v ufw &> /dev/null; then
    echo "❌ UFW 未安装，正在安装..."
    apt-get update
    apt-get install -y ufw
fi

echo "⚠️  警告：此脚本将配置防火墙规则"
echo "   如果通过 SSH 连接，请确保已开放 22 端口"
echo ""
read -p "是否继续？(y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 已取消"
    exit 1
fi

# ================================================
# 1. 重置现有规则（可选）
# ================================================
echo "📋 重置现有防火墙规则..."
ufw --force reset

# ================================================
# 2. 设置默认策略
# ================================================
echo "🔒 设置默认策略：拒绝所有入站，允许所有出站"
ufw default deny incoming
ufw default allow outgoing

# ================================================
# 3. 开放必要端口
# ================================================
echo "✅ 开放必要端口..."

# SSH（必须，否则无法远程连接）
echo "   - 开放 22/tcp (SSH)"
ufw allow 22/tcp

# HTTP（用于 Let's Encrypt 证书验证）
echo "   - 开放 80/tcp (HTTP)"
ufw allow 80/tcp

# HTTPS（主服务端口）
echo "   - 开放 443/tcp (HTTPS)"
ufw allow 443/tcp

# ================================================
# 4. 明确阻止危险端口（防御性配置）
# ================================================
echo "🚫 阻止危险端口对外暴露..."

# 数据库
ufw deny 3306/tcp 2>/dev/null && echo "   - 阻止 3306/tcp (MySQL)"
ufw deny 6379/tcp 2>/dev/null && echo "   - 阻止 6379/tcp (Redis)"

# 消息队列
ufw deny 5672/tcp 2>/dev/null && echo "   - 阻止 5672/tcp (RabbitMQ)"
ufw deny 15672/tcp 2>/dev/null && echo "   - 阻止 15672/tcp (RabbitMQ 管理)"

# 向量数据库
ufw deny 19530/tcp 2>/dev/null && echo "   - 阻止 19530/tcp (Milvus)"
ufw deny 9091/tcp 2>/dev/null && echo "   - 阻止 9091/tcp (Attxu UI)"

# 对象存储
ufw deny 9000/tcp 2>/dev/null && echo "   - 阻止 9000/tcp (MinIO API)"
ufw deny 9001/tcp 2>/dev/null && echo "   - 阻止 9001/tcp (MinIO 控制台)"

# Milvus 其他端口
ufw deny 2379/tcp 2>/dev/null && echo "   - 阻止 2379/tcp (etcd)"
ufw deny 2380/tcp 2>/dev/null && echo "   - 阻止 2380/tcp (etcd)"
ufw deny 4001/tcp 2>/dev/null && echo "   - 阻止 4001/tcp (Milvus)"

# 后端开发端口（生产环境不应该开放）
ufw deny 8000/tcp 2>/dev/null && echo "   - 阻止 8000/tcp (FastAPI 直接访问)"
ufw deny 5173/tcp 2>/dev/null && echo "   - 阻止 5173/tcp (Vite 开发服务器)"

# ================================================
# 5. 启用 UFW
# ================================================
echo ""
echo "🔥 启用防火墙..."
ufw --force enable

# ================================================
# 6. 显示配置结果
# ================================================
echo ""
echo "========================================"
echo "  防火墙配置完成！"
echo "========================================"
echo ""
ufw status verbose
echo ""
echo "✅ 开放的端口："
echo "   - 22/tcp  (SSH)"
echo "   - 80/tcp  (HTTP → 自动跳转 HTTPS)"
echo "   - 443/tcp (HTTPS)"
echo ""
echo "🔒 已阻止的端口（外部无法访问）："
echo "   - 3306    (MySQL)"
echo "   - 6379    (Redis)"
echo "   - 5672    (RabbitMQ)"
echo "   - 15672   (RabbitMQ 管理)"
echo "   - 19530   (Milvus)"
echo "   - 9000    (MinIO)"
echo "   - 9001    (MinIO 控制台)"
echo "   - 8000    (FastAPI)"
echo "   - 5173    (Vite)"
echo ""
echo "📝 用户只能访问："
echo "   - https://yourdomain.com (前端网站)"
echo "   - https://yourdomain.com/api/* (API 接口)"
echo ""
echo "⚠️  注意："
echo "   1. 后端服务应该绑定到 127.0.0.1（内网）"
echo "   2. 数据库应该绑定到 127.0.0.1（内网）"
echo "   3. 所有服务通过 Nginx 反向代理统一暴露"
echo ""
