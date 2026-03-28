#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
███╗   ███╗ ██████╗ ██████╗ ██╗
████╗ ████║██╔═══██╗██╔══██╗██║
██╔████╔██║██║   ██║██████╔╝██║
██║╚██╔╝██║██║   ██║██╔══██╗██║
██║ ╚═╝ ██║╚██████╔╝██║  ██║██║
╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝

MORI ORACLE SERVER —ULTIMATE EDITION
Версия: 2.0.0
Статус: АБСОЛЮТНО РАЗРЫВНОЙ
Поддержка: 10+ приложений, 1000+ пользователей
"""

import os
import sys
import logging
import time
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, jsonify, request, g
from flask_cors import CORS
from flask_jwt_extended import JWTManager, verify_jwt_in_request, get_jwt
from werkzeug.exceptions import HTTPException

# Импортируем конфиг
from config import Config

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
class CustomFormatter(logging.Formatter):
    """Кастомный форматтер для цветного логирования"""
    
    grey = "\x1b[38;21m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[38;5;226m"
    red = "\x1b[38;5;196m"
    bold_red = "\x1b[31;1m"
    green = "\x1b[38;5;40m"
    cyan = "\x1b[38;5;51m"
    magenta = "\x1b[38;5;201m"
    reset = "\x1b[0m"

    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: green + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

# Создаём директорию для логов если нет
os.makedirs('logs', exist_ok=True)

# Настройка корневого логгера
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Консольный handler с цветами
console_handler = logging.StreamHandler()
console_handler.setFormatter(CustomFormatter())
logger.addHandler(console_handler)

# Файловый handler для постоянного логирования
file_handler = logging.FileHandler(f'logs/mori_server_{datetime.now().strftime("%Y%m%d")}.log')
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger.addHandler(file_handler)

# Отдельный логгер для приложения
app_logger = logging.getLogger('mori_server')
app_logger.setLevel(logging.INFO)

# ========== СОЗДАНИЕ FLASK ПРИЛОЖЕНИЯ ==========
app = Flask(__name__)
app.config.from_object(Config)

# ========== РАСШИРЕННЫЙ CORS ==========
CORS(app, 
     origins=Config.ALLOWED_ORIGINS,
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization', 'X-Requested-With'],
     expose_headers=['Content-Type', 'Authorization'],
     supports_credentials=True,
     max_age=86400)  # Кэшировать preflight на 24 часа

# ========== JWT НАСТРОЙКИ ==========
jwt = JWTManager(app)

# Добавляем дополнительные claims в токен
@jwt.additional_claims_loader
def add_claims_to_access_token(identity):
    user = User.query.get(identity) if 'User' in globals() else None
    return {
        'access_level': user.access_level if user else 'guest',
        'iat': datetime.utcnow().timestamp()
    }

# Обработчики ошибок JWT
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({
        'error': 'Токен истёк',
        'code': 'token_expired'
    }), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({
        'error': 'Невалидный токен',
        'code': 'invalid_token'
    }), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({
        'error': 'Требуется авторизация',
        'code': 'authorization_required'
    }), 401

# ========== МИДЛВАРЫ (ПРОМЕЖУТОЧНЫЕ СЛОИ) ==========
@app.before_request
def before_request():
    """Действия перед каждым запросом"""
    g.start_time = time.time()
    g.request_id = os.urandom(8).hex()
    
    # Логируем входящий запрос
    app_logger.info(f"📥 [{g.request_id}] {request.method} {request.path} | IP: {request.remote_addr}")

@app.after_request
def after_request(response):
    """Действия после каждого запроса"""
    # Добавляем security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Request-ID'] = g.get('request_id', '')
    
    if hasattr(g, 'start_time') and isinstance(g.start_time, (int, float)):
       elapsed = time.time() - g.start_time
       response.headers['X-Response-Time'] = str(round(elapsed * 1000, 2))
       app_logger.info(f"📤 [{g.request_id}] {response.status_code} | {round(elapsed*1000,2)}ms")
    else:
       app_logger.info(f"📤 [{g.request_id}] {response.status_code}")
    
    return response

@app.teardown_appcontext
def teardown_db(error):
    """Закрываем соединения с БД после запроса"""
    from models import db
    db.session.remove()

# ========== ОБРАБОТЧИКИ ОШИБОК ==========
@app.errorhandler(400)
def bad_request(error):
    return jsonify({
        'error': 'Неверный запрос',
        'message': str(error.description if hasattr(error, 'description') else 'Проверьте введённые данные'),
        'code': 'bad_request'
    }), 400

@app.errorhandler(401)
def unauthorized(error):
    return jsonify({
        'error': 'Не авторизован',
        'message': 'Требуется авторизация',
        'code': 'unauthorized'
    }), 401

@app.errorhandler(403)
def forbidden(error):
    return jsonify({
        'error': 'Доступ запрещён',
        'message': 'Недостаточно прав',
        'code': 'forbidden'
    }), 403

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Не найдено',
        'message': 'Запрашиваемый ресурс не существует',
        'code': 'not_found',
        'path': request.path
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'error': 'Метод не разрешён',
        'message': f'Метод {request.method} не поддерживается для {request.path}',
        'code': 'method_not_allowed'
    }), 405

@app.errorhandler(429)
def rate_limit_exceeded(error):
    return jsonify({
        'error': 'Слишком много запросов',
        'message': 'Превышен лимит запросов. Попробуйте позже',
        'code': 'rate_limit_exceeded'
    }), 429

@app.errorhandler(500)
def internal_error(error):
    app_logger.error(f"💥 Внутренняя ошибка сервера: {str(error)}")
    return jsonify({
        'error': 'Внутренняя ошибка сервера',
        'message': 'Что-то пошло не так. Мы уже работаем над этим',
        'code': 'internal_error'
    }), 500

@app.errorhandler(HTTPException)
def handle_http_exception(error):
    """Обработка всех HTTP исключений"""
    response = jsonify({
        'error': error.name,
        'message': error.description,
        'code': f'http_{error.code}'
    })
    response.status_code = error.code
    return response

@app.errorhandler(Exception)
def handle_unhandled_exception(error):
    """Обработка всех необработанных исключений"""
    app_logger.error(f"💥 Необработанное исключение: {str(error)}", exc_info=True)
    return jsonify({
        'error': 'Внутренняя ошибка сервера',
        'message': 'Произошла непредвиденная ошибка',
        'code': 'unhandled_error'
    }), 500

# ========== МЕТРИКИ И МОНИТОРИНГ ==========
@app.route('/metrics', methods=['GET'])
def metrics():
    """Endpoint для метрик (для Prometheus/Grafana)"""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    
    metrics_data = {
        'system': {
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent
        },
        'process': {
            'cpu_percent': process.cpu_percent(interval=0.1),
            'memory_rss': process.memory_info().rss,
            'memory_vms': process.memory_info().vms,
            'connections': len(process.connections()),
            'threads': process.num_threads()
        },
        'app': {
            'uptime': time.time() - app.start_time if hasattr(app, 'start_time') else 0,
            'requests_count': getattr(g, 'requests_count', 0)
        }
    }
    
    return jsonify(metrics_data)

@app.route('/health', methods=['GET'])
def health():
    """Улучшенный health check"""
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '2.0.0',
        'services': {
            'database': 'checking',
            'redis': 'disabled'
        }
    }
    
    # Проверяем БД если уже инициализирована
    if 'db' in globals():
        try:
            db.session.execute('SELECT 1')
            health_status['services']['database'] = 'healthy'
        except Exception as e:
            health_status['services']['database'] = 'unhealthy'
            health_status['status'] = 'degraded'
            app_logger.error(f"Database health check failed: {e}")
    
    return jsonify(health_status), 200 if health_status['status'] == 'healthy' else 503

@app.route('/info', methods=['GET'])
def info():
    """Информация о сервере"""
    return jsonify({
        'name': 'MORI Oracle Server',
        'version': '2.0.0',
        'environment': 'development' if Config.DEBUG else 'production',
        'features': [
            'JWT Authentication',
            'Multi-level access (user/family/admin)',
            'RESTful API',
            'CORS enabled',
            'Request logging',
            'Metrics endpoint'
        ],
        'modules': [
            'auth', 'portfolio', 'library', 'chat', 
            'family', 'profile', 'admin'
        ],
        'endpoints_count': 0  # будет обновлено при регистрации роутов
    })

# ========== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ==========
def init_database():
    """Инициализация БД с проверкой"""
    try:
        from models import db
        db.init_app(app)
        
        with app.app_context():
            db.create_all()
            app_logger.info("✅ База данных инициализирована")
            
            # Создаём тестовые данные если нужно
            if Config.DEBUG:
                create_test_data()
                
    except Exception as e:
        app_logger.error(f"❌ Ошибка инициализации БД: {e}")
        raise

def create_test_data():
    """Создание тестовых данных для разработки"""
    from models import User, Book, db
    
    # Проверяем, есть ли уже пользователи
    if User.query.count() == 0:
        # Создаём админа
        admin = User(
            nickname='Админ',
            avatar='👑',
            access_level='admin',
            balance=1000000
        )
        db.session.add(admin)
        
        # Создаём семью
        family = User(
            nickname='Семья',
            avatar='👨‍👩‍👧‍👦',
            access_level='family',
            balance=50000
        )
        db.session.add(family)
        
        # Создаём обычного пользователя
        user = User(
            nickname='Пользователь',
            avatar='👤',
            access_level='user',
            balance=1000
        )
        db.session.add(user)
        
        db.session.commit()
        app_logger.info("✅ Тестовые пользователи созданы")

# ========== РЕГИСТРАЦИЯ РОУТОВ ==========
def register_blueprints():
    """Регистрация всех роутов"""
    from routes import register_all_routes
    register_all_routes(app)
    
    # Подсчитываем количество эндпоинтов
    endpoints = [rule.endpoint for rule in app.url_map.iter_rules()]
    app_logger.info(f"📋 Зарегистрировано эндпоинтов: {len(endpoints)}")

# ========== ЗАПУСК СЕРВЕРА ==========
if __name__ == '__main__':
    try:
        app_logger.info("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   ███╗   ███╗ ██████╗ ██████╗ ██╗                       ║
║   ████╗ ████║██╔═══██╗██╔══██╗██║                       ║
║   ██╔████╔██║██║   ██║██████╔╝██║                       ║
║   ██║╚██╔╝██║██║   ██║██╔══██╗██║                       ║
║   ██║ ╚═╝ ██║╚██████╔╝██║  ██║██║                       ║
║   ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝                       ║
║                                                          ║
║   🔥 MORI ORACLE SERVER v2.0.0                          ║
║   💪 РАЗРЫВНОЙ РЕЖИМ АКТИВИРОВАН                        ║
║   🚀 Поддержка 10+ приложений                            ║
╚══════════════════════════════════════════════════════════╝
        """)
        
        # Запоминаем время старта
        app.start_time = time.time()
        
        # Инициализируем БД
        init_database()
        
        # Регистрируем роуты
        register_blueprints()
        
        # Выводим информацию о запуске
        app_logger.info(f"🌐 Сервер запущен на {Config.HOST}:{Config.PORT}")
        app_logger.info(f"🐍 Debug mode: {Config.DEBUG}")
        app_logger.info("⚡ Ожидание подключений...")
        
        # Запускаем сервер
        app.run(
            host=Config.HOST,
            port=Config.PORT,
            debug=Config.DEBUG,
            threaded=True,  # Включаем многопоточность
            use_reloader=Config.DEBUG  # Автоперезагрузка в debug
        )
        
    except KeyboardInterrupt:
        app_logger.info("👋 Сервер остановлен пользователем")
    except Exception as e:
        app_logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
    finally:
        app_logger.info("🏁 Сервер завершил работу")

# ===== СЖАТИЕ ТРАФИКА (добавлено MEGA-START) =====
from flask import after_this_request, request
import gzip
import io

@app.after_request
def compress_response(response):
    accept_encoding = request.headers.get('Accept-Encoding', '')
    if 'gzip' in accept_encoding and response.content_length and response.content_length > 200:
        response.direct_passthrough = False
        
        gzip_buffer = io.BytesIO()
        with gzip.GzipFile(mode='wb', fileobj=gzip_buffer) as gzip_file:
            gzip_file.write(response.get_data())
        
        response.set_data(gzip_buffer.getvalue())
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Content-Length'] = len(response.get_data())
    
    return response
