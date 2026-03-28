def test_get_books(client):
    """Тест получения списка книг"""
    response = client.get('/api/books')
    assert response.status_code == 200
    data = response.get_json()
    assert 'books' in data
    assert len(data['books']) > 0

def test_get_book_by_id(client):
    """Тест получения конкретной книги"""
    response = client.get('/api/books/1')
    assert response.status_code == 200
    data = response.get_json()
    assert 'book' in data
    assert data['book']['id'] == 1

def test_add_book_admin(client):
    """Тест добавления книги (админ)"""
    # Логинимся админом
    login = client.post('/api/auth/login', json={
        'password': 'MORIADMIN'
    })
    token = login.get_json()['token']
    
    # Добавляем книгу
    response = client.post('/api/books', 
        json={
            'title': 'Тестовая книга',
            'author': 'Тест Автор',
            'category': 'test'
        },
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 201

def test_add_book_user(client):
    """Тест добавления книги (юзер - должно быть запрещено)"""
    # Логинимся юзером
    login = client.post('/api/auth/login', json={
        'password': 'MORI'
    })
    token = login.get_json()['token']
    
    # Пытаемся добавить книгу
    response = client.post('/api/books', 
        json={'title': 'Тест'},
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 403  # Доступ запрещён
