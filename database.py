#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
██████╗  █████╗ ████████╗ █████╗ ██████╗  █████╗ ███████╗███████╗
██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔════╝
██║  ██║███████║   ██║   ███████║██████╔╝███████║███████╗█████╗  
██║  ██║██╔══██║   ██║   ██╔══██║██╔══██╗██╔══██║╚════██║██╔══╝  
██████╔╝██║  ██║   ██║   ██║  ██║██████╔╝██║  ██║███████║███████╗
╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝

MORI DATABASE — МАСШТАБИРУЕМАЯ БД ДЛЯ 10+ ПРИЛОЖЕНИЙ
Версия: 2.0.0
Статус: ГОТОВА К НАГРУЗКАМ
"""

import os
import time
import logging
import json
from datetime import datetime, timedelta
from contextlib import contextmanager
from functools import wraps
from threading import Lock
import sqlite3
import hashlib

from flask import current_app, g
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.orm import scoped_session, sessionmaker, Query
from sqlalchemy.pool import QueuePool, NullPool
from werkzeug.local import LocalProxy

from models import db as sqlalchemy_db

# Настройка логирования
logger = logging.getLogger('mori_database')

# ========== КЛАСС ДЛЯ РАБОТЫ С НЕСКОЛЬКИМИ БАЗАМИ ==========
class MultiTenantDatabase:
    """
    Поддержка нескольких приложений (tenant'ов) в одной БД
    или в отдельных БД — масштабирование на 10+ приложений
    """
    
    def __init__(self):
        self.tenants = {}  # Словарь с подключениями к разным БД
        self.default_tenant = 'main'
        self.tenant_resolver = None  # Функция для определения tenant по запросу
        self.lock = Lock()
        
    def configure(self, tenants_config, default_tenant='main', resolver=None):
        """
        Настройка мультитенантности
        tenants_config: {
            'main': 'sqlite:///database.db',
            'app1': 'sqlite:///app1.db',
            'app2': 'postgresql://user:pass@localhost/app2'
        }
        """
        with self.lock:
            for tenant_name, db_uri in tenants_config.items():
                self.tenants[tenant_name] = {
                    'uri': db_uri,
                    'engine': None,
                    'session_factory': None,
                    'connections': 0,
                    'last_used': None
                }
            
            self.default_tenant = default_tenant
            self.tenant_resolver = resolver
            logger.info(f"✅ Настроено тенантов: {len(self.tenants)}")
    
    def get_engine(self, tenant=None):
        """Получение engine для тенанта"""
        tenant = tenant or self.default_tenant
        
        if tenant not in self.tenants:
            logger.warning(f"Тенант {tenant} не найден, использую default")
            tenant = self.default_tenant
        
        with self.lock:
            tenant_info = self.tenants[tenant]
            
            # Создаём engine если ещё нет
            if tenant_info['engine'] is None:
                # Настройки пула соединений в зависимости от типа БД
                if tenant_info['uri'].startswith('sqlite'):
                    # Для SQLite — особые настройки
                    engine = create_engine(
                        tenant_info['uri'],
                        poolclass=QueuePool,
                        pool_size=20,  # Макс соединений в пуле
                        max_overflow=10,  # Дополнительные при пике
                        pool_timeout=30,  # Таймаут ожидания соединения
                        pool_recycle=3600,  # Пересоздавать соединения каждый час
                        pool_pre_ping=True,  # Проверять соединение перед использованием
                        connect_args={
                            'timeout': 15,
                            'check_same_thread': False,
                            'isolation_level': None
                        }
                    )
                    
                    # Включаем WAL режим для SQLite (повышает производительность)
                    @event.listens_for(engine, 'connect')
                    def set_sqlite_pragma(dbapi_connection, connection_record):
                        cursor = dbapi_connection.cursor()
                        cursor.execute('PRAGMA journal_mode=WAL')
                        cursor.execute('PRAGMA synchronous=NORMAL')
                        cursor.execute('PRAGMA cache_size=10000')
                        cursor.execute('PRAGMA foreign_keys=ON')
                        cursor.execute('PRAGMA temp_store=MEMORY')
                        cursor.close()
                        
                else:
                    # Для PostgreSQL/MySQL — стандартные настройки
                    engine = create_engine(
                        tenant_info['uri'],
                        poolclass=QueuePool,
                        pool_size=50,
                        max_overflow=20,
                        pool_timeout=30,
                        pool_recycle=3600,
                        pool_pre_ping=True,
                        echo=False
                    )
                
                tenant_info['engine'] = engine
                tenant_info['session_factory'] = scoped_session(
                    sessionmaker(bind=engine)
                )
                logger.info(f"🔌 Создан engine для тенанта: {tenant}")
            
            tenant_info['connections'] += 1
            tenant_info['last_used'] = datetime.utcnow()
            
            return tenant_info['engine']
    
    def get_session(self, tenant=None):
        """Получение сессии для тенанта"""
        tenant = tenant or self.default_tenant
        engine = self.get_engine(tenant)
        return self.tenants[tenant]['session_factory']()
    
    def get_tenant_for_request(self):
        """Определение тенанта по текущему запросу"""
        if self.tenant_resolver:
            return self.tenant_resolver()
        
        # По умолчанию — из заголовка X-Tenant-ID
        from flask import request
        return request.headers.get('X-Tenant-ID', self.default_tenant)
    
    def cleanup_idle_connections(self, max_idle_minutes=30):
        """Очистка неактивных соединений"""
        with self.lock:
            now = datetime.utcnow()
            for tenant, info in self.tenants.items():
                if info['engine'] and info['last_used']:
                    idle = (now - info['last_used']).total_seconds() / 60
                    if idle > max_idle_minutes and info['connections'] == 0:
                        info['engine'].dispose()
                        info['engine'] = None
                        info['session_factory'] = None
                        logger.info(f"🧹 Очищены соединения для тенанта: {tenant}")

# ========== КЭШИРОВАНИЕ ЗАПРОСОВ ==========
class QueryCache:
    """Кэш для часто выполняемых запросов"""
    
    def __init__(self, maxsize=1000, ttl=300):
        self.cache = {}
        self.maxsize = maxsize
        self.ttl = ttl  # время жизни в секундах
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'invalidations': 0
        }
        self.lock = Lock()
    
    def get(self, key):
        """Получение из кэша"""
        with self.lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                if time.time() - timestamp < self.ttl:
                    self.stats['hits'] += 1
                    return value
                else:
                    # Просрочено
                    del self.cache[key]
            
            self.stats['misses'] += 1
            return None
    
    def set(self, key, value):
        """Сохранение в кэш"""
        with self.lock:
            # Если кэш переполнен, удаляем самое старое
            if len(self.cache) >= self.maxsize:
                oldest_key = min(self.cache.keys(), 
                                 key=lambda k: self.cache[k][1])
                del self.cache[oldest_key]
            
            self.cache[key] = (value, time.time())
            self.stats['sets'] += 1
    
    def invalidate(self, pattern=None):
        """Инвалидация кэша"""
        with self.lock:
            if pattern:
                # Удаляем по паттерну
                keys_to_delete = [k for k in self.cache if pattern in k]
                for k in keys_to_delete:
                    del self.cache[k]
                self.stats['invalidations'] += len(keys_to_delete)
            else:
                # Полная очистка
                self.cache.clear()
                self.stats['invalidations'] += 1
    
    def get_stats(self):
        """Статистика кэша"""
        return {
            **self.stats,
            'size': len(self.cache),
            'maxsize': self.maxsize,
            'hit_rate': self.stats['hits'] / (self.stats['hits'] + self.stats['misses'] + 1)
        }

# ========== ДЕКОРАТОР ДЛЯ ПОВТОРНЫХ ПОПЫТОК ==========
def retry_on_failure(max_retries=3, delay=0.5, backoff=2, exceptions=(OperationalError,)):
    """
    Декоратор для повторных попыток при ошибках БД
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            
            while retries <= max_retries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"❌ Превышено число попыток ({max_retries}): {e}")
                        raise
                    
                    logger.warning(f"⚠️ Ошибка БД, попытка {retries}/{max_retries}: {e}")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            return None
        return wrapper
    return decorator

# ========== МИГРАЦИИ БАЗЫ ДАННЫХ ==========
class DatabaseMigrator:
    """Система миграций для всех тенантов"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.migrations = []
        self.migration_history = {}
    
    def register_migration(self, version, description, up_func, down_func=None):
        """Регистрация миграции"""
        self.migrations.append({
            'version': version,
            'description': description,
            'up': up_func,
            'down': down_func,
            'timestamp': datetime.utcnow()
        })
        self.migrations.sort(key=lambda x: x['version'])
        logger.info(f"📝 Зарегистрирована миграция v{version}: {description}")
    
    def get_current_version(self, tenant='main'):
        """Текущая версия схемы для тенанта"""
        session = self.db_manager.get_session(tenant)
        try:
            # Создаём таблицу для миграций если нет
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            """))
            session.commit()
            
            result = session.execute(
                text("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1")
            ).fetchone()
            
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Ошибка получения версии: {e}")
            return 0
        finally:
            session.close()
    
    def migrate(self, target_version=None, tenant='main'):
        """Применение миграций до целевой версии"""
        current = self.get_current_version(tenant)
        target = target_version or (self.migrations[-1]['version'] if self.migrations else current)
        
        if current == target:
            logger.info(f"✅ Тенант {tenant} уже на версии {current}")
            return True
        
        session = self.db_manager.get_session(tenant)
        
        try:
            if target > current:
                # Применяем миграции вперёд
                for migration in self.migrations:
                    if migration['version'] > current and migration['version'] <= target:
                        logger.info(f"⬆️ Применяю миграцию v{migration['version']}: {migration['description']}")
                        migration['up'](session)
                        
                        # Записываем в историю
                        session.execute(
                            text("INSERT INTO schema_migrations (version, description) VALUES (:v, :d)"),
                            {'v': migration['version'], 'd': migration['description']}
                        )
                        session.commit()
                        
            elif target < current:
                # Откатываем миграции назад
                for migration in reversed(self.migrations):
                    if migration['version'] <= current and migration['version'] > target:
                        if migration.get('down'):
                            logger.info(f"⬇️ Откатываю миграцию v{migration['version']}")
                            migration['down'](session)
                            
                            # Удаляем из истории
                            session.execute(
                                text("DELETE FROM schema_migrations WHERE version = :v"),
                                {'v': migration['version']}
                            )
                            session.commit()
            
            logger.info(f"✅ Миграция тенанта {tenant} завершена: {current} → {target}")
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Ошибка миграции: {e}")
            return False
        finally:
            session.close()
    
    def migrate_all_tenants(self, target_version=None):
        """Применение миграций ко всем тенантам"""
        results = {}
        for tenant in self.db_manager.tenants:
            results[tenant] = self.migrate(target_version, tenant)
        return results

# ========== МОНИТОРИНГ БАЗЫ ДАННЫХ ==========
class DatabaseMonitor:
    """Мониторинг производительности БД"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.query_stats = {}
        self.slow_queries = []
        self.lock = Lock()
    
    def record_query(self, query, params, duration, tenant):
        """Запись статистики запроса"""
        with self.lock:
            # Общая статистика
            if query not in self.query_stats:
                self.query_stats[query] = {
                    'count': 0,
                    'total_time': 0,
                    'min_time': float('inf'),
                    'max_time': 0
                }
            
            stats = self.query_stats[query]
            stats['count'] += 1
            stats['total_time'] += duration
            stats['min_time'] = min(stats['min_time'], duration)
            stats['max_time'] = max(stats['max_time'], duration)
            
            # Медленные запросы (> 1 секунды)
            if duration > 1.0:
                self.slow_queries.append({
                    'query': query,
                    'params': params,
                    'duration': duration,
                    'tenant': tenant,
                    'timestamp': datetime.utcnow()
                })
                
                # Ограничиваем историю медленных запросов
                if len(self.slow_queries) > 100:
                    self.slow_queries = self.slow_queries[-100:]
    
    def get_stats(self):
        """Получение статистики"""
        return {
            'queries': self.query_stats,
            'slow_queries': self.slow_queries[-10:],  # последние 10
            'total_queries': sum(s['count'] for s in self.query_stats.values()),
            'total_time': sum(s['total_time'] for s in self.query_stats.values())
        }

# ========== ИНИЦИАЛИЗАЦИЯ ==========
db_manager = MultiTenantDatabase()
query_cache = QueryCache(maxsize=1000, ttl=300)
db_monitor = None
migrator = None

def init_database(app):
    """Инициализация базы данных с поддержкой мультитенантности"""
    global db_monitor, migrator
    
    # Конфигурация тенантов
    tenants = {
        'main': app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///database.db'),
    }
    
    # Добавляем дополнительные тенанты из конфига
    extra_tenants = app.config.get('EXTRA_TENANTS', {})
    tenants.update(extra_tenants)
    
    # Настраиваем мультитенантность
    db_manager.configure(tenants, default_tenant='main')
    
    # Создаём монитор
    db_monitor = DatabaseMonitor(db_manager)
    
    # Создаём мигратор
    migrator = DatabaseMigrator(db_manager)
    
    # Инициализируем основную БД
    with app.app_context():
        main_engine = db_manager.get_engine('main')
        sqlalchemy_db.metadata.create_all(main_engine)
        
        # Регистрируем слушатель для мониторинга запросов
        @event.listens_for(main_engine, 'before_cursor_execute')
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            conn.info.setdefault('query_start_time', []).append(time.time())
        
        @event.listens_for(main_engine, 'after_cursor_execute')
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            total = time.time() - conn.info['query_start_time'].pop()
            db_monitor.record_query(statement, parameters, total, 'main')
    
    logger.info("✅ Мультитенантная БД инициализирована")
    logger.info(f"📊 Тенантов: {len(tenants)}")
    
    return db_manager

# ========== ХЕЛПЕРЫ ДЛЯ РАБОТЫ С БД ==========
@contextmanager
def session_scope(tenant=None):
    """Контекстный менеджер для работы с сессией"""
    session = db_manager.get_session(tenant)
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка в транзакции: {e}")
        raise
    finally:
        session.close()

def get_db():
    """Получение текущей сессии (для совместимости)"""
    tenant = db_manager.get_tenant_for_request()
    return db_manager.get_session(tenant)

def cached_query(key_prefix, ttl=300):
    """Декоратор для кэширования результатов запроса"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Формируем ключ кэша
            cache_key = f"{key_prefix}:{hashlib.md5(str((args, kwargs)).encode()).hexdigest()}"
            
            # Пробуем получить из кэша
            cached = query_cache.get(cache_key)
            if cached is not None:
                return cached
            
            # Выполняем запрос
            result = func(*args, **kwargs)
            
            # Сохраняем в кэш
            query_cache.set(cache_key, result)
            
            return result
        return wrapper
    return decorator

# ========== ФУНКЦИИ ДЛЯ ТЕСТИРОВАНИЯ ==========
def get_database_stats():
    """Статистика использования БД"""
    stats = {
        'tenants': {},
        'cache': query_cache.get_stats() if query_cache else None,
        'monitor': db_monitor.get_stats() if db_monitor else None
    }
    
    for tenant, info in db_manager.tenants.items():
        stats['tenants'][tenant] = {
            'uri': info['uri'],
            'connections': info['connections'],
            'engine_active': info['engine'] is not None
        }
    
    return stats

def check_database_health():
    """Проверка здоровья всех БД"""
    results = {}
    
    for tenant in db_manager.tenants:
        try:
            session = db_manager.get_session(tenant)
            session.execute(text('SELECT 1'))
            session.close()
            results[tenant] = {'status': 'healthy', 'error': None}
        except Exception as e:
            results[tenant] = {'status': 'unhealthy', 'error': str(e)}
    
    return results

def cleanup_idle_connections():
    """Очистка неактивных соединений"""
    db_manager.cleanup_idle_connections()
    logger.info("🧹 Очистка неактивных соединений выполнена")

# ========== ЭКСПОРТ ==========
__all__ = [
    'db_manager',
    'query_cache',
    'init_database',
    'session_scope',
    'get_db',
    'cached_query',
    'retry_on_failure',
    'get_database_stats',
    'check_database_health',
    'cleanup_idle_connections',
    'MultiTenantDatabase',
    'DatabaseMigrator',
    'DatabaseMonitor'
]
