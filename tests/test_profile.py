def test_get_profile(client):
    """Тест получения профиля"""
    login = client.post('/api/auth/login', json={
        'password': 'MORIADMIN'
    })
    token = login.get_json()['token']
    user_id = login.get_json()['user']['id']
    
    response = client.get(f'/api/user/{user_id}',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data['id'] == user_id
