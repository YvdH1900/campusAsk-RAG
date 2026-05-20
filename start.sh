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

# ==================== 2. 检查本地服务 ====================
log_step "2. 检查本地服务状态"

# 检测端口是否开放
check_port() {
    local port=$1
    local service=$2
    
    if nc -z localhost $port 2>/dev/null || (echo > /dev/tcp/localhost/$port) 2>/dev/null; then
        log_info "${service} (端口 $port) - 已运行"
        return 0
    else
        log_error "${service} (端口 $port) - 未运行"
        return 1
    fi
}

declare -a FAILED_SERVICES
declare -a FAILED_PORTS

SERVICES=("MySQL:3306" "Redis:6379" "RabbitMQ:5672")

for service_info in "${SERVICES[@]}"; do
    IFS=':' read -r service port <<< "$service_info"
    if ! check_port $port "$service"; then
        FAILED_SERVICES+=("$service")
        FAILED_PORTS+=("$port")
    fi
done

if [ ${#FAILED_SERVICES[@]} -gt 0 ]; then
    echo ""
    log_warn "检测到以下服务未运行："
    for i in "${!FAILED_SERVICES[@]}"; do
        echo "   - ${FAILED_SERVICES[$i]} (端口 ${FAILED_PORTS[$i]})"
    done
    echo ""
    
    # 检查是否所有服务都未运行
    if [ ${#FAILED_SERVICES[@]} -eq ${#SERVICES[@]} ]; then
        log_info "所有基础服务（MySQL、Redis、RabbitMQ）均未运行"
        read -p "是否使用 Docker 一键安装并启动所有服务？(y/n): " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "将安装所有服务：${FAILED_SERVICES[*]}"
            INSTALL_ALL=true
        else
            echo ""
            log_warn "已跳过自动安装"
            log_info "💡 请手动启动以下服务后重新运行此脚本："
            for service in "${FAILED_SERVICES[@]}"; do
                log_info "   - ${service}"
            done
            echo ""
            log_info "📦 如需使用 Docker 安装，可以运行："
            log_info "   docker-compose -f docker-compose.services.yml up -d"
            echo ""
            exit 1
        fi
    else
        # 部分服务未运行，逐个询问
        log_info "检测到部分服务未运行，将逐个确认安装需求"
        echo ""
        
        declare -a SERVICES_TO_INSTALL
        declare -a PORTS_TO_INSTALL
        
        for i in "${!FAILED_SERVICES[@]}"; do
            service="${FAILED_SERVICES[$i]}"
            port="${FAILED_PORTS[$i]}"
            
            read -p "是否使用 Docker 安装并启动 ${service}？(y/n): " -n 1 -r
            echo
            
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                SERVICES_TO_INSTALL+=("$service")
                PORTS_TO_INSTALL+=("$port")
                log_info "✓ 已选择安装 ${service}"
            else
                echo ""
                log_warn "已跳过安装 ${service}"
                log_info "💡 请手动启动 ${service} 后重新运行此脚本"
                log_info "📦 如需使用 Docker 安装 ${service}，可以运行："
                
                case $service in
                    "MySQL")
                        log_info "   docker run -d --name campusask_mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=root -e MYSQL_DATABASE=campus_ask mysql:8.0"
                        ;;
                    "Redis")
                        log_info "   docker run -d --name campusask_redis -p 6379:6379 redis:7-alpine"
                        ;;
                    "RabbitMQ")
                        log_info "   docker run -d --name campusask_rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management-alpine"
                        ;;
                esac
                echo ""
                exit 1
            fi
        done
    fi
    
    # 安装选中的服务
    if [ ${#SERVICES_TO_INSTALL[@]} -gt 0 ]; then
        log_step "2.1 使用 Docker 安装选中的服务..."
        
        # 检查是否安装所有服务
        if [ "$INSTALL_ALL" = true ]; then
            # 使用现有的 docker-compose.services.yml
            if [ ! -f "docker-compose.services.yml" ]; then
                log_error "未找到 docker-compose.services.yml 文件"
                exit 1
            fi
            COMPOSE_FILE="docker-compose.services.yml"
        else
            # 创建临时的 docker-compose 配置，只包含选中的服务
            cat > docker-compose.temp.yml << 'EOF'
version: '3.8'

services:
EOF
            
            for i in "${!SERVICES_TO_INSTALL[@]}"; do
                service="${SERVICES_TO_INSTALL[$i]}"
                
                case $service in
                    "MySQL")
                        cat >> docker-compose.temp.yml << 'EOF'
  mysql:
    image: mysql:8.0
    container_name: campusask_mysql
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: campus_ask
      TZ: Asia/Shanghai
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci

EOF
                        ;;
                    "Redis")
                        cat >> docker-compose.temp.yml << 'EOF'
  redis:
    image: redis:7-alpine
    container_name: campusask_redis
    restart: always
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

EOF
                        ;;
                    "RabbitMQ")
                        cat >> docker-compose.temp.yml << 'EOF'
  rabbitmq:
    image: rabbitmq:3-management-alpine
    container_name: campusask_rabbitmq
    restart: always
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest
    ports:
      - "5672:5672"
      - "15672:15672"
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq

EOF
                        ;;
                esac
            done
            
            cat >> docker-compose.temp.yml << 'EOF'
volumes:
  mysql_data:
  redis_data:
  rabbitmq_data:
EOF
            
            log_info "已创建临时 Docker Compose 配置文件：docker-compose.temp.yml"
            COMPOSE_FILE="docker-compose.temp.yml"
        fi
        
        # 启动服务
        log_info "正在启动选中的服务..."
        $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" up -d
        
        log_info "等待服务启动 (约 30-60 秒)..."
        WAITED=0
        MAX_WAIT=90
        
        while [ $WAITED -lt $MAX_WAIT ]; do
            PROGRESS=$((WAITED * 100 / MAX_WAIT))
            FILLED=$((PROGRESS / 5))
            EMPTY=$((20 - FILLED))
            echo -ne "\r[$(printf '=%.0s' $(seq 1 $FILLED))$(printf ' %.0s' $(seq 1 $EMPTY))] ${PROGRESS}% (${WAITED}秒/${MAX_WAIT}秒)"
            sleep 5
            WAITED=$((WAITED + 5))
        done
        echo ""
        
        # 验证服务是否启动成功
        ALL_SERVICES_READY=true
        for i in "${!SERVICES_TO_INSTALL[@]}"; do
            service="${SERVICES_TO_INSTALL[$i]}"
            port="${PORTS_TO_INSTALL[$i]}"
            
            if nc -z localhost $port 2>/dev/null || (echo > /dev/tcp/localhost/$port) 2>/dev/null; then
                log_info "${service} (端口 $port) - 已启动"
            else
                log_warn "${service} (端口 $port) - 仍未响应，请稍后检查"
                ALL_SERVICES_READY=false
            fi
        done
        
        if [ "$ALL_SERVICES_READY" = true ]; then
            log_info "✅ 所有选中的服务已成功启动！"
        else
            log_warn "⚠️ 部分服务可能还未完全就绪，请稍候重试"
            log_info "💡 可以使用以下命令查看服务状态："
            log_info "   docker ps"
            for service in "${SERVICES_TO_INSTALL[@]}"; do
                log_info "   docker logs campusask_$(echo $service | tr '[:upper:]' '[:lower:]')"
            done
        fi
        
        # 清理临时文件
        if [ "$INSTALL_ALL" != true ] && [ -f "docker-compose.temp.yml" ]; then
            rm -f docker-compose.temp.yml
            log_info "已清理临时配置文件"
        fi
    fi
fi

if [ ! -f "backend/.env" ]; then
    if [ -f "backend/.env.example" ]; then
        cp backend/.env.example backend/.env
        log_warn "已从 .env.example 复制 .env 文件，请根据需要修改配置"
        log_warn "特别需要设置: DASHSCOPE_API_KEY（通义千问API密钥）"
        log_warn "             SECRET_KEY（JWT加密密钥）"
        log_warn "             MYSQL_ROOT_PASSWORD（MySQL root密码）"
    else
        log_error "未找到 backend/.env.example，请手动创建 backend/.env"
        exit 1
    fi
else
    log_info ".env 文件已存在"
fi

# 确保 volumes 目录存在
mkdir -p volumes/mysql volumes/redis volumes/rabbitmq volumes/etcd volumes/minio volumes/milvus volumes/uploads

# ==================== 3. 启动 Docker 服务 ====================
log_step "3. 启动所有 Docker 服务"

$DOCKER_COMPOSE_CMD --profile full down --remove-orphans 2>/dev/null || true

log_info "正在构建镜像并启动服务（首次需 10-15 分钟，后续使用缓存）..."
$DOCKER_COMPOSE_CMD --profile full up -d --build

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

wait_for_service "milvus-standalone" "Milvus" 180 &

wait_for_service "campusask-mysql" "MySQL" 120 &
wait_for_service "campusask-redis" "Redis" 60 &
wait_for_service "campusask-rabbitmq" "RabbitMQ" 60 &

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
echo -e "${BLUE}${BOLD}║          CampusAsk-RAG 服务已启动                      ║${NC}"
echo -e "${BLUE}${BOLD}╠════════════════════════════════════════════════════════╣${NC}"
echo -e "${BLUE}${BOLD}║${NC}                                                        ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}  ${GREEN}API 文档 (Swagger):${NC}  http://localhost:8000/docs         ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}  ${GREEN}API 文档 (ReDoc):${NC}    http://localhost:8000/redoc        ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}  ${GREEN}健康检查:${NC}            http://localhost:8000/health        ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}  ${GREEN}RabbitMQ 管理面板:${NC}    http://localhost:15672            ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}  ${GREEN}MinIO 控制台:${NC}        http://localhost:9001              ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}                                                        ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}  默认管理员账号: ${YELLOW}admin${NC}                               ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}  管理员密码请查看环境变量或启动日志              ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}  (请登录后立即修改密码)                                  ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}║${NC}                                                        ${BLUE}${BOLD}║${NC}"
echo -e "${BLUE}${BOLD}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

log_info "查看日志: $DOCKER_COMPOSE_CMD logs -f [service_name]"
log_info "停止服务: $DOCKER_COMPOSE_CMD --profile full down"
echo ""
