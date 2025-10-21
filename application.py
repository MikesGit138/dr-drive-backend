from flask import Flask, request, jsonify
import google.generativeai as genai
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import jwt
import os

application = Flask(__name__)

# Configure Database
application.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
application.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
application.config['JWT_EXPIRATION_HOURS'] = 24
application.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 
    'postgresql://dr_drive_db_user:I0obQSE1VHgl5Na3BxKLJkx6gevMcu3p@dpg-d3qj5uumcj7s73bp8sn0-a.oregon-postgres.render.com/dr_drive_db'
)
db = SQLAlchemy(application)

from flask_migrate import Migrate

migrate = Migrate(application, db)

# Configure Gemini API
BASE_SYSTEM_INSTRUCTION = ("You are an expert automotive mechanic AI assistant. "
                          "Your exclusive role is to provide accurate diagnostic advice, "
                          "explain repair procedures, discuss maintenance schedules, help users understand "
                          "automotive systems, and guide them through troubleshooting vehicle problems. "
                          "You will only assist with vehicle maintenance, repair, diagnostics, parts guidance, "
                          "and mechanical safety procedures. You must refuse all requests outside this scope—including "
                          "general knowledge, personal advice, creative writing, finance, legal matters, health topics, "
                          "or any non-automotive subjects—by politely redirecting: 'I am specifically designed to help with automotive "
                          "mechanical issues. Your question is outside my scope. Please ask me something about vehicle maintenance, "
                          "repair, or diagnostics.' Never engage with off-topic content, provide partial answers to unrelated questions, "
                          "or attempt to bridge non-mechanical topics to your expertise. When responding to mechanic-related queries, be "
                          "specific and detailed in your instructions, provide step-by-step guidance for complex repairs, specify output "
                          "formats when needed (like checklists or procedures), and if users share images of vehicles or parts, analyze the "
                          "relevant details they provide and tailor your advice specifically to what you observe rather than giving generic "
                          "responses. Always maintain professionalism and suggest professional service when safety or specialized equipment "
                          "is required.")

genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))


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

    def generate_token(self):
        """Generate JWT token with user claims including vehicle info"""
        payload = {
            'user_id': self.id,
            'username': self.username,
            'email': self.email,
            'year': self.year,
            'make': self.make,
            'model': self.model,
            'chassis': self.chassis,
            'exp': datetime.utcnow() + timedelta(hours=application.config['JWT_EXPIRATION_HOURS'])
        }
        return jwt.encode(payload, application.config['SECRET_KEY'], algorithm="HS256")


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
            data = jwt.decode(token, application.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])

            if not current_user:
                return jsonify({'error': 'User not found'}), 401

        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token is invalid'}), 401

        # Pass the decoded token data as well
        return f(current_user, data, *args, **kwargs)

    return decorated


def build_vehicle_context(token_data):
    """Build vehicle context string from token data"""
    vehicle_parts = []
    
    if token_data.get('year'):
        vehicle_parts.append(str(token_data['year']))
    if token_data.get('make'):
        vehicle_parts.append(token_data['make'])
    if token_data.get('model'):
        vehicle_parts.append(token_data['model'])
    
    vehicle_context = ""
    if vehicle_parts:
        vehicle_str = " ".join(vehicle_parts)
        vehicle_context = f"[VEHICLE: {vehicle_str}"
        
        if token_data.get('chassis'):
            vehicle_context += f", VIN/Chassis: {token_data['chassis']}"
        
        vehicle_context += "] "
    
    return vehicle_context


def get_system_instruction_with_vehicle(token_data):
    """Build system instruction with vehicle context"""
    vehicle_parts = []
    
    if token_data.get('year'):
        vehicle_parts.append(str(token_data['year']))
    if token_data.get('make'):
        vehicle_parts.append(token_data['make'])
    if token_data.get('model'):
        vehicle_parts.append(token_data['model'])
    
    if vehicle_parts:
        vehicle_str = " ".join(vehicle_parts)
        vehicle_info = f" The user you are assisting owns a {vehicle_str}."
        
        if token_data.get('chassis'):
            vehicle_info += f" The vehicle's VIN/Chassis number is {token_data['chassis']}."
        
        vehicle_info += (" When providing advice, prioritize information specific to this vehicle's make, model, and year. "
                        "Reference the specific vehicle when relevant, and tailor your diagnostic advice and repair procedures "
                        "to this particular vehicle unless the user asks about a different vehicle.")
        
        return BASE_SYSTEM_INSTRUCTION + vehicle_info
    
    return BASE_SYSTEM_INSTRUCTION


# Auth Routes
@application.route('/api/register', methods=['POST'])
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

        # Generate token with vehicle claims
        token = user.generate_token()

        return jsonify({
            'success': True,
            'message': 'User created successfully',
            'user': user.to_dict(),
            'token': token
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@application.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()

        if not data or not all(k in data for k in ['username', 'password']):
            return jsonify({'error': 'Username and password are required'}), 400

        user = User.query.filter_by(username=data['username']).first()

        if not user or not user.check_password(data['password']):
            return jsonify({'error': 'Invalid username or password'}), 401

        # Generate token with vehicle claims
        token = user.generate_token()

        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': user.to_dict(),
            'token': token
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Protected User Routes
@application.route('/api/profile', methods=['GET'])
@token_required
def get_profile(current_user, token_data):
    return jsonify({
        'success': True,
        'user': current_user.to_dict(),
        'token_claims': {
            'year': token_data.get('year'),
            'make': token_data.get('make'),
            'model': token_data.get('model'),
            'chassis': token_data.get('chassis')
        }
    })


@application.route('/api/profile', methods=['PUT'])
@token_required
def update_profile(current_user, token_data):
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

        # Generate new token with updated claims
        new_token = current_user.generate_token()

        return jsonify({
            'success': True,
            'message': 'Profile updated successfully',
            'user': current_user.to_dict(),
            'token': new_token
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# Admin Routes (kept for backward compatibility, but should be protected)
@application.route('/api/users', methods=['GET'])
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
@application.route('/api', methods=['GET'])
def hello():
    return 'Hello! Gemini API Flask Server is running.'


@application.route('/api/generate', methods=['POST'])
@token_required
def generate(current_user, token_data):
    try:
        print(f"Content-Type: {request.content_type}")
        print(f"Has files: {bool(request.files)}")
        print(f"Has form: {bool(request.form)}")
        print(f"User: {current_user.username}, Vehicle: {token_data.get('year')} {token_data.get('make')} {token_data.get('model')}")

        # Create model with user-specific system instruction
        system_instruction = get_system_instruction_with_vehicle(token_data)
        model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_instruction)

        # Check if request has files (multipart/form-data) or JSON
        if request.files or request.form:
            # Handle file upload from mobile app
            prompt = request.form.get('prompt', '')

            if not prompt:
                return jsonify({'error': 'Please provide a prompt'}), 400

            print(f"Prompt: {prompt}")

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
                'vehicle_info': {
                    'year': token_data.get('year'),
                    'make': token_data.get('make'),
                    'model': token_data.get('model'),
                    'chassis': token_data.get('chassis')
                },
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

            print(f"Prompt: {prompt}")

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
                'vehicle_info': {
                    'year': token_data.get('year'),
                    'make': token_data.get('make'),
                    'model': token_data.get('model'),
                    'chassis': token_data.get('chassis')
                },
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


@application.route('/api/chat', methods=['POST'])
@token_required
def chat(current_user, token_data):
    try:
        data = request.get_json()

        if not data or 'message' not in data:
            return jsonify({'error': 'Please provide a message in the request body'}), 400

        message = data['message']
        history = data.get('history', [])

        # Create model with user-specific system instruction
        system_instruction = get_system_instruction_with_vehicle(token_data)
        model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_instruction)

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
            'user_id': current_user.id,
            'vehicle_info': {
                'year': token_data.get('year'),
                'make': token_data.get('make'),
                'model': token_data.get('model'),
                'chassis': token_data.get('chassis')
            }
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
    with application.app_context():
        db.create_all()
        print("Database tables created successfully!")

    application.run(debug=True, host='0.0.0.0', port=6000)