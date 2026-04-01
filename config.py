#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CONFIG — КОНФИГУРАЦИЯ СЕРВЕРА
"""

import os
from datetime import timedelta

class Config:
    # Пароли доступа (как в auth.js)
    PASSWORDS = {
        "MORI": "user",
        "MORIFAMILY": "family",
        "MORIADMIN": "admin"
    }
    
    # JWT настройки
    JWT_SECRET_KEY = "mori-super-secret-key-2026"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
    
    # База данных
    SQLALCHEMY_DATABASE_URI = "sqlite:///database.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Сервер
    DEBUG = True
    HOST = "0.0.0.0"
    PORT = 5000
    
    # CORS (из api.js)
    ALLOWED_ORIGINS = [
        "http://localhost:8080",
        "http://127.0.0.1:8080", 
        "http://192.168.0.101:8080",
        "https://chrisostin.github.io",
        "https://mori-oracle.netlify.app",
        "https://mori-server.onrender.com"
    ]    
    
    # Дополнительные тенанты для 10+ приложений
    EXTRA_TENANTS = {}
