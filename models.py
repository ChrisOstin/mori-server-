#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MORI MODELS
Полная структура данных для всего приложения
Версия: 1.0.0
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

# ========== ПОЛЬЗОВАТЕЛИ ==========
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(50), unique=True)
    avatar = db.Column(db.String(10), default='👤')
    access_level = db.Column(db.String(20), default='user')  # user, family, admin
    balance = db.Column(db.Float, default=0)
    
    # Статистика
    level = db.Column(db.Integer, default=1)
    experience = db.Column(db.Integer, default=0)
    messages_count = db.Column(db.Integer, default=0)
    pages_read = db.Column(db.Integer, default=0)
    calculations = db.Column(db.Integer, default=0)
    ai_questions = db.Column(db.Integer, default=0)
    
    # Настройки
    notifications = db.Column(db.Boolean, default=True)
    theme = db.Column(db.String(20), default='mori-classic')
    sound = db.Column(db.Boolean, default=True)
    vibration = db.Column(db.Boolean, default=True)
    privacy_online = db.Column(db.Boolean, default=True)
    privacy_balance = db.Column(db.Boolean, default=False)
    
    # Системные поля
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime)
    is_blocked = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    
    # Связи
    messages = db.relationship('ChatMessage', backref='author', lazy=True)
    transactions = db.relationship('BudgetTransaction', backref='user', lazy=True)
    reminders = db.relationship('Reminder', backref='user', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nickname': self.nickname,
            'username': self.username,
            'avatar': self.avatar,
            'access_level': self.access_level,
            'balance': self.balance,
            'level': self.level,
            'experience': self.experience,
            'stats': {
                'messages': self.messages_count,
                'pagesRead': self.pages_read,
                'calculations': self.calculations,
                'aiQuestions': self.ai_questions
            },
            'settings': {
                'notifications': self.notifications,
                'theme': self.theme,
                'sound': self.sound,
                'vibration': self.vibration,
                'privacyOnline': self.privacy_online,
                'privacyBalance': self.privacy_balance
            },
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None
        }

# ========== КНИГИ ==========
class Book(db.Model):
    __tablename__ = 'books'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    cover = db.Column(db.String(10), default='📚')
    pages = db.Column(db.Integer)
    year = db.Column(db.Integer)
    description = db.Column(db.Text)
    language = db.Column(db.String(10), default='ru')
    format = db.Column(db.String(10), default='txt')
    size = db.Column(db.String(20))
    file_path = db.Column(db.String(500))
    
    # Статистика
    downloads = db.Column(db.Integer, default=0)
    rating = db.Column(db.Float, default=0)
    rating_count = db.Column(db.Integer, default=0)
    
    # Системные поля
    is_public = db.Column(db.Boolean, default=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'category': self.category,
            'cover': self.cover,
            'pages': self.pages,
            'year': self.year,
            'description': self.description,
            'language': self.language,
            'format': self.format,
            'size': self.size,
            'rating': self.rating,
            'rating_count': self.rating_count,
            'downloads': self.downloads,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }

# ========== ЧАТ ==========
class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    chat_type = db.Column(db.String(20), nullable=False)  # general, family, admin
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    reply_to = db.Column(db.Integer)
    image = db.Column(db.String(500))
    voice = db.Column(db.String(500))
    voice_duration = db.Column(db.Integer)
    
    # Реакции в формате JSON: {"👍": 3, "❤️": 1}
    reactions = db.Column(db.Text, default='{}')
    reactions_users = db.Column(db.Text, default='{}')  # {"👍": [1,2,3], "❤️": [4]}
    
    # Системные поля
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    edited = db.Column(db.Boolean, default=False)
    edited_at = db.Column(db.DateTime)
    is_deleted = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'chat_type': self.chat_type,
            'userId': self.user_id,
            'text': self.text,
            'replyTo': self.reply_to,
            'image': self.image,
            'voice': self.voice,
            'voiceDuration': self.voice_duration,
            'reactions': json.loads(self.reactions) if self.reactions else {},
            'reactionsUsers': json.loads(self.reactions_users) if self.reactions_users else {},
            'timestamp': self.created_at.timestamp() * 1000 if self.created_at else None,
            'edited': self.edited,
            'editedAt': self.edited_at.timestamp() * 1000 if self.edited_at else None
        }

# ========== СЕМЬЯ ==========
class FamilyMember(db.Model):
    __tablename__ = 'family_members'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    role = db.Column(db.String(50))
    is_head = db.Column(db.Boolean, default=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связь
    user = db.relationship('User', backref='family_member')
    
    def to_dict(self):
        return {
            'id': self.user_id,
            'nickname': self.user.nickname if self.user else None,
            'avatar': self.user.avatar if self.user else '👤',
            'role': self.role,
            'isHead': self.is_head,
            'joinedAt': self.joined_at.isoformat() if self.joined_at else None
        }

class BudgetTransaction(db.Model):
    __tablename__ = 'budget_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10), nullable=False)  # income, expense
    title = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'title': self.title,
            'amount': self.amount,
            'userName': self.user.nickname if self.user else 'Пользователь',
            'timestamp': self.created_at.timestamp() * 1000 if self.created_at else None
        }

class CalendarEvent(db.Model):
    __tablename__ = 'calendar_events'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.Date, nullable=False)
    type = db.Column(db.String(20), default='event')  # event, birthday
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'date': self.date.isoformat() if self.date else None,
            'type': self.type
        }

class Reminder(db.Model):
    __tablename__ = 'reminders'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.Date, nullable=False)
    type = db.Column(db.String(20), default='task')  # task, birthday, event
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'date': self.date.isoformat() if self.date else None,
            'type': self.type,
            'completed': self.completed
        }

# ========== ПОРТФЕЛЬ (MORI) ==========
class MoriPrice(db.Model):
    __tablename__ = 'mori_prices'
    
    id = db.Column(db.Integer, primary_key=True)
    price = db.Column(db.Float, nullable=False)
    change_24h = db.Column(db.Float, default=0)
    volume_24h = db.Column(db.Float, default=0)
    liquidity = db.Column(db.Float, default=0)
    market_cap = db.Column(db.Float, default=0)
    fdv = db.Column(db.Float, default=0)
    circulating_supply = db.Column(db.Float, default=1000000000)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'price': self.price,
            'change24h': self.change_24h,
            'volume24h': self.volume_24h,
            'liquidity': self.liquidity,
            'marketCap': self.market_cap,
            'fdv': self.fdv,
            'circulatingSupply': self.circulating_supply,
            'timestamp': self.timestamp.timestamp() * 1000 if self.timestamp else None
        }

class MoriHistory(db.Model):
    __tablename__ = 'mori_history'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    open = db.Column(db.Float, nullable=False)
    high = db.Column(db.Float, nullable=False)
    low = db.Column(db.Float, nullable=False)
    close = db.Column(db.Float, nullable=False)
    volume = db.Column(db.Float, nullable=False)
    
    def to_dict(self):
        return {
            'x': self.timestamp.timestamp() * 1000 if self.timestamp else None,
            'o': self.open,
            'h': self.high,
            'l': self.low,
            'c': self.close,
            'v': self.volume
        }

class Whale(db.Model):
    __tablename__ = 'whales'
    
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    percentage = db.Column(db.Float)
    change = db.Column(db.Float, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'address': self.address,
            'amount': self.amount,
            'percentage': self.percentage,
            'change': self.change
        }
