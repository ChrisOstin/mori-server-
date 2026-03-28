def test_get_family_members_admin(client):
    """Тест получения членов семьи (админ)"""
    login = client.post('/api/auth/login', json={
        'password': 'MORIADMIN'
    })
    token = login.get_json()['token']
    
    response = client.get('/api/family/members',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert 'members' in data

def test_get_family_members_user(client):
    """Тест получения членов семьи (юзер - нельзя)"""
    login = client.post('/api/auth/login', json={
        'password': 'MORI'
    })
    token = login.get_json()['token']
    
    response = client.get('/api/family/members',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 403  # Доступ запрещён
