#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EXCEPTIONS — КАСТОМНЫЕ ИСКЛЮЧЕНИЯ ДЛЯ 10+ ПРИЛОЖЕНИЙ
"""

class MoriBaseException(Exception):
    """Базовое исключение"""
    status_code = 500
    error_code = 'internal_error'
    
    def __init__(self, message=None, payload=None):
        super().__init__()
        self.message = message or self.__doc__
        self.payload = payload
    
    def to_dict(self):
        rv = {
            'error': self.error_code,
            'message': self.message
        }
        if self.payload:
            rv['details'] = self.payload
        return rv

# ========== 400 BAD REQUEST ==========
class BadRequestException(MoriBaseException):
    """Неверный запрос"""
    status_code = 400
    error_code = 'bad_request'

class ValidationException(BadRequestException):
    """Ошибка валидации"""
    error_code = 'validation_error'

class InvalidJSONException(BadRequestException):
    """Неверный JSON"""
    error_code = 'invalid_json'

# ========== 401 UNAUTHORIZED ==========
class UnauthorizedException(MoriBaseException):
    """Не авторизован"""
    status_code = 401
    error_code = 'unauthorized'

class TokenExpiredException(UnauthorizedException):
    """Токен истёк"""
    error_code = 'token_expired'

class InvalidTokenException(UnauthorizedException):
    """Неверный токен"""
    error_code = 'invalid_token'

# ========== 403 FORBIDDEN ==========
class ForbiddenException(MoriBaseException):
    """Доступ запрещён"""
    status_code = 403
    error_code = 'forbidden'

class InsufficientPermissionsException(ForbiddenException):
    """Недостаточно прав"""
    error_code = 'insufficient_permissions'

class IPBlockedException(ForbiddenException):
    """IP заблокирован"""
    error_code = 'ip_blocked'

# ========== 404 NOT FOUND ==========
class NotFoundException(MoriBaseException):
    """Не найдено"""
    status_code = 404
    error_code = 'not_found'

class UserNotFoundException(NotFoundException):
    """Пользователь не найден"""
    error_code = 'user_not_found'

class BookNotFoundException(NotFoundException):
    """Книга не найдена"""
    error_code = 'book_not_found'

# ========== 409 CONFLICT ==========
class ConflictException(MoriBaseException):
    """Конфликт"""
    status_code = 409
    error_code = 'conflict'

class UserExistsException(ConflictException):
    """Пользователь уже существует"""
    error_code = 'user_exists'

# ========== 429 TOO MANY REQUESTS ==========
class RateLimitException(MoriBaseException):
    """Слишком много запросов"""
    status_code = 429
    error_code = 'rate_limit_exceeded'

# ========== 500 INTERNAL ==========
class InternalException(MoriBaseException):
    """Внутренняя ошибка"""
    status_code = 500
    error_code = 'internal_error'

class DatabaseException(InternalException):
    """Ошибка базы данных"""
    error_code = 'database_error'

class CacheException(InternalException):
    """Ошибка кэша"""
    error_code = 'cache_error'

# ========== ХЕЛПЕР ДЛЯ ОБРАБОТКИ ==========
def register_error_handlers(app):
    """Регистрация обработчиков ошибок"""
    
    @app.errorhandler(MoriBaseException)
    def handle_mori_exception(error):
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response
    
    @app.errorhandler(400)
    def handle_bad_request(e):
        return jsonify(BadRequestException(str(e)).to_dict()), 400
    
    @app.errorhandler(401)
    def handle_unauthorized(e):
        return jsonify(UnauthorizedException().to_dict()), 401
    
    @app.errorhandler(403)
    def handle_forbidden(e):
        return jsonify(ForbiddenException().to_dict()), 403
    
    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify(NotFoundException().to_dict()), 404
    
    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        return jsonify({
            'error': 'method_not_allowed',
            'message': f'Метод {request.method} не поддерживается для {request.path}'
        }), 405
    
    @app.errorhandler(409)
    def handle_conflict(e):
        return jsonify(ConflictException(str(e)).to_dict()), 409
    
    @app.errorhandler(429)
    def handle_rate_limit(e):
        return jsonify(RateLimitException().to_dict()), 429
    
    @app.errorhandler(500)
    def handle_internal(e):
        logger.error(f"Unhandled error: {e}")
        return jsonify(InternalException().to_dict()), 500
