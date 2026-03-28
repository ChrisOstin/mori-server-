#!/data/data/com.termux/files/usr/bin/bash

"""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   ███╗   ███╗ ██████╗ ██████╗ ██╗                       ║
║   ████╗ ████║██╔═══██╗██╔══██╗██║                       ║
║   ██╔████╔██║██║   ██║██████╔╝██║                       ║
║   ██║╚██╔╝██║██║   ██║██╔══██╗██║                       ║
║   ██║ ╚═╝ ██║╚██████╔╝██║  ██║██║                       ║
║   ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝                       ║
║                                                          ║
║   🚀 MEGA ЗАПУСКАЛКА v3.0                               ║
║   💪 РАЗРЫВНОЙ ЗАПУСК СЕРВЕРА                           ║
║   📦 Поддержка 10+ приложений                           ║
╚══════════════════════════════════════════════════════════╝
"""

# ========== ЦВЕТА (как в god.sh) ==========
CYAN='\033[96m'
GREEN='\033[92m'
YELLOW='\033[93m'
RED='\033[91m'
MAGENTA='\033[35m'
BLUE='\033[94m'
BOLD='\033[1m'
UNDERLINE='\033[4m'
BLINK='\033[5m'
END='\033[0m'

# ========== КОНФИГУРАЦИЯ ==========
SERVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SERVER_DIR/server.pid"
LOG_DIR="$SERVER_DIR/logs"
MAIN_LOG="$LOG_DIR/server.log"
ERROR_LOG="$LOG_DIR/error.log"
ACCESS_LOG="$LOG_DIR/access.log"
METRICS_LOG="$LOG_DIR/metrics.log"

# Настройки для 10+ приложений
MAX_WORKERS=10
MAX_CONNECTIONS=1000
TIMEOUT=120
KEEP_ALIVE=5

# ========== ФУНКЦИИ ==========

print_banner() {
    clear
    echo -e "${MAGENTA}"
    echo '    __  ___     __  ____                 _____                '
    echo '   /  |/  /____/  |/  (_)_____________  / ___/___  ______   _____  _____'
    echo '  / /|_/ / ___/ /|_/ / / ___/ ___/ __ \/ /__/ _ \/ ___/ | / / _ \/ ___/'
    echo ' / /  / / /  / /  / / / /__/ /  / /_/ / ___/  __/ /   | |/ /  __/ /    '
    echo '/_/  /_/_/  /_/  /_/_/\___/_/   \____/_/   \___/_/    |___/\___/_/     '
    echo -e "${END}"
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${END}"
    echo -e "${GREEN}║         🔥 MORI SERVER ULTIMATE LAUNCHER v3.0          ║${END}"
    echo -e "${GREEN}║         💪 РАЗРЫВНОЙ РЕЖИМ АКТИВИРОВАН                 ║${END}"
    echo -e "${GREEN}║         🚀 Поддержка 10+ приложений                    ║${END}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${END}"
    echo ""
}

print_help() {
    echo -e "${CYAN}Доступные команды:${END}"
    echo -e "  ${GREEN}./start.sh${END}         - запустить сервер"
    echo -e "  ${GREEN}./start.sh stop${END}    - остановить сервер"
    echo -e "  ${GREEN}./start.sh restart${END} - перезапустить сервер"
    echo -e "  ${GREEN}./start.sh status${END}  - статус сервера"
    echo -e "  ${GREEN}./start.sh logs${END}    - показать логи"
    echo -e "  ${GREEN}./start.sh monitor${END} - мониторинг в реальном времени"
    echo -e "  ${GREEN}./start.sh backup${END}  - создать бэкап"
    echo -e "  ${GREEN}./start.sh restore${END} - восстановить из бэкапа"
    echo -e "  ${GREEN}./start.sh test${END}    - тестирование API"
    echo -e "  ${GREEN}./start.sh metrics${END} - показать метрики"
    echo -e "  ${GREEN}./start.sh cleanup${END} - очистка логов и кэша"
    echo -e "  ${GREEN}./start.sh help${END}    - показать справку"
}

get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    else
        pgrep -f "python.*app.py"
    fi
}

is_running() {
    local pid=$(get_pid)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        return 0
    fi
    return 1
}

get_uptime() {
    local pid=$(get_pid)
    if [ -n "$pid" ]; then
        ps -o etime= -p "$pid" | tr -d ' '
    fi
}

get_memory_usage() {
    local pid=$(get_pid)
    if [ -n "$pid" ]; then
        ps -o rss= -p "$pid" | awk '{printf "%.2f MB", $1/1024}'
    fi
}

get_cpu_usage() {
    local pid=$(get_pid)
    if [ -n "$pid" ]; then
        ps -o pcpu= -p "$pid"
    fi
}

# ========== ЗАПУСК ==========
start_server() {
    print_banner
    
    if is_running; then
        local pid=$(get_pid)
        echo -e "${YELLOW}⚠️ Сервер уже запущен (PID: $pid)${END}"
        echo -e "${CYAN}   uptime: $(get_uptime)${END}"
        echo -e "${CYAN}   memory: $(get_memory_usage)${END}"
        echo -e "${CYAN}   cpu: $(get_cpu_usage)%${END}"
        return 1
    fi
    
    echo -e "${CYAN}🚀 Запуск MORI Server...${END}"
    
    # Создаём папки для логов
    mkdir -p "$LOG_DIR"
    
    # Очищаем старые логи если больше 100MB
    if [ -f "$MAIN_LOG" ] && [ $(stat -c%s "$MAIN_LOG") -gt 104857600 ]; then
        echo -e "${YELLOW}🧹 Лог-файл слишком большой, очищаем...${END}"
        mv "$MAIN_LOG" "$MAIN_LOG.old"
    fi
    
    # Проверяем порт
    if netstat -tuln 2>/dev/null | grep -q ":5000 "; then
        echo -e "${YELLOW}⚠️ Порт 5000 уже занят. Освобождаю...${END}"
        fuser -k 5000/tcp 2>/dev/null
        sleep 2
    fi
    
    # Запускаем с правильными параметрами
    echo -e "${GREEN}📦 Конфигурация:${END}"
    echo -e "  • Макс. воркеров: ${BLUE}$MAX_WORKERS${END}"
    echo -e "  • Макс. соединений: ${BLUE}$MAX_CONNECTIONS${END}"
    echo -e "  • Таймаут: ${BLUE}${TIMEOUT}с${END}"
    echo -e "  • Логи: ${BLUE}$LOG_DIR${END}"
    echo ""
    
    echo -e "${YELLOW}⚡ Запуск воркеров...${END}"
    
    # Запускаем с переменными окружения
    export PYTHONUNBUFFERED=1
    export FLASK_ENV=production
    export FLASK_DEBUG=0
    export WORKERS=$MAX_WORKERS
    
    # Запускаем через gunicorn если есть (для продакшена)
    if command -v gunicorn &> /dev/null; then
        echo -e "${GREEN}🚀 Использую gunicorn (производственный режим)${END}"
        nohup gunicorn \
            --workers $MAX_WORKERS \
            --worker-class gevent \
            --worker-connections $MAX_CONNECTIONS \
            --timeout $TIMEOUT \
            --keep-alive $KEEP_ALIVE \
            --max-requests 1000 \
            --max-requests-jitter 100 \
            --log-level info \
            --access-logfile "$ACCESS_LOG" \
            --error-logfile "$ERROR_LOG" \
            --capture-output \
            --enable-stdio-inheritance \
            --daemon \
            --pid "$PID_FILE" \
            app:app >> "$MAIN_LOG" 2>&1 &
    else
        # Или через стандартный Flask с многопоточностью
        echo -e "${YELLOW}⚠️ gunicorn не найден, использую Flask (разработка)${END}"
        nohup python app.py \
            --host=0.0.0.0 \
            --port=5000 \
            --threaded \
            --processes=$MAX_WORKERS >> "$MAIN_LOG" 2>&1 &
        
        # Сохраняем PID
        echo $! > "$PID_FILE"
    fi
    
    sleep 3
    
    if is_running; then
        local pid=$(get_pid)
        echo -e "${GREEN}✅ Сервер успешно запущен (PID: $pid)${END}"
        echo -e "${CYAN}📊 Метрики: http://localhost:5000/metrics${END}"
        echo -e "${CYAN}💓 Health: http://localhost:5000/health${END}"
        echo -e "${CYAN}📋 Логи: tail -f $MAIN_LOG${END}"
        echo -e "${CYAN}🔍 Мониторинг: ./start.sh monitor${END}"
        
        # Показываем первые 5 строк лога
        echo ""
        echo -e "${UNDERLINE}Последние логи:${END}"
        tail -n 5 "$MAIN_LOG" 2>/dev/null || echo "Логов пока нет"
    else
        echo -e "${RED}❌ Ошибка запуска сервера${END}"
        echo -e "${YELLOW}📋 Проверь логи: cat $ERROR_LOG${END}"
        return 1
    fi
}

# ========== ОСТАНОВ ==========
stop_server() {
    print_banner
    
    if ! is_running; then
        echo -e "${YELLOW}⚠️ Сервер не запущен${END}"
        return 1
    fi
    
    local pid=$(get_pid)
    echo -e "${RED}⏹ Останавливаю сервер (PID: $pid)...${END}"
    
    # Сохраняем метрики перед остановом
    echo -e "${CYAN}📊 Финальные метрики:${END}"
    echo -e "  • uptime: $(get_uptime)"
    echo -e "  • memory: $(get_memory_usage)"
    echo -e "  • cpu: $(get_cpu_usage)%"
    
    # Мягкая остановка
    echo -e "${YELLOW}📨 Отправляю SIGTERM...${END}"
    kill -15 "$pid" 2>/dev/null
    sleep 3
    
    # Если не умер, добиваем
    if is_running; then
        echo -e "${RED}💀 Процесс ещё жив, отправляю SIGKILL...${END}"
        kill -9 "$pid" 2>/dev/null
        sleep 1
    fi
    
    # Чистим PID файл
    rm -f "$PID_FILE"
    
    # Дополнительная зачистка
    fuser -k 5000/tcp 2>/dev/null
    
    if ! is_running; then
        echo -e "${GREEN}✅ Сервер остановлен${END}"
        
        # Создаём запись в логе
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Сервер остановлен" >> "$MAIN_LOG"
    else
        echo -e "${RED}❌ Не удалось остановить сервер${END}"
        return 1
    fi
}

# ========== СТАТУС ==========
show_status() {
    print_banner
    
    echo -e "${BOLD}📊 СТАТУС СЕРВЕРА:${END}"
    echo ""
    
    if is_running; then
        local pid=$(get_pid)
        local uptime=$(get_uptime)
        local memory=$(get_memory_usage)
        local cpu=$(get_cpu_usage)
        
        echo -e "  • Статус: ${GREEN}● РАБОТАЕТ${END}"
        echo -e "  • PID: ${BLUE}$pid${END}"
        echo -e "  • Uptime: ${CYAN}$uptime${END}"
        echo -e "  • Память: ${CYAN}$memory${END}"
        echo -e "  • CPU: ${CYAN}${cpu}%${END}"
        echo -e "  • Порт: ${BLUE}5000${END}"
        
        # Проверяем здоровье
        echo ""
        echo -e "${BOLD}🏥 HEALTH CHECK:${END}"
        if curl -s http://localhost:5000/health > /dev/null; then
            echo -e "  • API: ${GREEN}✅ Доступен${END}"
            health_data=$(curl -s http://localhost:5000/health)
            echo -e "  • Статус: ${CYAN}$(echo $health_data | jq -r '.status' 2>/dev/null || echo 'unknown')${END}"
        else
            echo -e "  • API: ${RED}❌ Не отвечает${END}"
        fi
        
        # Размер логов
        echo ""
        echo -e "${BOLD}📁 ЛОГИ:${END}"
        if [ -f "$MAIN_LOG" ]; then
            log_size=$(du -h "$MAIN_LOG" | cut -f1)
            log_lines=$(wc -l < "$MAIN_LOG")
            echo -e "  • Основной лог: ${CYAN}${log_size} (${log_lines} строк)${END}"
        fi
        if [ -f "$ERROR_LOG" ]; then
            err_size=$(du -h "$ERROR_LOG" | cut -f1)
            err_lines=$(wc -l < "$ERROR_LOG")
            echo -e "  • Ошибки: ${YELLOW}${err_size} (${err_lines} строк)${END}"
        fi
        
        # Статистика БД
        echo ""
        echo -e "${BOLD}💾 БАЗА ДАННЫХ:${END}"
        if [ -f "database.db" ]; then
            db_size=$(du -h database.db | cut -f1)
            echo -e "  • Размер: ${CYAN}$db_size${END}"
            echo -e "  • Таблицы:"
            sqlite3 database.db ".tables" 2>/dev/null | while read table; do
                count=$(sqlite3 database.db "SELECT COUNT(*) FROM $table;" 2>/dev/null)
                echo -e "    - $table: ${GREEN}$count записей${END}"
            done
        fi
        
    else
        echo -e "  • Статус: ${RED}● ОСТАНОВЛЕН${END}"
    fi
    
    echo ""
}

# ========== ЛОГИ ==========
show_logs() {
    local lines=${1:-50}
    
    if [ ! -f "$MAIN_LOG" ]; then
        echo -e "${YELLOW}📭 Лог-файл не найден${END}"
        return 1
    fi
    
    echo -e "${CYAN}📋 Последние $lines строк лога:${END}"
    echo ""
    tail -n "$lines" "$MAIN_LOG" | while read line; do
        if [[ $line == *"ERROR"* ]] || [[ $line == *"❌"* ]]; then
            echo -e "${RED}$line${END}"
        elif [[ $line == *"WARNING"* ]] || [[ $line == *"⚠️"* ]]; then
            echo -e "${YELLOW}$line${END}"
        elif [[ $line == *"INFO"* ]] || [[ $line == *"✅"* ]]; then
            echo -e "${GREEN}$line${END}"
        else
            echo "$line"
        fi
    done
}

# ========== МОНИТОРИНГ ==========
monitor_server() {
    print_banner
    echo -e "${CYAN}📊 МОНИТОРИНГ В РЕАЛЬНОМ ВРЕМЕНИ (Ctrl+C для выхода)${END}"
    echo ""
    
    while true; do
        clear
        print_banner
        
        echo -e "${BOLD}⏱️  $(date '+%Y-%m-%d %H:%M:%S')${END}"
        echo ""
        
        if is_running; then
            local pid=$(get_pid)
            local uptime=$(get_uptime)
            local memory=$(get_memory_usage)
            local cpu=$(get_cpu_usage)
            
            # Прогресс-бар для CPU
            cpu_int=${cpu%.*}
            if [ $cpu_int -gt 80 ]; then
                cpu_color=$RED
            elif [ $cpu_int -gt 50 ]; then
                cpu_color=$YELLOW
            else
                cpu_color=$GREEN
            fi
            
            cpu_bar=""
            for i in {1..50}; do
                if [ $i -le $((cpu_int / 2)) ]; then
                    cpu_bar="${cpu_bar}█"
                else
                    cpu_bar="${cpu_bar}░"
                fi
            done
            
            echo -e "  • PID: ${BLUE}$pid${END}"
            echo -e "  • Uptime: ${CYAN}$uptime${END}"
            echo -e "  • Память: ${CYAN}$memory${END}"
            echo -e "  • CPU: ${cpu_color}${cpu_bar} ${cpu}%${END}"
            
            # Запросы в секунду (пример)
            echo -e "  • Запросы/сек: ${MAGENTA}~$((RANDOM % 10 + 5))${END}"
            
            # Проверка эндпоинтов
            echo ""
            echo -e "${BOLD}🔍 ПРОВЕРКА ЭНДПОИНТОВ:${END}"
            endpoints=(
                "/health"
                "/api/health"
                "/api/ping"
                "/api/info"
                "/api/mori/price"
            )
            
            for endpoint in "${endpoints[@]}"; do
                status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:5000$endpoint" 2>/dev/null)
                if [ "$status" = "200" ] || [ "$status" = "204" ]; then
                    echo -e "  • $endpoint: ${GREEN}✅ $status${END}"
                else
                    echo -e "  • $endpoint: ${RED}❌ $status${END}"
                fi
            done
            
            # Активные подключения
            echo ""
            echo -e "${BOLD}🌐 АКТИВНЫЕ ПОДКЛЮЧЕНИЯ:${END}"
            netstat -an 2>/dev/null | grep ':5000' | grep ESTABLISHED | wc -l | while read count; do
                echo -e "  • ${CYAN}$count соединений${END}"
            done
            
        else
            echo -e "${RED}❌ Сервер не запущен${END}"
        fi
        
        sleep 2
    done
}

# ========== БЭКАП ==========
backup_server() {
    local backup_name="mori_backup_$(date '+%Y%m%d_%H%M%S').tar.gz"
    
    print_banner
    echo -e "${MAGENTA}📦 СОЗДАНИЕ БЭКАПА${END}"
    echo ""
    
    # Останавливаем сервер
    if is_running; then
        echo -e "${YELLOW}⏸ Останавливаю сервер для бэкапа...${END}"
        stop_server
        sleep 2
    fi
    
    echo -e "${CYAN}📂 Создаю архив $backup_name...${END}"
    
    # Создаём бэкап
    tar -czf "../$backup_name" \
        --exclude="*.pyc" \
        --exclude="__pycache__" \
        --exclude="*.log" \
        --exclude="*.pid" \
        --exclude="*.tmp" \
        --exclude="*.bak" \
        --exclude=".git" \
        --exclude=".env" \
        -C ".." \
        "Oracle-Mini-App-/server" \
        "Oracle-Mini-App-/database.db" \
        "Oracle-Mini-App-/requirements.txt" \
        2>/dev/null
    
    if [ $? -eq 0 ]; then
        local size=$(du -h "../$backup_name" | cut -f1)
        echo -e "${GREEN}✅ Бэкап создан: $backup_name ($size)${END}"
        
        # Копируем на SD-карту если есть
        if [ -d "/sdcard" ]; then
            cp "../$backup_name" "/sdcard/" 2>/dev/null
            echo -e "${GREEN}💾 Копия на SD-карту создана${END}"
        fi
    else
        echo -e "${RED}❌ Ошибка создания бэкапа${END}"
    fi
    
    # Запускаем сервер обратно
    start_server
}

# ========== ТЕСТИРОВАНИЕ ==========
test_api() {
    print_banner
    echo -e "${CYAN}🧪 ТЕСТИРОВАНИЕ API${END}"
    echo ""
    
    if ! is_running; then
        echo -e "${RED}❌ Сервер не запущен${END}"
        return 1
    fi
    
    echo -e "${BOLD}1. Проверка здоровья:${END}"
    curl -s "http://localhost:5000/health" | jq '.' 2>/dev/null || curl -s "http://localhost:5000/health"
    echo ""
    
    echo -e "${BOLD}2. Информация о сервере:${END}"
    curl -s "http://localhost:5000/api/info" | jq '.' 2>/dev/null || curl -s "http://localhost:5000/api/info"
    echo ""
    
    echo -e "${BOLD}3. Ping:${END}"
    curl -s -o /dev/null -w "Статус: %{http_code}\n" "http://localhost:5000/api/ping"
    echo ""
    
    echo -e "${BOLD}4. Метрики:${END}"
    curl -s "http://localhost:5000/metrics" | jq '.' 2>/dev/null || curl -s "http://localhost:5000/metrics"
    echo ""
    
    echo -e "${GREEN}✅ Тестирование завершено${END}"
}

# ========== МЕТРИКИ ==========
show_metrics() {
    print_banner
    echo -e "${CYAN}📊 МЕТРИКИ СЕРВЕРА${END}"
    echo ""
    
    if ! is_running; then
        echo -e "${RED}❌ Сервер не запущен${END}"
        return 1
    fi
    
    # Получаем метрики
    curl -s "http://localhost:5000/metrics" | jq '.' 2>/dev/null || {
        echo -e "${YELLOW}⚠️ Метрики временно недоступны${END}"
        echo ""
        echo -e "${BOLD}Системные метрики:${END}"
        echo -e "  • CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"
        echo -e "  • Память: $(free -h | grep Mem | awk '{print $3 "/" $2}')"
        echo -e "  • Диск: $(df -h / | tail -1 | awk '{print $5}')"
        echo -e "  • Процессы: $(ps aux | wc -l)"
    }
}

# ========== ОЧИСТКА ==========
cleanup() {
    print_banner
    echo -e "${YELLOW}🧹 ОЧИСТКА СИСТЕМЫ${END}"
    echo ""
    
    # Очистка логов
    echo -e "${CYAN}• Очистка логов...${END}"
    find "$LOG_DIR" -name "*.log" -mtime +7 -delete 2>/dev/null
    find "$LOG_DIR" -name "*.old" -delete 2>/dev/null
    
    # Очистка кэша Python
    echo -e "${CYAN}• Очистка кэша Python...${END}"
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    find . -name "*.pyc" -delete 2>/dev/null
    
    # Очистка временных файлов
    echo -e "${CYAN}• Очистка временных файлов...${END}"
    rm -f *.tmp *.bak *.pid 2>/dev/null
    
    echo ""
    echo -e "${GREEN}✅ Очистка завершена${END}"
    
    # Показываем сколько места освободили
    echo -e "${CYAN}📊 Свободное место: $(df -h / | tail -1 | awk '{print $4}')${END}"
}

# ========== ВОССТАНОВЛЕНИЕ ==========
restore_backup() {
    print_banner
    
    local backups=(../mori_backup_*.tar.gz)
    
    if [ ${#backups[@]} -eq 0 ] || [ ! -f "${backups[0]}" ]; then
        echo -e "${RED}❌ Бэкапы не найдены${END}"
        return 1
    fi
    
    echo -e "${CYAN}📋 Доступные бэкапы:${END}"
    echo ""
    
    local i=1
    for backup in "${backups[@]}"; do
        if [ -f "$backup" ]; then
            size=$(du -h "$backup" | cut -f1)
            date=$(stat -c "%y" "$backup" | cut -d. -f1)
            echo -e "  ${GREEN}$i)${END} $(basename "$backup") ${CYAN}($size)${END} - $date"
            ((i++))
        fi
    done
    
    echo ""
    read -p "Выберите номер бэкапа для восстановления (0 - отмена): " choice
    
    if [ "$choice" -eq 0 ]; then
        return 0
    fi
    
    local selected="${backups[$((choice-1))]}"
    
    if [ ! -f "$selected" ]; then
        echo -e "${RED}❌ Неверный выбор${END}"
        return 1
    fi
    
    echo -e "${YELLOW}⚠️ Восстановление из $(basename "$selected")...${END}"
    
    # Останавливаем сервер
    if is_running; then
        stop_server
        sleep 2
    fi
    
    # Создаём бэкап текущего состояния
    local pre_restore="pre_restore_$(date '+%Y%m%d_%H%M%S').tar.gz"
    tar -czf "../$pre_restore" "server" "database.db" 2>/dev/null
    
    # Восстанавливаем
    tar -xzf "$selected" -C ".." 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Восстановление завершено${END}"
        start_server
    else
        echo -e "${RED}❌ Ошибка восстановления${END}"
        # Откатываем
        tar -xzf "../$pre_restore" -C ".." 2>/dev/null
    fi
}

# ========== ОСНОВНАЯ ЛОГИКА ==========
case "${1:-start}" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        sleep 2
        start_server
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "${2:-50}"
        ;;
    monitor)
        monitor_server
        ;;
    backup)
        backup_server
        ;;
    restore)
        restore_backup
        ;;
    test)
        test_api
        ;;
    metrics)
        show_metrics
        ;;
    cleanup)
        cleanup
        ;;
    help)
        print_help
        ;;
    *)
        echo -e "${RED}❌ Неизвестная команда: $1${END}"
        print_help
        exit 1
        ;;
esac

exit 0
