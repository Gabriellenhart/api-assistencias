# /tests/test_auth.py

import json

def test_login_sucesso(client, init_database):
    """
    Testa o login de um usuário com credenciais válidas.
    Verifica se o status code é 200 e se os tokens são retornados.
    """
    # Dados do login para o usuário 'tecnico' criado na fixture 'init_database'
    login_data = {
        'email': 'admin@email.com',
        'password': '123456'
    }
    
    # Faz a requisição POST para o endpoint de login
    response = client.post('/auth/login', data=json.dumps(login_data), content_type='application/json')
    
    # Carrega a resposta JSON
    json_response = json.loads(response.data)
    
    # Asserções (verificações)
    assert response.status_code == 200
    assert 'access_token' in json_response
    assert 'refresh_token' in json_response
    assert json_response['message'] == 'Login realizado com sucesso!'

def test_login_senha_invalida(client, init_database):
    """
    Testa o login de um usuário com uma senha incorreta.
    Verifica se o status code é 401 (Unauthorized).
    """
    login_data = {
        'email': 'tecnico@test.com',
        'password': 'senhaincorreta'
    }
    
    response = client.post('/auth/login', data=json.dumps(login_data), content_type='application/json')
    json_response = json.loads(response.data)
    
    assert response.status_code == 401
    assert json_response['message'] == 'Credenciais inválidas. Verifique seu e-mail e senha.'

def test_login_email_invalido(client, init_database):
    """
    Testa o login com um e-mail que não existe no banco de dados.
    Verifica se o status code é 401.
    """
    login_data = {
        'email': 'naoexiste@test.com',
        'password': 'password123'
    }
    
    response = client.post('/auth/login', data=json.dumps(login_data), content_type='application/json')
    json_response = json.loads(response.data)
    
    assert response.status_code == 401

def test_refresh_token(client, init_database):
    """
    Testa a funcionalidade de refresh do token.
    1. Faz login para obter um refresh_token.
    2. Usa o refresh_token para obter um novo access_token.
    """
    # 1. Faz login para obter os tokens
    login_data = {'email': 'admin@test.com', 'password': 'supersecret'}
    login_response = client.post(
        '/auth/login', 
        data=json.dumps(login_data), 
        content_type='application/json'
    )
    assert login_response.status_code == 200
    tokens = json.loads(login_response.data)
    refresh_token = tokens.get('refresh_token')
    
    # Garante que o refresh token foi recebido
    assert refresh_token is not None

    # 2. Faz a requisição de refresh usando o refresh_token no header
    refresh_response = client.post(
        '/auth/refresh',
        headers={'Authorization': f'Bearer {refresh_token}'}
    )
    
    # Carrega a resposta do refresh
    new_token_data = json.loads(refresh_response.data)

    # Asserções FINAIS
    assert refresh_response.status_code == 200
    assert 'access_token' in new_token_data