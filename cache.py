#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CACHE — МНОГОУРОВНЕВОЕ КЭШИРОВАНИЕ ДЛЯ 10+ ПРИЛОЖЕНИЙ
"""

import time
import json
import pickle
import hashlib
import logging
from threading import Lock
from collections import OrderedDict

logger = logging.getLogger('mori_cache')

# ========== LRU КЭШ (НАИБОЛЕЕ ЧАСТО ИСПОЛЬЗУЕМЫЕ) ==========
class LRUCache:
    """Кэш с вытеснением наименее используемых"""
    
    def __init__(self, capacity=1000, ttl=300):
        self.capacity = capacity
        self.ttl = ttl  # время жизни в секундах
        self.cache = OrderedDict()
        self.timestamps = {}
        self.hits = 0
        self.misses = 0
        self.lock = Lock()
    
    def get(self, key):
        """Получение из кэша"""
        with self.lock:
            if key in self.cache:
                # Проверяем TTL
                if time.time() - self.timestamps[key] < self.ttl:
                    self.cache.move_to_end(key)
                    self.hits += 1
                    return self.cache[key]
                else:
                    # Просрочено
                    del self.cache[key]
                    del self.timestamps[key]
            
            self.misses += 1
            return None
    
    def set(self, key, value):
        """Сохранение в кэш"""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            elif len(self.cache) >= self.capacity:
                # Удаляем самый старый
                oldest = next(iter(self.cache))
                del self.cache[oldest]
                del self.timestamps[oldest]
            
            self.cache[key] = value
            self.timestamps[key] = time.time()
    
    def delete(self, key):
        """Удаление из кэша"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                del self.timestamps[key]
                return True
        return False
    
    def clear(self):
        """Очистка кэша"""
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()
            logger.info("🧹 Кэш очищен")
    
    def get_stats(self):
        """Статистика"""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return {
            'size': len(self.cache),
            'capacity': self.capacity,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.2%}",
            'oldest': next(iter(self.timestamps.values())) if self.timestamps else None,
            'newest': next(reversed(self.timestamps.values())) if self.timestamps else None
        }

# ========== ТЭГИРОВАННЫЙ КЭШ (ДЛЯ ГРУППОВОЙ ИНВАЛИДАЦИИ) ==========
class TaggedCache:
    """Кэш с поддержкой тегов (для инвалидации групп)"""
    
    def __init__(self, lru_cache):
        self.lru = lru_cache
        self.tags = {}  # тег -> список ключей
    
    def get(self, key):
        return self.lru.get(key)
    
    def set(self, key, value, tags=None):
        self.lru.set(key, value)
        
        if tags:
            for tag in tags:
                if tag not in self.tags:
                    self.tags[tag] = []
                if key not in self.tags[tag]:
                    self.tags[tag].append(key)
    
    def invalidate_tag(self, tag):
        """Инвалидация всех ключей с тегом"""
        if tag in self.tags:
            for key in self.tags[tag]:
                self.lru.delete(key)
            del self.tags[tag]
            logger.info(f"🏷 Инвалидирован тег: {tag}")
    
    def invalidate_pattern(self, pattern):
        """Инвалидация по паттерну"""
        keys_to_delete = [k for k in self.lru.cache.keys() if pattern in k]
        for key in keys_to_delete:
            self.lru.delete(key)
        logger.info(f"🔍 Инвалидировано по паттерну '{pattern}': {len(keys_to_delete)} ключей")

# ========== ДВУХУРОВНЕВЫЙ КЭШ (ПАМЯТЬ + ФАЙЛЫ) ==========
class TwoLevelCache:
    """L1: память, L2: файлы (для больших данных)"""
    
    def __init__(self, memory_cache, cache_dir='./cache'):
        self.memory = memory_cache
        self.cache_dir = cache_dir
        import os
        os.makedirs(cache_dir, exist_ok=True)
    
    def get(self, key):
        # Сначала память
        value = self.memory.get(key)
        if value is not None:
            return value
        
        # Потом файл
        file_path = f"{self.cache_dir}/{hashlib.md5(key.encode()).hexdigest()}.cache"
        try:
            with open(file_path, 'rb') as f:
                value = pickle.load(f)
                # Сохраняем в память для будущих запросов
                self.memory.set(key, value)
                return value
        except:
            return None
    
    def set(self, key, value, to_disk=False):
        # Всегда в память
        self.memory.set(key, value)
        
        # Опционально на диск
        if to_disk:
            file_path = f"{self.cache_dir}/{hashlib.md5(key.encode()).hexdigest()}.cache"
            with open(file_path, 'wb') as f:
                pickle.dump(value, f)

# ========== ИНИЦИАЛИЗАЦИЯ ==========
# Основной кэш для частых запросов
main_cache = LRUCache(capacity=2000, ttl=300)

# Кэш с тегами для grouped инвалидации
tagged_cache = TaggedCache(main_cache)

# Двухуровневый кэш для больших данных
big_cache = TwoLevelCache(LRUCache(capacity=500, ttl=3600), cache_dir='./big_cache')

def get_cache_stats():
    """Статистика всех кэшей"""
    return {
        'main': main_cache.get_stats(),
        'tagged': {
            'tags': len(tagged_cache.tags),
            'total_keys': sum(len(keys) for keys in tagged_cache.tags.values())
        }
    }

def clear_all_caches():
    """Очистка всех кэшей"""
    main_cache.clear()
    tagged_cache.tags.clear()
    import shutil
    shutil.rmtree('./big_cache', ignore_errors=True)
    logger.info("🧹 Все кэши очищены")
