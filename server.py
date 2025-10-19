from flask import Flask, request, jsonify
import google.generativeai as genai
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)

# Configure Database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://localhost/mechanic_db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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
    phone = db.Column(db.String(10), nullable=False)
    chassis = db.Column(db.String(80), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    make = db.Column(db.String(10), nullable=False)
    model = db.Column(db.String(10), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


# User Routes
@app.route('/api/users', methods=['POST'])
def create_user():
    try:
        data = request.get_json()

        if not data or not all(k in data for k in ['username', 'email', 'password']):
            return jsonify({'error': 'Username, email, and password are required'}), 400

        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 400

        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 400

        user = User(username=data['username'], email=data['email'])
        user.set_password(data['password'])

        db.session.add(user)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'User created successfully',
            'user': user.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


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


@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify({
            'success': True,
            'user': user.to_dict()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json()

        if 'username' in data:
            user.username = data['username']
        if 'email' in data:
            user.email = data['email']
        if 'password' in data:
            user.set_password(data['password'])

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'User updated successfully',
            'user': user.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        db.session.delete(user)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'User deleted successfully'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# Gemini Routes
@app.route('/api', methods=['GET'])
def hello():
    return 'Hello! Gemini API Flask Server is running.'


# @app.route('/api/generate', methods=['POST'])
# def generate():
#     try:
#         data = request.get_json()
#
#         if not data or 'prompt' not in data:
#             return jsonify({'error': 'Please provide a prompt in the request body'}), 400
#
#         prompt = data['prompt']
#         images = data.get('images', [])  # Array of base64 encoded images
#
#         # Build content list for Gemini
#         content = [prompt]
#
#         # Add images if provided
#         if images:
#             import base64
#             from PIL import Image
#             import io
#
#             for img_data in images:
#                 # Remove data URL prefix if present
#                 if ',' in img_data:
#                     img_data = img_data.split(',')[1]
#
#                 # Add padding if needed
#                 missing_padding = len(img_data) % 4
#                 if missing_padding:
#                     img_data += '=' * (4 - missing_padding)
#
#                 # Decode base64 image
#                 img_bytes = base64.b64decode(img_data)
#                 img = Image.open(io.BytesIO(img_bytes))
#                 content.append(img)
#
#         # Generate content using Gemini
#         response = model.generate_content(content)
#
#         return jsonify({
#             'success': True,
#             'prompt': prompt,
#             'images_count': len(images),
#             'response': response.text
#         })
#
#     except Exception as e:
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

@app.route('/api/generate', methods=['POST'])
def generate():
    try:
        # Check if request has files (multipart/form-data) or JSON
        if request.files:
            # Handle file upload from mobile app
            prompt = request.form.get('prompt', '')

            if not prompt:
                return jsonify({'error': 'Please provide a prompt'}), 400

            # Get uploaded images
            uploaded_files = request.files.getlist('images')

            if not uploaded_files:
                return jsonify({'error': 'No images provided'}), 400

            # Build content list for Gemini
            content = [prompt]

            from PIL import Image
            import io

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
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/chat', methods=['POST'])
def chat():
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
            'history': history_json
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