import pytest
from app import app as flask_app
from database import db as _db
from models import User

@pytest.fixture
def app():
    """Тестовое Flask приложение"""
    flask_app.config['TESTING'] = True
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    return flask_app

@pytest.fixture
def client(app):
    """Тестовый клиент"""
    return app.test_client()

@pytest.fixture
def db(app):
    """Тестовая БД"""
    with app.app_context():
        _db.create_all()
        
        # Создаём тестовых пользователей
        admin = User(
            nickname='ТестАдмин',
            access_level='admin',
            balance=1000
        )
        _db.session.add(admin)
        
        family = User(
            nickname='ТестСемья',
            access_level='family',
            balance=500
        )
        _db.session.add(family)
        
        user = User(
            nickname='ТестЮзер',
            access_level='user',
            balance=100
        )
        _db.session.add(user)
        
        _db.session.commit()
        
        yield _db
        _db.drop_all()
