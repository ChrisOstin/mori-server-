def test_admin_stats_admin(client):
    """Тест получения статистики (админ)"""
    login = client.post('/api/auth/login', json={
        'password': 'MORIADMIN'
    })
    token = login.get_json()['token']
    
    response = client.get('/api/admin/stats',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert 'stats' in data

def test_admin_stats_user(client):
    """Тест получения статистики (юзер - нельзя)"""
    login = client.post('/api/auth/login', json={
        'password': 'MORI'
    })
    token = login.get_json()['token']
    
    response = client.get('/api/admin/stats',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 403
