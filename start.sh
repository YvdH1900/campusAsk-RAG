#!/usr/bin/env bash
# ================================================
# CampusAsk-RAG 生产环境一键启动脚本 (Linux)
# ================================================
# 功能：
#   1. 检测 Docker 环境
#   2. 初始化 .env 配置（如不存在则从 .env.example 复制）
#   3. 启动所有 Docker 服务（MySQL、Redis、RabbitMQ、Milvus、etcd、MinIO、后端、Celery）
#   4. 等待健康检查通过
#   5. 显示服务访问地址
#
# 使用方法：
#   chmod +x start.sh
#   ./start.sh
# ================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'
BOLD='\033[1m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "\n${BLUE}${BOLD}>>> $1${NC}"; }

# ==================== 1. 检测 Docker ====================
log_step "1. 检测 Docker 环境"

if ! command -v docker &> /dev/null; then
    log_error "未找到 Docker，请先安装 Docker"
    exit 1
fi

if ! docker info &> /dev/null; then
    log_error "Docker 未运行，请先启动 Docker 服务"
    exit 1
fi

DOCKER_COMPOSE_CMD="docker compose"
if ! docker compose version &> /dev/null; then
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        log_error "未找到 docker compose 或 docker-compose 命令"
        exit 1
    fi
fi

log_info "Docker 环境检测通过，使用命令：${DOCKER_COMPOSE_CMD}"

# ==================== 2. 检查配置文件 ====================
log_step "2. 检查配置文件"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        log_warn "已从 .env.example 复制 .env 文件到项目根目录"
        log_warn "请编辑 .env 文件，配置以下关键参数后重新运行："
        log_warn "  - DASHSCOPE_API_KEY  （通义千问 API 密钥，必填）"
        log_warn "  - SECRET_KEY          （JWT 加密密钥，openssl rand -hex 32）"
        log_warn "  - MYSQL_ROOT_PASSWORD （MySQL root 密码）"
        log_warn "  - REDIS_PASSWORD      （Redis 密码）"
        log_warn "  - RABBITMQ_PASSWORD   （RabbitMQ 密码）"
        exit 1
    else
        log_error "未找到 .env.example 文件"
        exit 1
    fi
else
    log_info "根目录 .env 文件已存在"
fi

if [ ! -f "backend/.env" ]; then
    if [ -f "backend/.env.example" ]; then
        cp backend/.env.example backend/.env
        log_info "已从 .env.example 复制 backend/.env（使用默认值）"
    fi
fi

# 确保 volumes 目录存在
mkdir -p volumes/mysql volumes/redis volumes/rabbitmq volumes/etcd volumes/minio volumes/milvus volumes/uploads

# ==================== 3. 启动 Docker 服务 ====================
log_step "3. 启动所有 Docker 服务（生产环境）"

$DOCKER_COMPOSE_CMD --profile full -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true

log_info "正在构建镜像并启动服务（首次需 10-15 分钟，后续使用缓存）..."
$DOCKER_COMPOSE_CMD --profile full -f docker-compose.prod.yml up -d --build

# ==================== 4. 等待服务就绪 ====================
log_step "4. 等待服务健康检查通过"

wait_for_service() {
    local container=$1
    local name=$2
    local max_wait=${3:-120}
    local waited=0

    while [ $waited -lt $max_wait ]; do
        status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "unknown")
        if [ "$status" = "healthy" ]; then
            log_info "${name} ($container) 已就绪"
            return 0
        elif [ "$status" = "unhealthy" ]; then
            log_error "${name} ($container) 健康检查失败"
            return 1
        fi
        sleep 2
        waited=$((waited + 2))
        echo -n "."
    done
    echo ""
    log_error "${name} ($container) 等待超时 (${max_wait}s)"
    return 1
}

wait_for_service "campusask-milvus" "Milvus" 180 &
wait_for_service "campusask-etcd" "etcd" 60 &
wait_for_service "campusask-minio" "MinIO" 60 &

wait_for_service "campusask-mysql" "MySQL" 120 &
wait_for_service "campusask-redis" "Redis" 60 &
wait_for_service "campusask-rabbitmq" "RabbitMQ" 60 &

# Nginx 无内置健康检查，通过宿主机直连检测
wait_for_nginx() {
    local max_wait=60
    local waited=0
    while [ $waited -lt $max_wait ]; do
        if curl -sf http://localhost:80/ > /dev/null 2>&1; then
            log_info "Nginx (campusask-nginx) 已就绪"
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
        echo -n "."
    done
    echo ""
    log_error "Nginx (campusask-nginx) 等待超时 (${max_wait}s)"
    return 1
}
wait_for_nginx &

set +e
wait
HEALTH_EXIT=$?
set -e

if [ $HEALTH_EXIT -ne 0 ]; then
    log_error "部分服务健康检查失败，请检查日志: $DOCKER_COMPOSE_CMD logs"
    exit 1
fi

# ==================== 5. 显示结果 ====================
log_step "5. 启动完成"

echo ""
echo -e "${BLUE}${BOLD}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}${BOLD}║          CampusAsk-RAG 服务已启动 (生产环境)           ║${NC}"
echo -e "${BLUE}${BOLD}╠════════════════════════════════════════════════════════╣${NC}"
echo -e "${BLUE}${BOLD}║${NC}                                                        ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}  ${GREEN}前端页面:${NC}            http://服务器IP                 ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}  ${GREEN}API 健康检查:${NC}        http://服务器IP/api/health       ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}                                                        ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}  ${YELLOW}所有内部服务端口（3306/6379/19530 等）已隐藏${NC}        ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}  ${YELLOW}仅通过 Nginx (80/443) 统一对外提供服务${NC}              ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}                                                        ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}  默认管理员账号: ${YELLOW}admin${NC}                               ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}  (请登录后立即修改密码)                                  ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}                                                        ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

log_info "查看日志: $DOCKER_COMPOSE_CMD -f docker-compose.prod.yml logs -f [service_name]"
log_info "停止服务: ./stop.sh"
echo ""
