#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MORI AUTH — СИСТЕМА АВТОРИЗАЦИИ
Поддерживает 10+ приложений, тысячи пользователей
Версия: 1.0.0
"""

from flask import request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import hmac
import logging

from models import db, User
from config import Config

logger = logging.getLogger(__name__)

# ========== ДЕКОРАТОРЫ ДЛЯ ПРОВЕРКИ ПРАВ ==========
def requires_access_level(level):
    """Декоратор для проверки уровня доступа"""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            
            if not user or user.is_deleted or user.is_blocked:
                return jsonify({"error": "Пользователь не найден или заблокирован"}), 403
            
            # Проверяем уровень доступа
            if level == "admin" and user.access_level != "admin":
                return jsonify({"error": "Требуются права администратора"}), 403
            elif level == "family" and user.access_level not in ["family", "admin"]:
                return jsonify({"error": "Требуются права семьи"}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_client_ip():
    """Получение реального IP клиента (с учётом прокси)"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    return request.remote_addr

def generate_device_fingerprint():
    """Генерация отпечатка устройства для защиты"""
    data = f"{request.user_agent.string}{get_client_ip()}{request.headers.get('Accept-Language', '')}"
    return hashlib.sha256(data.encode()).hexdigest()

# ========== ЭНДПОИНТЫ АВТОРИЗАЦИИ ==========

def register_auth_routes(app):
    
    @app.route('/api/auth/login', methods=['POST'])
    def login():
        """Вход по паролю (MORI / MORIFAMILY / MORIADMIN)"""
        try:
            data = request.get_json()
            if not data or 'password' not in data:
                return jsonify({"error": "Требуется пароль"}), 400
            
            password = data['password']
            device_fingerprint = generate_device_fingerprint()
            
            # Определяем уровень доступа по паролю
            access_level = Config.PASSWORDS.get(password)
            if not access_level:
                logger.warning(f"Неудачная попытка входа с IP {get_client_ip()}")
                return jsonify({"error": "Неверный пароль"}), 401
            
            # Ищем пользователя с таким уровнем доступа
            user = User.query.filter_by(access_level=access_level, is_deleted=False).first()
            
            # Если пользователь не найден, создаём нового
            if not user:
                nickname = {
                    "admin": "Админ",
                    "family": "Семья",
                    "user": "Пользователь"
                }.get(access_level, "Пользователь")
                
                user = User(
                    nickname=nickname,
                    access_level=access_level,
                    balance=1000,
                    avatar="👤",
                    created_at=datetime.utcnow()
                )
                db.session.add(user)
                db.session.commit()
                logger.info(f"Создан новый пользователь: {nickname} (уровень {access_level})")
            
            # Обновляем last_seen
            user.last_seen = datetime.utcnow()
            db.session.commit()
            
            # Создаём токены
            access_token = create_access_token(
                identity=str(user.id),
                additional_claims={
                    "access_level": user.access_level,
                    "device": device_fingerprint
                }
            )
            refresh_token = create_refresh_token(identity=user.id)
            
            logger.info(f"Успешный вход: {user.nickname} (ID: {user.id}, уровень: {user.access_level})")
            
            return jsonify({
                "success": True,
                "token": access_token,
                "refresh_token": refresh_token,
                "user": user.to_dict()
            }), 200
            
        except Exception as e:
            logger.error(f"Ошибка при входе: {str(e)}")
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500
    # Алиас для совместимости с Mini App (без /api)
    @app.route('/auth/login', methods=['POST'])
    def login_alias():
        return login()


    @app.route('/api/auth/register', methods=['POST'])
    def register():
        """Регистрация нового пользователя"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "Нет данных"}), 400
            
            # Проверяем обязательные поля
            if not data.get('nickname') or len(data['nickname'].strip()) < 3:
                return jsonify({"error": "Никнейм должен быть минимум 3 символа"}), 400
            
            nickname = data['nickname'].strip()
            avatar = data.get('avatar', '👤')
            balance = float(data.get('balance', 0))
            access_level = data.get('accessLevel', 'user')
            
            # Проверяем уникальность никнейма
            if User.query.filter_by(nickname=nickname, is_deleted=False).first():
                return jsonify({"error": "Пользователь с таким именем уже существует"}), 409
            
            # Создаём пользователя
            user = User(
                nickname=nickname,
                avatar=avatar,
                balance=balance,
                access_level=access_level,
                created_at=datetime.utcnow()
            )
            
            db.session.add(user)
            db.session.commit()
            
            # Создаём токен
            access_token = create_access_token(
                identity=str(user.id),
                additional_claims={"access_level": user.access_level}
            )
            
            logger.info(f"Зарегистрирован новый пользователь: {nickname} (ID: {user.id})")
            
            return jsonify({
                "success": True,
                "token": access_token,
                "user": user.to_dict()
            }), 201
            
        except Exception as e:
            logger.error(f"Ошибка при регистрации: {str(e)}")
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500
    
    @app.route('/api/auth/verify', methods=['POST'])
    @jwt_required()
    def verify_token():
        """Проверка валидности токена"""
        try:
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            
            if not user or user.is_deleted or user.is_blocked:
                return jsonify({"valid": False}), 401
            
            # Проверяем устройство (опционально)
            device_fingerprint = generate_device_fingerprint()
            # Можно добавить проверку device_fingerprint с тем, что в токене
            
            user.last_seen = datetime.utcnow()
            db.session.commit()
            
            return jsonify({
                "valid": True,
                "user": user.to_dict()
            }), 200
            
        except Exception as e:
            logger.error(f"Ошибка при проверке токена: {str(e)}")
            return jsonify({"valid": False}), 401
    
    @app.route('/api/auth/refresh', methods=['POST'])
    @jwt_required(refresh=True)
    def refresh_token():
        """Обновление access токена"""
        try:
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            
            if not user or user.is_deleted or user.is_blocked:
                return jsonify({"error": "Пользователь не найден"}), 401
            
            new_token = create_access_token(
                identity=str(user.id),
                additional_claims={"access_level": user.access_level}
            )
            
            return jsonify({"token": new_token}), 200
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении токена: {str(e)}")
            return jsonify({"error": "Не удалось обновить токен"}), 500
    
    @app.route('/api/auth/logout', methods=['POST'])
    @jwt_required()
    def logout():
        """Выход из системы"""
        try:
            user_id = get_jwt_identity()
            logger.info(f"Пользователь {user_id} вышел")
            
            # Здесь можно добавить инвалидацию токена в чёрный список
            # (если используете Redis или БД для черного списка)
            
            return jsonify({"success": True}), 200
            
        except Exception as e:
            logger.error(f"Ошибка при выходе: {str(e)}")
            return jsonify({"error": "Внутренняя ошибка"}), 500
    
    @app.route('/api/auth/me', methods=['GET'])
    @jwt_required()
    def get_current_user():
        """Получение данных текущего пользователя"""
        try:
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            
            if not user or user.is_deleted:
                return jsonify({"error": "Пользователь не найден"}), 404
            
            return jsonify(user.to_dict()), 200
            
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {str(e)}")
            return jsonify({"error": "Внутренняя ошибка"}), 500
    
    @app.route('/api/auth/users/<int:user_id>', methods=['GET'])
    @jwt_required()
    def get_user(user_id):
        """Получение данных другого пользователя"""
        try:
            current_user_id = get_jwt_identity()
            current_user = User.query.get(current_user_id)
            
            # Проверяем права (только админ или family может смотреть других)
            if current_user.access_level not in ['admin', 'family'] and current_user_id != user_id:
                return jsonify({"error": "Недостаточно прав"}), 403
            
            user = User.query.get(user_id)
            if not user or user.is_deleted:
                return jsonify({"error": "Пользователь не найден"}), 404
            
            return jsonify(user.to_dict()), 200
            
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {str(e)}")
            return jsonify({"error": "Внутренняя ошибка"}), 500
    
    @app.route('/api/auth/users/<int:user_id>', methods=['PUT'])
    @jwt_required()
    def update_user(user_id):
        """Обновление данных пользователя"""
        try:
            current_user_id = get_jwt_identity()
            current_user = User.query.get(current_user_id)
            data = request.get_json()
            
            # Проверяем права
            if current_user_id != user_id and current_user.access_level != 'admin':
                return jsonify({"error": "Недостаточно прав"}), 403
            
            user = User.query.get(user_id)
            if not user or user.is_deleted:
                return jsonify({"error": "Пользователь не найден"}), 404
            
            # Обновляем поля (только разрешённые)
            allowed_fields = ['nickname', 'avatar', 'balance']
            if current_user.access_level == 'admin':
                allowed_fields.extend(['access_level', 'is_blocked'])
            
            for field in allowed_fields:
                if field in data:
                    setattr(user, field, data[field])
            
            # Обновляем настройки
            if 'settings' in data:
                settings = data['settings']
                settings_fields = ['notifications', 'theme', 'sound', 'vibration', 
                                  'privacy_online', 'privacy_balance']
                for field in settings_fields:
                    if field in settings:
                        setattr(user, field, settings[field])
            
            # Обновляем статистику
            if 'stats' in data:
                stats = data['stats']
                stats_fields = ['messages_count', 'pages_read', 'calculations', 'ai_questions']
                for field in stats_fields:
                    if field in stats:
                        setattr(user, field, stats[field])
            
            db.session.commit()
            logger.info(f"Обновлён пользователь {user_id}")
            
            return jsonify({
                "success": True,
                "user": user.to_dict()
            }), 200
            
        except Exception as e:
            logger.error(f"Ошибка обновления пользователя: {str(e)}")
            return jsonify({"error": "Внутренняя ошибка"}), 500
    
    @app.route('/api/auth/users', methods=['GET'])
    @requires_access_level('family')
    def get_users():
        """Получение списка пользователей (только для семьи и админов)"""
        try:
            users = User.query.filter_by(is_deleted=False).order_by(User.level.desc()).all()
            return jsonify({
                "success": True,
                "users": [u.to_dict() for u in users]
            }), 200
            
        except Exception as e:
            logger.error(f"Ошибка получения списка пользователей: {str(e)}")
            return jsonify({"error": "Внутренняя ошибка"}), 500
