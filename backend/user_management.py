from flask import Flask, request, jsonify
import jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from functools import wraps
import os

def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv('POSTGRES_DB', 'blockchain_db'),
        user=os.getenv('POSTGRES_USER', 'blockchain_user'),
        password=os.getenv('POSTGRES_PASSWORD', 'blockchain_password'),
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432')
    )
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(200) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create images table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            image_data BYTEA NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cur.close()
    conn.close()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            data = jwt.decode(token, os.getenv(''), algorithms=["HS256"])
        except:
            return jsonify({'message': 'Invalid token'}), 401
            
        return f(*args, **kwargs)
    
    return decorated

def create_user_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    
    # Initialize database
    init_db()
    
    @app.route('/register', methods=['POST'])
    def register():
        data = request.get_json()
        
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({'message': 'Missing required fields'}), 400
            
        hashed_password = generate_password_hash(data['password'])
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id",
                (data['username'], hashed_password)
            )
            user_id = cur.fetchone()[0]
            conn.commit()
        except psycopg2.IntegrityError:
            conn.rollback()
            return jsonify({'message': 'Username already exists'}), 400
        finally:
            cur.close()
            conn.close()
            
        return jsonify({'message': 'User created successfully', 'user_id': user_id}), 201
    
    @app.route('/login', methods=['POST'])
    def login():
        data = request.get_json()
        
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({'message': 'Missing required fields'}), 400
            
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT id, password_hash FROM users WHERE username = %s",
            (data['username'],)
        )
        user = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if not user or not check_password_hash(user[1], data['password']):
            return jsonify({'message': 'Invalid credentials'}), 401
            
        token = jwt.encode({
            'user_id': user[0],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'])
        
        return jsonify({'token': token})
    
    def token_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = None
            auth_header = request.headers.get('Authorization')
            
            if auth_header:
                # Split 'Bearer <token>'
                try:
                    token = auth_header.split(' ')[1]
                except IndexError:
                    return jsonify({'message': 'Invalid token format'}), 401
            
            if not token:
                return jsonify({'message': 'Token is missing'}), 401
                
            try:
                # Decode the token
                data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
                current_user_id = data['user_id']
            except jwt.ExpiredSignatureError:
                return jsonify({'message': 'Token has expired'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'message': 'Invalid token'}), 401
                
            return f(*args, **kwargs)
        return decorated

    @app.route('/upload-image', methods=['POST'])
    @token_required
    def upload_image():
        if 'image' not in request.files:
            return jsonify({'message': 'No image provided'}), 400
            
        image = request.files['image']
        image_data = image.read()
        
        # Get the token from the Authorization header
        auth_header = request.headers.get('Authorization')
        token = auth_header.split(' ')[1]
        
        # Decode the token to get user_id
        user_id = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])['user_id']
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "INSERT INTO images (user_id, image_data) VALUES (%s, %s) RETURNING id",
            (user_id, psycopg2.Binary(image_data))
        )
        image_id = cur.fetchone()[0]
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'message': 'Image uploaded successfully', 'image_id': image_id}), 201
    
    @app.route('/get-image/<int:image_id>', methods=['GET'])
    @token_required
    def get_image(image_id):
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT image_data FROM images WHERE id = %s",
            (image_id,)
        )
        image = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if not image:
            return jsonify({'message': 'Image not found'}), 404
            
        return send_file(
            io.BytesIO(image[0]),
            mimetype='image/jpeg'
        )
    
    return app