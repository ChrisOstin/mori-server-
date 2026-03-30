#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
██████╗  ██████╗ ██╗   ██╗████████╗███████╗███████╗
██╔══██╗██╔═══██╗██║   ██║╚══██╔══╝██╔════╝██╔════╝
██████╔╝██║   ██║██║   ██║   ██║   █████╗  ███████╗
██╔══██╗██║   ██║██║   ██║   ██║   ██╔══╝  ╚════██║
██║  ██║╚██████╔╝╚██████╔╝   ██║   ███████╗███████║
╚═╝  ╚═╝ ╚═════╝  ╚═════╝    ╚═╝   ╚══════╝╚══════╝

MORI ROUTES — 35 ЭНДПОИНТОВ ДЛЯ МАСШТАБИРОВАНИЯ
Версия: 2.0.0
Статус: ГОТОВ К 10+ ПРИЛОЖЕНИЯМ
"""

import json
import logging
import requests
from datetime import datetime, timedelta
from functools import wraps

from flask import request, jsonify, send_file, g
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy import desc, func, or_

from models import db, User, Book, ChatMessage, FamilyMember, BudgetTransaction
from models import CalendarEvent, Reminder, MoriPrice, MoriHistory, Whale
from auth import requires_access_level, register_auth_routes
from database import session_scope, cached_query, get_db, retry_on_failure
from config import Config

logger = logging.getLogger('mori_routes')

# ========== ДЕКОРАТОР ДЛЯ ТЕНАНТОВ ==========
def with_tenant(f):
    """Добавляет информацию о тенанте в запрос"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Получаем tenant из заголовка или поддомена
        tenant = request.headers.get('X-Tenant-ID', 'main')
        g.tenant = tenant
        g.start_time = datetime.utcnow()
        
        # Добавляем в лог
        logger.debug(f"📌 Тенант: {tenant} | Path: {request.path}")
        
        return f(*args, **kwargs)
    return decorated_function
# ========== НОВАЯ ФУНКЦИЯ ДЛЯ ЦЕНЫ (DexScreener + fallback CoinGecko) ==========
def get_mori_price():
    """Получение текущей цены MORI — DexScreener + fallback CoinGecko"""
    
    # Пробуем DexScreener с User-Agent
    try:
        token_address = "8ZHE4ow1a2jjxuoMfyExuNamQNALv5ekZhsBn5nMDf5e"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resp = requests.get(
            f"https://api.dexscreener.com/latest/dex/search?q={token_address}",
            headers=headers,
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("pairs"):
                pair = data["pairs"][0]
                price = float(pair.get("priceUsd"))
                change24h = float(pair.get("priceChange", {}).get("h24", 0))
                volume24h = float(pair.get("volume", {}).get("h24", 0))
                liquidity = float(pair.get("liquidity", {}).get("usd", 0))
                fdv = price * 1_000_000_000
                marketCap = price * 400_000_000
                
                return jsonify({
                    "price": round(price, 6),
                    "change24h": round(change24h, 2),
                    "volume24h": int(volume24h),
                    "liquidity": int(liquidity),
                    "fdv": int(fdv),
                    "marketCap": int(marketCap),
                    "circulatingSupply": 400_000_000,
                    "timestamp": datetime.utcnow().timestamp()
                })
    except Exception as e:
        logger.error(f"DexScreener error: {e}")
    
    # Fallback: CoinGecko
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": "solana", "vs_currencies": "usd"}
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            sol_price = data.get("solana", {}).get("usd", 0)
            # 1 MORI ≈ 0.00005432 SOL (актуальное соотношение)
            mori_price = sol_price * 0.00005432
            return jsonify({
                "price": round(mori_price, 6),
                "change24h": 0,
                "volume24h": 0,
                "liquidity": 0,
                "fdv": 0,
                "marketCap": 0,
                "circulatingSupply": 400_000_000,
                "timestamp": datetime.utcnow().timestamp()
            })
    except Exception as e:
        logger.error(f"CoinGecko error: {e}")
    
    # Если всё упало
    return jsonify({"error": "Сервис временно недоступен"}), 503

@with_tenant
def get_mori_history():
    try:
        timeframe = request.args.get('timeframe', '1d')
        print(f"📊 Запрос истории для {timeframe}")
        
        days_map = {
            '12h': 1,
            '1d': 1,
            '3d': 3,
            '1m': 30,
            '3m': 90,
            '6m': 180,
            '12m': 365
        }
        days = days_map.get(timeframe, 1)
        
        url = "https://api.coingecko.com/api/v3/coins/solana/market_chart"
        params = {'vs_currency': 'usd', 'days': days}
        
        resp = requests.get(url, params=params, timeout=10)
        
        if resp.status_code != 200:
            print(f"❌ CoinGecko ошибка: {resp.status_code}")
            return jsonify([])
        
        data = resp.json()
        prices = data.get('prices', [])
        print(f"📈 Получено цен: {len(prices)}")
        
        if not prices:
            return jsonify([])
        
        result = []
        for ts, price in prices:
            mori_price = price * 0.00005432
            result.append({
                'x': ts,
                'y': round(mori_price, 6)
            })
        
        print(f"✅ Возвращаем {len(result)} точек")
        return jsonify(result)
        
    except Exception as e:
        print(f"💥 Ошибка: {e}")
        return jsonify([])
 
@with_tenant
@cached_query('whales', ttl=300)  # Кэш на 5 минут
def get_whales():
    """Получение списка крупных держателей"""
    try:
        whales = Whale.query.order_by(desc(Whale.amount)).limit(10).all()
            
        if not whales:
            # Тестовые данные
            whales_data = [
                {'address': '0x1234...5678', 'amount': 15000000, 'percentage': 15, 'change': 2.5},
                {'address': '0x8765...4321', 'amount': 12000000, 'percentage': 12, 'change': -1.2},
                {'address': '0xabcd...efgh', 'amount': 8000000, 'percentage': 8, 'change': 0.8},
                {'address': '0xefgh...ijkl', 'amount': 5000000, 'percentage': 5, 'change': 5.3},
                {'address': '0xijkl...mnop', 'amount': 3000000, 'percentage': 3, 'change': -0.5}
            ]
            return jsonify(whales_data), 200
            
        return jsonify([w.to_dict() for w in whales]), 200
            
    except Exception as e:
        logger.error(f"Ошибка получения китов: {e}")
        return jsonify([]), 200
    
# ========== БИБЛИОТЕКА ==========
    
@with_tenant
@cached_query('all_books', ttl=60)  # Кэш на 1 минуту
def get_books():
    """Получение всех книг"""
    try:
        books = Book.query.filter_by(is_public=True).order_by(Book.title).all()
        return jsonify({
            'success': True,
            'books': [b.to_dict() for b in books]
        }), 200
    except Exception as e:
        logger.error(f"Ошибка получения книг: {e}")
        return jsonify({'success': False, 'error': 'Ошибка загрузки'}), 500
    
@with_tenant
def get_book(book_id):
    """Получение конкретной книги"""
    try:
        book = Book.query.get(book_id)
        if not book or not book.is_public:
            return jsonify({'success': False, 'error': 'Книга не найдена'}), 404
            
        return jsonify({
            'success': True,
            'book': book.to_dict()
        }), 200
    except Exception as e:
        logger.error(f"Ошибка получения книги {book_id}: {e}")
        return jsonify({'success': False, 'error': 'Ошибка загрузки'}), 500
    
@with_tenant
def download_book(book_id):
    """Скачивание книги"""
    try:
        book = Book.query.get(book_id)
        if not book or not book.file_path:
            return jsonify({'success': False, 'error': 'Файл не найден'}), 404
            
        # Увеличиваем счётчик скачиваний
        book.downloads += 1
        db.session.commit()
            
        return send_file(
            book.file_path,
            as_attachment=True,
            download_name=f"{book.title}.{book.format}",
            mimetype='application/octet-stream'
        )
            
    except Exception as e:
        logger.error(f"Ошибка скачивания книги {book_id}: {e}")
        return jsonify({'success': False, 'error': 'Ошибка скачивания'}), 500
    
@with_tenant
@jwt_required()
@requires_access_level('admin')
def add_book():
    """Добавление книги (только админ)"""
    try:
        data = request.get_json()
            
        # Проверка обязательных полей
        required = ['title', 'author', 'category']
        for field in required:
            if field not in data:
                return jsonify({'success': False, 'error': f'Поле {field} обязательно'}), 400
            
        book = Book(
            title=data['title'],
            author=data['author'],
            category=data['category'],
            cover=data.get('cover', '📚'),
            pages=data.get('pages'),
            year=data.get('year'),
            description=data.get('description'),
            language=data.get('language', 'ru'),
            format=data.get('format', 'txt'),
            size=data.get('size'),
            file_path=data.get('file_path'),
            uploaded_by=get_jwt_identity()
        )
            
        db.session.add(book)
        db.session.commit()
            
        logger.info(f"📚 Добавлена книга: {book.title}")
            
        return jsonify({
            'success': True,
            'book': book.to_dict()
        }), 201
            
    except Exception as e:
        logger.error(f"Ошибка добавления книги: {e}")
        return jsonify({'success': False, 'error': 'Ошибка добавления'}), 500
    
@with_tenant
@jwt_required()
@requires_access_level('admin')
def update_book(book_id):
    """Обновление книги (только админ)"""
    try:
        book = Book.query.get(book_id)
        if not book:
            return jsonify({'success': False, 'error': 'Книга не найдена'}), 404
            
        data = request.get_json()
            
        # Обновляем поля
        updatable = ['title', 'author', 'category', 'cover', 'pages', 
                    'year', 'description', 'language', 'format', 'size', 
                    'file_path', 'is_public']
            
        for field in updatable:
            if field in data:
                setattr(book, field, data[field])
            
        db.session.commit()
        logger.info(f"📝 Обновлена книга: {book.title}")
            
        return jsonify({
            'success': True,
            'book': book.to_dict()
        }), 200
            
    except Exception as e:
        logger.error(f"Ошибка обновления книги {book_id}: {e}")
        return jsonify({'success': False, 'error': 'Ошибка обновления'}), 500
    
@with_tenant
@jwt_required()
@requires_access_level('admin')
def delete_book(book_id):
    """Удаление книги (только админ)"""
    try:
        book = Book.query.get(book_id)
        if not book:
            return jsonify({'success': False, 'error': 'Книга не найдена'}), 404
            
        db.session.delete(book)
        db.session.commit()
            
        logger.info(f"🗑️ Удалена книга: {book.title}")
            
        return jsonify({'success': True}), 200
            
    except Exception as e:
        logger.error(f"Ошибка удаления книги {book_id}: {e}")
        return jsonify({'success': False, 'error': 'Ошибка удаления'}), 500
    
# ========== ЧАТ ==========
@with_tenant
@jwt_required()
def get_chat_messages(chat_type):
    """Получение сообщений чата"""
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
            
        # Проверка типа чата
        if chat_type not in ['general', 'family', 'admin']:
            return jsonify({'success': False, 'error': 'Неверный тип чата'}), 400
            
        # Проверка доступа
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
            
        if chat_type == 'family' and user.access_level not in ['family', 'admin']:
            return jsonify({'success': False, 'error': 'Нет доступа'}), 403
            
        if chat_type == 'admin' and user.access_level != 'admin':
            return jsonify({'success': False, 'error': 'Нет доступа'}), 403
            
        messages = ChatMessage.query.filter_by(
            chat_type=chat_type,
            is_deleted=False
        ).order_by(
            desc(ChatMessage.created_at)
        ).limit(limit).offset(offset).all()
            
        # Добавляем информацию о пользователях
        result = []
        user_cache = {}
            
        for msg in messages:
            msg_dict = msg.to_dict()
                
            if msg.user_id not in user_cache:
                user_cache[msg.user_id] = User.query.get(msg.user_id)
                
            user = user_cache[msg.user_id]
            if user:
                msg_dict['user'] = {
                    'id': user.id,
                    'nickname': user.nickname,
                    'avatar': user.avatar,
                    'access_level': user.access_level
                }
                
            result.append(msg_dict)
            
        return jsonify({
            'success': True,
            'messages': result
        }), 200
            
    except Exception as e:
        logger.error(f"Ошибка получения сообщений: {e}")
        return jsonify({'success': False, 'error': 'Ошибка загрузки'}), 500
    
@with_tenant
@jwt_required()
def send_message():
    """Отправка сообщения"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
            
        chat_type = data.get('chat_type')
        text = data.get('text')
        reply_to = data.get('reply_to')
            
        if not chat_type or not text:
            return jsonify({'success': False, 'error': 'Не все поля заполнены'}), 400
            
        message = ChatMessage(
            chat_type=chat_type,
            user_id=user_id,
            text=text,
            reply_to=reply_to,
            created_at=datetime.utcnow()
        )
            
        db.session.add(message)
            
        # Обновляем статистику пользователя
        user = User.query.get(user_id)
        if user:
            user.messages_count += 1
            user.last_seen = datetime.utcnow()
            
        db.session.commit()
            
        # Добавляем информацию о пользователе
        msg_dict = message.to_dict()
        msg_dict['user'] = {
            'id': user.id,
            'nickname': user.nickname,
            'avatar': user.avatar,
            'access_level': user.access_level
        }
            
        logger.info(f"💬 Новое сообщение в {chat_type} от {user.nickname}")
            
        return jsonify({
            'success': True,
            'message': msg_dict
        }), 201
            
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        return jsonify({'success': False, 'error': 'Ошибка отправки'}), 500
    
@with_tenant
@jwt_required()
def toggle_reaction(message_id):
    """Добавление/удаление реакции"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        reaction = data.get('reaction')
            
        if not reaction:
            return jsonify({'success': False, 'error': 'Не указана реакция'}), 400
            
        message = ChatMessage.query.get(message_id)
        if not message:
            return jsonify({'success': False, 'error': 'Сообщение не найдено'}), 404
            
        # Загружаем текущие реакции
        reactions = json.loads(message.reactions) if message.reactions else {}
        reactions_users = json.loads(message.reactions_users) if message.reactions_users else {}
            
        users = reactions_users.get(reaction, [])
            
        if user_id in users:
            # Удаляем реакцию
            users.remove(user_id)
            reactions[reaction] = max(0, reactions.get(reaction, 1) - 1)
            if reactions[reaction] == 0:
                del reactions[reaction]
                del reactions_users[reaction]
            else:
                reactions_users[reaction] = users
        else:
            # Добавляем реакцию
            users.append(user_id)
            reactions[reaction] = len(users)
            reactions_users[reaction] = users
            
        message.reactions = json.dumps(reactions)
        message.reactions_users = json.dumps(reactions_users)
            
        db.session.commit()
            
        return jsonify({
            'success': True,
            'reactions': reactions,
            'reactionsUsers': reactions_users
        }), 200
            
    except Exception as e:
        logger.error(f"Ошибка обработки реакции: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
@with_tenant
@jwt_required()
@requires_access_level('family')
def get_chat_users():
    """Получение списка пользователей для чата"""
    try:
        users = User.query.filter_by(is_deleted=False, is_blocked=False).all()
            
        result = []
        for user in users:
            result.append({
                'id': user.id,
                'nickname': user.nickname,
                'avatar': user.avatar,
                'access_level': user.access_level,
                'online': (datetime.utcnow() - (user.last_seen or datetime.utcnow())).seconds < 300
            })
            
        return jsonify({
            'success': True,
            'users': result
        }), 200
            
    except Exception as e:
        logger.error(f"Ошибка получения пользователей: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
# ========== СЕМЬЯ ==========
    
@with_tenant
@jwt_required()
@requires_access_level('family')
def get_family_members():
    """Получение участников семьи"""
    try:
        members = FamilyMember.query.all()
            
        result = []
        for member in members:
            user = User.query.get(member.user_id)
            if user and not user.is_deleted:
                member_dict = member.to_dict()
                member_dict['user'] = user.to_dict()
                result.append(member_dict)
            
        # Определяем главу семьи
        head = FamilyMember.query.filter_by(is_head=True).first()
            
        return jsonify({
            'success': True,
            'members': result,
            'head_id': head.user_id if head else None
        }), 200
            
    except Exception as e:
        logger.error(f"Ошибка получения членов семьи: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
@with_tenant
@jwt_required()
@requires_access_level('family')
def add_family_member():
    """Добавление участника семьи (только глава)"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
            
        # Проверяем, что добавляющий - глава семьи
        head = FamilyMember.query.filter_by(user_id=user_id, is_head=True).first()
        if not head:
            return jsonify({'success': False, 'error': 'Только глава семьи может добавлять участников'}), 403
            
        new_user_id = data.get('user_id')
        role = data.get('role')
            
        if not new_user_id:
            return jsonify({'success': False, 'error': 'Не указан пользователь'}), 400
            
        # Проверяем, что пользователь существует
        user = User.query.get(new_user_id)
        if not user:
            return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404
            
        # Проверяем, что ещё не в семье
        existing = FamilyMember.query.filter_by(user_id=new_user_id).first()
        if existing:
            return jsonify({'success': False, 'error': 'Пользователь уже в семье'}), 400
            
        member = FamilyMember(
            user_id=new_user_id,
            role=role,
            joined_at=datetime.utcnow()
        )
            
        db.session.add(member)
            
        # Повышаем уровень доступа до family
        user.access_level = 'family'
            
        db.session.commit()
            
        logger.info(f"👨‍👩‍👧‍👦 Новый член семьи: {user.nickname}")
            
        return jsonify({
            'success': True,
            'member': member.to_dict()
        }), 201
            
    except Exception as e:
        logger.error(f"Ошибка добавления в семью: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
@with_tenant
@jwt_required()
@requires_access_level('family')
def remove_family_member(member_id):
    """Удаление участника семьи"""
    try:
        user_id = get_jwt_identity()
            
        # Проверяем права
        head = FamilyMember.query.filter_by(user_id=user_id, is_head=True).first()
        if not head and user_id != member_id:
            return jsonify({'success': False, 'error': 'Недостаточно прав'}), 403
            
        member = FamilyMember.query.filter_by(user_id=member_id).first()
        if not member:
            return jsonify({'success': False, 'error': 'Участник не найден'}), 404
            
        if member.is_head and user_id != member_id:
            return jsonify({'success': False, 'error': 'Нельзя удалить главу семьи'}), 403
            
        user = User.query.get(member_id)
        if user:
            user.access_level = 'user'
            
        db.session.delete(member)
        db.session.commit()
            
        logger.info(f"👋 Участник {user.nickname if user else member_id} покинул семью")
            
        return jsonify({'success': True}), 200
            
    except Exception as e:
        logger.error(f"Ошибка удаления из семьи: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
@with_tenant
@jwt_required()
@requires_access_level('family')
def get_budget():
    """Получение семейного бюджета"""
    try:
        transactions = BudgetTransaction.query.order_by(
            desc(BudgetTransaction.created_at)
        ).limit(100).all()
            
        total = sum(t.amount if t.type == 'income' else -t.amount for t in transactions)
        income = sum(t.amount for t in transactions if t.type == 'income')
        expenses = sum(t.amount for t in transactions if t.type == 'expense')
            
        return jsonify({
            'success': True,
            'budget': {
                'total': total,
                'income': income,
                'expenses': expenses,
                'history': [t.to_dict() for t in transactions]
            }
        }), 200
            
    except Exception as e:
        logger.error(f"Ошибка получения бюджета: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
@with_tenant
@jwt_required()
@requires_access_level('family')
def add_transaction():
    """Добавление транзакции в бюджет"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
            
        transaction_type = data.get('type')
        title = data.get('title')
        amount = data.get('amount')
            
        if not all([transaction_type, title, amount]):
            return jsonify({'success': False, 'error': 'Не все поля заполнены'}), 400
            
        if transaction_type not in ['income', 'expense']:
            return jsonify({'success': False, 'error': 'Неверный тип транзакции'}), 400
            
        transaction = BudgetTransaction(
            type=transaction_type,
            title=title,
            amount=amount,
            user_id=user_id,
            created_at=datetime.utcnow()
        )
            
        db.session.add(transaction)
        db.session.commit()
            
        logger.info(f"💰 {transaction_type}: {title} - {amount} MORI")
            
        return jsonify({
            'success': True,
            'transaction': transaction.to_dict()
        }), 201
            
    except Exception as e:
        logger.error(f"Ошибка добавления транзакции: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
@with_tenant
@jwt_required()
@requires_access_level('family')
def get_calendar_events():
    """Получение событий календаря"""
    try:
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)
            
        query = CalendarEvent.query
            
        if year and month is not None:
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)
                
            query = query.filter(
                CalendarEvent.date >= start_date,
                CalendarEvent.date < end_date
            )
            
        events = query.order_by(CalendarEvent.date).all()
            
        return jsonify({
            'success': True,
            'events': [e.to_dict() for e in events]
        }), 200
            
    except Exception as e:
        logger.error(f"Ошибка получения событий: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
@with_tenant
@jwt_required()
@requires_access_level('family')
def add_calendar_event():
    """Добавление события в календарь"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
            
        title = data.get('title')
        date_str = data.get('date')
        event_type = data.get('type', 'event')
            
        if not title or not date_str:
            return jsonify({'success': False, 'error': 'Не все поля заполнены'}), 400
            
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'error': 'Неверный формат даты'}), 400
            
        event = CalendarEvent(
            title=title,
            date=date,
            type=event_type,
            created_by=user_id,
            created_at=datetime.utcnow()
        )
            
        db.session.add(event)
        db.session.commit()
            
        logger.info(f"📅 Добавлено событие: {title}")
            
        return jsonify({
            'success': True,
            'event': event.to_dict()
        }), 201
            
    except Exception as e:
        logger.error(f"Ошибка добавления события: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
@with_tenant
@jwt_required()
@requires_access_level('family')
def delete_calendar_event(event_id):
    """Удаление события"""
    try:
        event = CalendarEvent.query.get(event_id)
        if not event:
            return jsonify({'success': False, 'error': 'Событие не найдено'}), 404
            
        db.session.delete(event)
        db.session.commit()
            
        logger.info(f"🗑️ Удалено событие: {event.title}")
            
        return jsonify({'success': True}), 200
            
    except Exception as e:
        logger.error(f"Ошибка удаления события: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
@with_tenant
@jwt_required()
@requires_access_level('family')
def get_reminders():
    """Получение напоминаний"""
    try:
        user_id = get_jwt_identity()
            
        reminders = Reminder.query.filter_by(
            user_id=user_id,
            completed=False
        ).order_by(Reminder.date).all()
            
        return jsonify({
            'success': True,
            'reminders': [r.to_dict() for r in reminders]
        }), 200
            
    except Exception as e:
        logger.error(f"Ошибка получения напоминаний: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
@with_tenant
@jwt_required()
@requires_access_level('family')
def add_reminder():
    """Добавление напоминания"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
            
        title = data.get('title')
        date_str = data.get('date')
        reminder_type = data.get('type', 'task')
            
        if not title or not date_str:
            return jsonify({'success': False, 'error': 'Не все поля заполнены'}), 400
            
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'error': 'Неверный формат даты'}), 400
            
        reminder = Reminder(
            title=title,
            date=date,
            type=reminder_type,
            user_id=user_id,
            created_at=datetime.utcnow()
        )
            
        db.session.add(reminder)
        db.session.commit()
            
        logger.info(f"⏰ Добавлено напоминание: {title}")
            
        return jsonify({
            'success': True,
            'reminder': reminder.to_dict()
        }), 201
            
    except Exception as e:
        logger.error(f"Ошибка добавления напоминания: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
@with_tenant
@jwt_required()
@requires_access_level('family')
def update_reminder(reminder_id):
    """Обновление напоминания (отметка о выполнении)"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
            
        reminder = Reminder.query.get(reminder_id)
        if not reminder:
            return jsonify({'success': False, 'error': 'Напоминание не найдено'}), 404
            
        if reminder.user_id != user_id:
            return jsonify({'success': False, 'error': 'Нет доступа'}), 403
            
        if 'completed' in data:
            reminder.completed = data['completed']
            
        db.session.commit()
            
        return jsonify({
            'success': True,
            'reminder': reminder.to_dict()
        }), 200
            
    except Exception as e:
        logger.error(f"Ошибка обновления напоминания: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
@with_tenant
@jwt_required()
@requires_access_level('family')
def delete_reminder(reminder_id):
    """Удаление напоминания"""
    try:
        user_id = get_jwt_identity()
            
        reminder = Reminder.query.get(reminder_id)
        if not reminder:
            return jsonify({'success': False, 'error': 'Напоминание не найдено'}), 404
            
        if reminder.user_id != user_id:
            return jsonify({'success': False, 'error': 'Нет доступа'}), 403
            
        db.session.delete(reminder)
        db.session.commit()
            
        logger.info(f"🗑️ Удалено напоминание: {reminder.title}")
            
        return jsonify({'success': True}), 200
            
    except Exception as e:
        logger.error(f"Ошибка удаления напоминания: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
# ========== ПРОФИЛЬ ==========
    
@with_tenant
@jwt_required()
def get_user_profile(user_id):
    """Получение профиля пользователя"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
            
        # Проверка прав
        if current_user_id != user_id and current_user.access_level not in ['admin', 'family']:
            return jsonify({'success': False, 'error': 'Недостаточно прав'}), 403
            
        user = User.query.get(user_id)
        if not user or user.is_deleted:
            return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404
            
        return jsonify(user.to_dict()), 200
            
    except Exception as e:
        logger.error(f"Ошибка получения профиля: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
@with_tenant
@jwt_required()
def get_user_stats(user_id):
    """Получение статистики пользователя"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
            
        if current_user_id != user_id and current_user.access_level != 'admin':
            return jsonify({'success': False, 'error': 'Недостаточно прав'}), 403
            
        user = User.query.get(user_id)
        if not user or user.is_deleted:
            return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404
            
        # Собираем статистику
        stats = {
            'messages': user.messages_count,
            'pagesRead': user.pages_read,
            'calculations': user.calculations,
            'aiQuestions': user.ai_questions,
            'level': user.level,
            'experience': user.experience,
            'nextLevelExp': user.level * 100,
            'progress': (user.experience / (user.level * 100)) * 100
        }
            
        return jsonify(stats), 200
            
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
# ========== АДМИНКА ==========
    
@with_tenant
@jwt_required()
@requires_access_level('admin')
def get_admin_stats():
    """Получение общей статистики (только админ)"""
    try:
        # Основные метрики
        total_users = User.query.filter_by(is_deleted=False).count()
        active_today = User.query.filter(
            User.last_seen >= datetime.utcnow() - timedelta(days=1)
        ).count()
        total_books = Book.query.filter_by(is_public=True).count()
        total_messages = ChatMessage.query.count()
        total_family = FamilyMember.query.count()
            
        # Статистика по уровням доступа
        access_stats = {
            'admin': User.query.filter_by(access_level='admin', is_deleted=False).count(),
            'family': User.query.filter_by(access_level='family', is_deleted=False).count(),
            'user': User.query.filter_by(access_level='user', is_deleted=False).count()
        }
            
        # Активность по дням (последние 7 дней)
        daily_activity = []
        for i in range(7):
            day = datetime.utcnow().date() - timedelta(days=i)
            count = User.query.filter(
                func.date(User.last_seen) == day
            ).count()
            daily_activity.append({
                'date': day.isoformat(),
                'active_users': count
            })
            
        return jsonify({
            'success': True,
            'stats': {
                'users': {
                    'total': total_users,
                    'active_today': active_today,
                    'by_access': access_stats,
                    'daily_activity': daily_activity
                },
                'content': {
                    'books': total_books,
                    'messages': total_messages,
                    'family_members': total_family
                }
            }
        }), 200
            
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
@with_tenant
@jwt_required()
@requires_access_level('admin')
def get_all_users():
    """Получение всех пользователей (только админ)"""
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        search = request.args.get('search', '')
            
        query = User.query.filter_by(is_deleted=False)
            
        if search:
            query = query.filter(
                or_(
                    User.nickname.contains(search),
                    User.username.contains(search)
                )
            )
            
        total = query.count()
        users = query.order_by(User.id).limit(limit).offset(offset).all()
            
        return jsonify({
            'success': True,
            'users': [u.to_dict() for u in users],
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200
            
    except Exception as e:
        logger.error(f"Ошибка получения пользователей: {e}")
        return jsonify({'success': False, 'error': 'Ошибка'}), 500
    
# ========== МЕТА ==========
    
def ping():
    """Пинг для проверки соединения"""
    return '', 204
    
def api_health():
    """Проверка здоровья API"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '2.0.0',
        'tenant': g.get('tenant', 'main')
    }), 200
    
def api_info():
    """Информация о API"""
    return jsonify({
        'name': 'MORI Oracle API',
        'version': '2.0.0',
        'description': 'API для MORI Oracle Mini App',
        'endpoints': 35,
        'auth': ['JWT', 'Multi-level'],
        'features': ['Portfolio', 'Library', 'Chat', 'Family', 'Profile', 'Admin']
    }), 200
    
# ========== РЕГИСТРАЦИЯ ВСЕХ РОУТОВ ==========
def register_all_routes(app):

    # Сначала регистрируем auth роуты
    register_auth_routes(app)

    # ========== РЕГИСТРАЦИЯ ВСЕХ МАРШРУТОВ ==========
    app.add_url_rule('/api/mori/price', view_func=get_mori_price, methods=['GET'])
    app.add_url_rule('/api/mori/history', view_func=get_mori_history, methods=['GET'])
    app.add_url_rule('/api/mori/whales', view_func=get_whales, methods=['GET'])

    app.add_url_rule('/api/books', view_func=get_books, methods=['GET'])
    app.add_url_rule('/api/books/<int:book_id>', view_func=get_book, methods=['GET'])
    app.add_url_rule('/api/books/<int:book_id>/download', view_func=download_book, methods=['GET'])
    app.add_url_rule('/api/books', view_func=add_book, methods=['POST'])
    app.add_url_rule('/api/books/<int:book_id>', view_func=update_book, methods=['PUT'])
    app.add_url_rule('/api/books/<int:book_id>', view_func=delete_book, methods=['DELETE'])

    app.add_url_rule('/api/chat/<string:chat_type>/messages', view_func=get_chat_messages, methods=['GET'])
    app.add_url_rule('/api/chat/message', view_func=send_message, methods=['POST'])
    app.add_url_rule('/api/chat/message/<int:message_id>/reaction', view_func=toggle_reaction, methods=['POST'])
    app.add_url_rule('/api/chat/users', view_func=get_chat_users, methods=['GET'])

    app.add_url_rule('/api/family/members', view_func=get_family_members, methods=['GET'])
    app.add_url_rule('/api/family/members', view_func=add_family_member, methods=['POST'])
    app.add_url_rule('/api/family/members/<int:member_id>', view_func=remove_family_member, methods=['DELETE'])
    app.add_url_rule('/api/family/budget', view_func=get_budget, methods=['GET'])
    app.add_url_rule('/api/family/budget', view_func=add_transaction, methods=['POST'])
    app.add_url_rule('/api/family/calendar', view_func=get_calendar_events, methods=['GET'])
    app.add_url_rule('/api/family/calendar', view_func=add_calendar_event, methods=['POST'])
    app.add_url_rule('/api/family/calendar/<int:event_id>', view_func=delete_calendar_event, methods=['DELETE'])
    app.add_url_rule('/api/family/reminders', view_func=get_reminders, methods=['GET'])
    app.add_url_rule('/api/family/reminders', view_func=add_reminder, methods=['POST'])
    app.add_url_rule('/api/family/reminders/<int:reminder_id>', view_func=update_reminder, methods=['PUT'])
    app.add_url_rule('/api/family/reminders/<int:reminder_id>', view_func=delete_reminder, methods=['DELETE'])

    app.add_url_rule('/api/user/<int:user_id>', view_func=get_user_profile, methods=['GET'])
    app.add_url_rule('/api/user/<int:user_id>/stats', view_func=get_user_stats, methods=['GET'])

    app.add_url_rule('/api/admin/stats', view_func=get_admin_stats, methods=['GET'])
    app.add_url_rule('/api/admin/users', view_func=get_all_users, methods=['GET'])

    app.add_url_rule('/api/ping', view_func=ping, methods=['GET'])
    app.add_url_rule('/api/health', view_func=api_health, methods=['GET'])
    app.add_url_rule('/api/info', view_func=api_info, methods=['GET'])

    logger.info(f"✅ Зарегистрировано 35 эндпоинтов для {len(Config.ALLOWED_ORIGINS)} origins")

