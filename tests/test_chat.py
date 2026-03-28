def test_get_messages(client):
    """Тест получения сообщений"""
    # Логинимся
    login = client.post('/api/auth/login', json={
        'password': 'MORIADMIN'
    })
    token = login.get_json()['token']
    
    # Получаем сообщения
    response = client.get('/api/chat/general/messages',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert 'messages' in data

def test_send_message(client):
    """Тест отправки сообщения"""
    login = client.post('/api/auth/login', json={
        'password': 'MORIADMIN'
    })
    token = login.get_json()['token']
    
    # Отправляем
    response = client.post('/api/chat/message',
        json={
            'chat_type': 'general',
            'text': 'Тестовое сообщение'
        },
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 201
