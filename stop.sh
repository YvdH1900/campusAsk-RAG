#!/usr/bin/env bash
# ================================================
# CampusAsk-RAG Stop Script (Linux)
# ================================================
# Usage:
#   chmod +x stop.sh
#   ./stop.sh              # stop containers, keep data
#   ./stop.sh --clean      # stop containers + delete ALL volumes/data
# ================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "\n${BLUE}>>> $1${NC}"; }

DOCKER_COMPOSE_CMD="docker compose"
if ! docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
fi

CLEAN=false
if [ "$1" = "--clean" ] || [ "$1" = "-c" ]; then
    CLEAN=true
fi

# ==================== 1. Stop containers ====================
log_step "1. 停止所有 Docker 服务..."

if [ "$CLEAN" = true ]; then
    log_warn "将删除所有数据卷（MySQL、Redis、Milvus、上传文件等）"
    read -p "确认删除所有数据？[y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        $DOCKER_COMPOSE_CMD --profile full down -v --remove-orphans
        log_info "所有容器和数据卷已删除"
        rm -rf volumes/ uploads/
        log_info "本地 volumes/ 目录已清理"
    else
        $DOCKER_COMPOSE_CMD --profile full down --remove-orphans
        log_info "已取消删除数据卷，仅停止容器"
    fi
else
    $DOCKER_COMPOSE_CMD --profile full down --remove-orphans
    log_info "所有容器已停止（数据保留）"
fi

# ==================== 2. Done ====================
log_step "2. 关闭完成"

echo ""
echo -e "${GREEN}  ✓  CampusAsk-RAG 已停止${NC}"
echo ""
if [ "$CLEAN" = false ]; then
    echo -e "  ${YELLOW}提示：${NC} 数据已保留，下次启动可直接恢复"
    echo -e "  ${YELLOW}彻底清理：${NC} ./stop.sh --clean"
fi
echo ""
