import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_create_user(client):
    response = client.post('/users', json={'name': 'John'})
    assert response.status_code == 201
    assert response.json['name'] == 'John'

def test_get_users(client):
    client.post('/users', json={'name': 'John'})
    response = client.get('/users')
    assert response.status_code == 200
    assert len(response.json) > 0

def test_get_user(client):
    client.post('/users', json={'name': 'John'})
    response = client.get('/users/1')
    assert response.status_code == 200

def test_delete_user(client):
    client.post('/users', json={'name': 'John'})
    response = client.delete('/users/1')
    assert response.status_code == 200
