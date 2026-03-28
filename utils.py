#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
UTILS — ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ МАСШТАБИРОВАНИЯ
"""

import re
import json
import time
import uuid
import socket
import hashlib
import logging
from datetime import datetime, timedelta
from functools import wraps
import psutil

logger = logging.getLogger('mori_utils')

# ========== ВАЛИДАЦИЯ ==========
def validate_email(email):
    """Проверка email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Проверка телефона"""
    pattern = r'^\+?[0-9]{10,15}$'
    return re.match(pattern, phone) is not None

def validate_password(password):
    """Проверка сложности пароля"""
    if len(password) < 8:
        return False, "Пароль должен быть минимум 8 символов"
    if not re.search(r'[A-Z]', password):
        return False, "Пароль должен содержать заглавную букву"
    if not re.search(r'[a-z]', password):
        return False, "Пароль должен содержать строчную букву"
    if not re.search(r'[0-9]', password):
        return False, "Пароль должен содержать цифру"
    return True, "OK"

def sanitize_input(text):
    """Очистка ввода от XSS"""
    if not text:
        return text
    # Заменяем опасные символы
    replacements = {
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
        '&': '&amp;',
        '(': '&#40;',
        ')': '&#41;',
        '/': '&#47;',
        '\\': '&#92;'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

# ========== ГЕНЕРАЦИЯ ==========
def generate_id(prefix=''):
    """Генерация уникального ID"""
    unique = f"{time.time_ns()}{uuid.uuid4().int}{socket.gethostname()}"
    hash_id = hashlib.md5(unique.encode()).hexdigest()[:16]
    return f"{prefix}_{hash_id}" if prefix else hash_id

def generate_token(length=32):
    """Генерация случайного токена"""
    return hashlib.sha256(os.urandom(32)).hexdigest()[:length]

def generate_short_code(length=6):
    """Генерация короткого кода (для инвайтов)"""
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789'
    return ''.join(chars[hashlib.md5(os.urandom(1)).digest()[0] % len(chars)] 
                  for _ in range(length))

# ========== ФОРМАТИРОВАНИЕ ==========
def format_size(bytes):
    """Форматирование размера файла"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024
    return f"{bytes:.1f} PB"

def format_duration(seconds):
    """Форматирование длительности"""
    if seconds < 60:
        return f"{seconds:.0f} сек"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes:.0f} мин {seconds % 60:.0f} сек"
    hours = minutes // 60
    if hours < 24:
        return f"{hours:.0f} ч {minutes % 60:.0f} мин"
    days = hours // 24
    return f"{days:.0f} д {hours % 24:.0f} ч"

def format_number(num):
    """Форматирование больших чисел"""
    if num < 1000:
        return str(num)
    if num < 1000000:
        return f"{num/1000:.1f}K"
    if num < 1000000000:
        return f"{num/1000000:.1f}M"
    return f"{num/1000000000:.1f}B"

# ========== ДАТЫ ==========
def time_ago(timestamp):
    """Форматирование времени в формате '5 минут назад'"""
    if not timestamp:
        return ''
    
    diff = datetime.utcnow() - timestamp
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return f"{int(seconds)} сек назад"
    if seconds < 3600:
        return f"{int(seconds // 60)} мин назад"
    if seconds < 86400:
        return f"{int(seconds // 3600)} ч назад"
    if seconds < 2592000:
        return f"{int(seconds // 86400)} дн назад"
    if seconds < 31536000:
        return f"{int(seconds // 2592000)} мес назад"
    return f"{int(seconds // 31536000)} г назад"

def is_today(date):
    """Проверка, сегодня ли дата"""
    if not date:
        return False
    today = datetime.utcnow().date()
    return date.date() == today

def is_this_week(date):
    """Проверка, на этой ли неделе"""
    if not date:
        return False
    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start <= date.date() <= week_end

# ========== СИСТЕМНЫЕ ==========
def get_system_stats():
    """Системная статистика"""
    return {
        'cpu': psutil.cpu_percent(interval=1),
        'memory': psutil.virtual_memory().percent,
        'disk': psutil.disk_usage('/').percent,
        'processes': len(psutil.pids()),
        'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat()
    }

def get_network_stats():
    """Сетевая статистика"""
    net_io = psutil.net_io_counters()
    return {
        'bytes_sent': format_size(net_io.bytes_sent),
        'bytes_recv': format_size(net_io.bytes_recv),
        'packets_sent': net_io.packets_sent,
        'packets_recv': net_io.packets_recv,
        'errin': net_io.errin,
        'errout': net_io.errout,
        'dropin': net_io.dropin,
        'dropout': net_io.dropout
    }

# ========== ДЕКОРАТОРЫ ==========
def retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
    """Декоратор для повторных попыток"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        raise
                    logger.warning(f"Попытка {attempt + 1} не удалась: {e}")
                    time.sleep(current_delay)
                    current_delay *= backoff
            return None
        return wrapper
    return decorator

def measure_time(func):
    """Декоратор для замера времени выполнения"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        logger.debug(f"{func.__name__} выполнен за {elapsed*1000:.2f}ms")
        return result
    return wrapper

# ========== ЭКСПОРТ ==========
__all__ = [
    'validate_email',
    'validate_phone', 
    'validate_password',
    'sanitize_input',
    'generate_id',
    'generate_token',
    'generate_short_code',
    'format_size',
    'format_duration',
    'format_number',
    'time_ago',
    'is_today',
    'is_this_week',
    'get_system_stats',
    'get_network_stats',
    'retry',
    'measure_time'
]
