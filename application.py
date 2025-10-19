from flask import Flask, request, jsonify
import google.generativeai as genai
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import jwt
import os

app = Flask(__name__)

# Configure Database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://localhost/mechanic_db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['JWT_EXPIRATION_HOURS'] = 24

db = SQLAlchemy(app)

from flask_migrate import Migrate
migrate = Migrate(app, db)

# Configure Gemini API
SYSTEM_INSTRUCTION = "You are a mechanic"
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=SYSTEM_INSTRUCTION)


# User Model
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    phone = db.Column(db.String(10), nullable=True)
    chassis = db.Column(db.String(80), nullable=True)
    year = db.Column(db.Integer, nullable=True)
    make = db.Column(db.String(10), nullable=True)
    model = db.Column(db.String(10), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'phone': self.phone,
            'chassis': self.chassis,
            'year': self.year,
            'make': self.make,
            'model': self.model,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


# JWT Token Decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Get token from Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]  # Bearer <token>
            except IndexError:
                return jsonify({'error': 'Token format invalid. Use: Bearer <token>'}), 401

        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        try:
            # Decode token
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])

            if not current_user:
                return jsonify({'error': 'User not found'}), 401

        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token is invalid'}), 401

        return f(current_user, *args, **kwargs)

    return decorated


# Auth Routes
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()

        required_fields = ['username', 'email', 'password']
        if not data or not all(k in data for k in required_fields):
            return jsonify({'error': 'Username, email, and password are required'}), 400

        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 400

        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 400

        user = User(
            username=data['username'],
            email=data['email'],
            phone=data.get('phone'),
            chassis=data.get('chassis'),
            year=data.get('year'),
            make=data.get('make'),
            model=data.get('model')
        )
        user.set_password(data['password'])

        db.session.add(user)
        db.session.commit()

        # Generate token
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(hours=app.config['JWT_EXPIRATION_HOURS'])
        }, app.config['SECRET_KEY'], algorithm="HS256")

        return jsonify({
            'success': True,
            'message': 'User created successfully',
            'user': user.to_dict(),
            'token': token
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()

        if not data or not all(k in data for k in ['username', 'password']):
            return jsonify({'error': 'Username and password are required'}), 400

        user = User.query.filter_by(username=data['username']).first()

        if not user or not user.check_password(data['password']):
            return jsonify({'error': 'Invalid username or password'}), 401

        # Generate token
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(hours=app.config['JWT_EXPIRATION_HOURS'])
        }, app.config['SECRET_KEY'], algorithm="HS256")

        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': user.to_dict(),
            'token': token
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Protected User Routes
@app.route('/api/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    return jsonify({
        'success': True,
        'user': current_user.to_dict()
    })


@app.route('/api/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    try:
        data = request.get_json()

        if 'username' in data:
            current_user.username = data['username']
        if 'email' in data:
            current_user.email = data['email']
        if 'password' in data:
            current_user.set_password(data['password'])
        if 'phone' in data:
            current_user.phone = data['phone']
        if 'chassis' in data:
            current_user.chassis = data['chassis']
        if 'year' in data:
            current_user.year = data['year']
        if 'make' in data:
            current_user.make = data['make']
        if 'model' in data:
            current_user.model = data['model']

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Profile updated successfully',
            'user': current_user.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# Admin Routes (kept for backward compatibility, but should be protected)
@app.route('/api/users', methods=['GET'])
def get_users():
    try:
        users = User.query.all()
        return jsonify({
            'success': True,
            'users': [user.to_dict() for user in users]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Protected Gemini Routes
@app.route('/api', methods=['GET'])
def hello():
    return 'Hello! Gemini API Flask Server is running.'


@app.route('/api/generate', methods=['POST'])
def generate():
    try:
        print(f"Content-Type: {request.content_type}")
        print(f"Has files: {bool(request.files)}")
        print(f"Has form: {bool(request.form)}")

        # Check if request has files (multipart/form-data) or JSON
        if request.files or request.form:
            # Handle file upload from mobile app
            prompt = request.form.get('prompt', '')

            if not prompt:
                return jsonify({'error': 'Please provide a prompt'}), 400

            # Get uploaded images
            uploaded_files = request.files.getlist('images')

            # Build content list for Gemini
            content = [prompt]

            from PIL import Image
            import io

            if uploaded_files:
                for file in uploaded_files:
                    # Read the file and convert to PIL Image
                    img_bytes = file.read()
                    img = Image.open(io.BytesIO(img_bytes))
                    content.append(img)

            # Generate content using Gemini
            response = model.generate_content(content)

            return jsonify({
                'success': True,
                'prompt': prompt,
                'images_count': len(uploaded_files),
                'response': response.text
            })

        else:
            # Handle JSON with base64 images (backward compatibility)
            data = request.get_json()

            if not data or 'prompt' not in data:
                return jsonify({'error': 'Please provide a prompt in the request body'}), 400

            prompt = data['prompt']
            images = data.get('images', [])

            # Build content list for Gemini
            content = [prompt]

            # Add images if provided
            if images:
                import base64
                from PIL import Image
                import io

                for img_data in images:
                    # Remove data URL prefix if present
                    if ',' in img_data:
                        img_data = img_data.split(',')[1]

                    # Add padding if needed
                    missing_padding = len(img_data) % 4
                    if missing_padding:
                        img_data += '=' * (4 - missing_padding)

                    # Decode base64 image
                    img_bytes = base64.b64decode(img_data)
                    img = Image.open(io.BytesIO(img_bytes))
                    content.append(img)

            # Generate content using Gemini
            response = model.generate_content(content)

            return jsonify({
                'success': True,
                'prompt': prompt,
                'images_count': len(images),
                'response': response.text
            })

    except Exception as e:
        print(f"Error in generate: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/chat', methods=['POST'])
@token_required
def chat(current_user):
    try:
        data = request.get_json()

        if not data or 'message' not in data:
            return jsonify({'error': 'Please provide a message in the request body'}), 400

        message = data['message']
        history = data.get('history', [])

        # Start a chat session
        chat = model.start_chat(history=history)
        response = chat.send_message(message)

        # Convert history to JSON serializable format
        history_json = []
        for msg in chat.history:
            history_json.append({
                'role': msg.role,
                'parts': [{'text': part.text} for part in msg.parts]
            })

        return jsonify({
            'success': True,
            'message': message,
            'response': response.text,
            'history': history_json,
            'user_id': current_user.id
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    # Check if API key is set
    if not os.environ.get('GEMINI_API_KEY'):
        print("Warning: GEMINI_API_KEY environment variable not set!")
        print("Set it with: export GEMINI_API_KEY='your-api-key'")

    # Create database tables
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")

    app.run(debug=True, host='0.0.0.0', port=6000)