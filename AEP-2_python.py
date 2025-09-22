# Issue: AEP-2
# Generated: 2025-09-22T05:39:45.982229
# Thread: 552dd45d
# Enhanced: LangChain structured generation
# AI Model: None
# Max Length: 25000 characters

import logging
import jwt
from flask import Flask, request, jsonify

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)

# Secret key for JWT token
SECRET_KEY = 'secret'

# User database (for demo purposes)
users = {
    'user1': 'password1',
    'user2': 'password2'
}

# Login API
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if username in users and users[username] == password:
        token = jwt.encode({'username': username}, SECRET_KEY, algorithm='HS256')
        return jsonify({'token': token.decode('utf-8')})
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

# Registration API
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if username in users:
        return jsonify({'error': 'Username already exists'}), 400
    else:
        users[username] = password
        return jsonify({'message': 'User registered successfully'})

if __name__ == '__main__':
    app.run()