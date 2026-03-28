def test_login_admin(client):
    """Тест входа админа"""
    response = client.post('/api/auth/login', json={
        'password': 'MORIADMIN'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] == True
    assert 'token' in data
    assert data['user']['access_level'] == 'admin'

def test_login_family(client):
    """Тест входа семьи"""
    response = client.post('/api/auth/login', json={
        'password': 'MORIFAMILY'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['user']['access_level'] == 'family'

def test_login_user(client):
    """Тест входа юзера"""
    response = client.post('/api/auth/login', json={
        'password': 'MORI'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['user']['access_level'] == 'user'

def test_login_wrong_password(client):
    """Тест неверного пароля"""
    response = client.post('/api/auth/login', json={
        'password': 'huinya'
    })
    assert response.status_code == 401

def test_get_current_user(client):
    """Тест получения текущего юзера"""
    # Сначала логинимся
    login = client.post('/api/auth/login', json={
        'password': 'MORIADMIN'
    })
    token = login.get_json()['token']
    
    # Потом запрашиваем данные
    response = client.get('/api/auth/me', headers={
        'Authorization': f'Bearer {token}'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['nickname'] == 'ТестАдмин'
