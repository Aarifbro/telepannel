#!/bin/bash

# Process manager for 24/7 bot operation with health checks and auto-restart

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
LOG_DIR="${DIR}/logs"
PID_FILE="${DIR}/bot.pid"
HEALTH_CHECK_INTERVAL=60  # Check every 60 seconds
MAX_MEMORY_MB=500        # Restart if memory usage exceeds this
MAX_UPTIME_HOURS=24      # Restart daily for health

# Create logs directory
mkdir -p "${LOG_DIR}"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_DIR}/manager.log"
}

# Check if bot process is running
is_bot_running() {
    if [ -f "${PID_FILE}" ]; then
        local pid=$(cat "${PID_FILE}")
        if ps -p $pid > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Start the bot
start_bot() {
    log "Starting bot..."
    
    # Setup environment
    source "${DIR}/.venv/bin/activate"
    
    # Start bot in background
    python "${DIR}/main.py" >> "${LOG_DIR}/bot.log" 2>> "${LOG_DIR}/bot_error.log" &
    local pid=$!
    echo $pid > "${PID_FILE}"
    
    log "Bot started with PID: ${pid}"
    echo $pid
}

# Stop the bot
stop_bot() {
    if [ -f "${PID_FILE}" ]; then
        local pid=$(cat "${PID_FILE}")
        log "Stopping bot (PID: ${pid})..."
        
        kill -TERM $pid 2>/dev/null || true
        sleep 5
        
        if ps -p $pid > /dev/null 2>&1; then
            kill -KILL $pid 2>/dev/null || true
        fi
        
        rm -f "${PID_FILE}"
        log "Bot stopped"
    fi
}

# Health check function
health_check() {
    if ! is_bot_running; then
        return 1
    fi
    
    local pid=$(cat "${PID_FILE}")
    
    # Check memory usage
    local memory_kb=$(ps -o rss= -p $pid 2>/dev/null || echo "0")
    local memory_mb=$((memory_kb / 1024))
    
    if [ $memory_mb -gt $MAX_MEMORY_MB ]; then
        log "Bot memory usage too high: ${memory_mb}MB > ${MAX_MEMORY_MB}MB"
        return 2
    fi
    
    # Check uptime
    local start_time=$(ps -o lstart= -p $pid 2>/dev/null || echo "")
    if [ ! -z "$start_time" ]; then
        local uptime_hours=$(( ($(date +%s) - $(date -d "$start_time" +%s)) / 3600 ))
        if [ $uptime_hours -gt $MAX_UPTIME_HOURS ]; then
            log "Bot uptime too long: ${uptime_hours}h > ${MAX_UPTIME_HOURS}h"
            return 3
        fi
    fi
    
    return 0
}

# Main management loop
manage_bot() {
    log "Starting bot process manager..."
    log "Health check interval: ${HEALTH_CHECK_INTERVAL}s"
    log "Memory limit: ${MAX_MEMORY_MB}MB"
    log "Uptime limit: ${MAX_UPTIME_HOURS}h"
    
    # Initial start
    start_bot
    
    # Management loop
    while true; do
        sleep $HEALTH_CHECK_INTERVAL
        
        health_check
        local health_status=$?
        
        case $health_status in
            1)  # Bot not running
                log "Bot not running, restarting..."
                start_bot
                ;;
            2)  # Memory limit exceeded
                log "Restarting bot due to high memory usage"
                stop_bot
                sleep 5
                start_bot
                ;;
            3)  # Uptime limit exceeded
                log "Restarting bot for daily health maintenance"
                stop_bot
                sleep 5
                start_bot
                ;;
            0)  # All good
                local pid=$(cat "${PID_FILE}")
                local memory_kb=$(ps -o rss= -p $pid 2>/dev/null || echo "0")
                local memory_mb=$((memory_kb / 1024))
                log "Health check OK - PID: ${pid}, Memory: ${memory_mb}MB"
                ;;
        esac
    done
}

# Handle script termination
cleanup() {
    log "Process manager shutting down..."
    stop_bot
    exit 0
}

trap cleanup SIGTERM SIGINT

# Check command line arguments
case "${1:-start}" in
    start)
        manage_bot
        ;;
    stop)
        stop_bot
        ;;
    restart)
        stop_bot
        sleep 2
        start_bot
        ;;
    status)
        if is_bot_running; then
            local pid=$(cat "${PID_FILE}")
            echo "Bot is running (PID: ${pid})"
        else
            echo "Bot is not running"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac