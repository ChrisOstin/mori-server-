#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MIDDLEWARE — ПРОМЕЖУТОЧНЫЕ СЛОИ ДЛЯ 10+ ПРИЛОЖЕНИЙ
"""

import time
import logging
from functools import wraps
from flask import request, g, jsonify
from werkzeug.middleware.profiler import Profiler
import hashlib
import hmac

logger = logging.getLogger('mori_middleware')

# ========== RATE LIMITING (ДЛЯ ЗАЩИТЫ) ==========
class RateLimiter:
    """Ограничение запросов от одного клиента"""
    
    def __init__(self, requests_per_minute=60, requests_per_hour=1000):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.minute_limits = {}
        self.hour_limits = {}
        self.blocked_ips = set()
        self.blocked_tokens = set()
    
    def is_allowed(self, key):
        """Проверка лимита для ключа (IP или токен)"""
        now = time.time()
        
        # Минутный лимит
        minute_key = f"minute_{key}"
        if minute_key not in self.minute_limits:
            self.minute_limits[minute_key] = []
        
        # Очищаем старые записи (> 1 минуты)
        self.minute_limits[minute_key] = [
            t for t in self.minute_limits[minute_key] 
            if now - t < 60
        ]
        
        # Проверяем минутный лимит
        if len(self.minute_limits[minute_key]) >= self.requests_per_minute:
            return False
        
        # Часовой лимит
        hour_key = f"hour_{key}"
        if hour_key not in self.hour_limits:
            self.hour_limits[hour_key] = []
        
        # Очищаем старые записи (> 1 часа)
        self.hour_limits[hour_key] = [
            t for t in self.hour_limits[hour_key] 
            if now - t < 3600
        ]
        
        # Проверяем часовой лимит
        if len(self.hour_limits[hour_key]) >= self.requests_per_hour:
            return False
        
        # Добавляем текущий запрос
        self.minute_limits[minute_key].append(now)
        self.hour_limits[hour_key].append(now)
        
        return True
    
    def block_ip(self, ip):
        """Блокировка IP"""
        self.blocked_ips.add(ip)
        logger.warning(f"🚫 IP заблокирован: {ip}")
    
    def block_token(self, token):
        """Блокировка токена"""
        self.blocked_tokens.add(token)
        logger.warning(f"🚫 Токен заблокирован")
    
    def cleanup(self):
        """Очистка устаревших блокировок"""
        now = time.time()
        self.minute_limits = {
            k: v for k, v in self.minute_limits.items()
            if v and now - v[-1] < 3600
        }
        self.hour_limits = {
            k: v for k, v in self.hour_limits.items()
            if v and now - v[-1] < 3600
        }

rate_limiter = RateLimiter()

# ========== CSRF ЗАЩИТА ==========
def generate_csrf_token():
    """Генерация CSRF токена"""
    if 'csrf_token' not in g:
        g.csrf_token = hashlib.sha256(
            f"{request.remote_addr}{request.user_agent}{time.time()}".encode()
        ).hexdigest()
    return g.csrf_token

def validate_csrf_token(token):
    """Проверка CSRF токена"""
    if not token:
        return False
    # Простая проверка длины и формата
    return len(token) == 64 and all(c in '0123456789abcdef' for c in token)

# ========== МИДЛВАРЫ ==========

def setup_middleware(app):
    
    @app.before_request
    def before_request_middleware():
        """Перед каждым запросом"""
        g.start_time = time.time()
        g.request_id = hashlib.md5(f"{time.time()}{request.remote_addr}".encode()).hexdigest()[:8]
        
        # Получаем реальный IP
        g.client_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        
        # Проверяем блокировку IP
        if g.client_ip in rate_limiter.blocked_ips:
            logger.warning(f"🚫 Заблокированный IP пытается подключиться: {g.client_ip}")
            return jsonify({"error": "IP заблокирован"}), 403
        
        # Проверяем rate limit
        if not rate_limiter.is_allowed(g.client_ip):
            logger.warning(f"⚠️ Rate limit превышен для IP: {g.client_ip}")
            return jsonify({"error": "Слишком много запросов"}), 429
        
        # Для не-GET запросов проверяем CSRF
        if request.method not in ['GET', 'HEAD', 'OPTIONS']:
            csrf_token = request.headers.get('X-CSRF-Token')
            if not validate_csrf_token(csrf_token):
                logger.warning(f"⚠️ Неверный CSRF токен от {g.client_ip}")
                return jsonify({"error": "Неверный CSRF токен"}), 403
        
        # Логируем запрос
        logger.info(f"📥 [{g.request_id}] {request.method} {request.path} | IP: {g.client_ip}")
        
        # Добавляем заголовки безопасности
        g.security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
            'Content-Security-Policy': "default-src 'self'",
            'X-Request-ID': g.request_id
        }
    
    @app.after_request
    def after_request_middleware(response):
        """После каждого запроса"""
        # Добавляем заголовки безопасности
        if hasattr(g, 'security_headers'):
            for key, value in g.security_headers.items():
                response.headers[key] = value
        
        # Добавляем CSRF токен для GET запросов
        if request.method == 'GET':
            response.headers['X-CSRF-Token'] = generate_csrf_token()
        
        # Считаем время выполнения
        if hasattr(g, 'start_time'):
            elapsed = (time.time() - g.start_time) * 1000  # в миллисекундах
            response.headers['X-Response-Time'] = f"{elapsed:.2f}ms"
            
            # Логируем медленные запросы
            if elapsed > 1000:  # > 1 секунды
                logger.warning(f"🐌 Медленный запрос [{g.request_id}]: {elapsed:.2f}ms")
            
            logger.info(f"📤 [{g.request_id}] {response.status_code} | {elapsed:.2f}ms")
        
        return response
    
    @app.errorhandler(429)
    def rate_limit_handler(error):
        """Обработка превышения лимитов"""
        logger.warning(f"⚠️ Rate limit достигнут для {g.get('client_ip', 'unknown')}")
        return jsonify({
            "error": "Слишком много запросов",
            "message": "Попробуйте позже",
            "retry_after": 60
        }), 429
    
    @app.route('/api/security/block', methods=['POST'])
    def block_ip():
        """Блокировка IP (только для админов)"""
        from auth import requires_access_level
        data = request.get_json()
        ip = data.get('ip')
        if ip:
            rate_limiter.block_ip(ip)
            logger.info(f"🔨 IP заблокирован администратором: {ip}")
            return jsonify({"success": True}), 200
        return jsonify({"error": "IP не указан"}), 400
