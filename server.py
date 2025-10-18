from flask import Flask, request, jsonify
import google.generativeai as genai
import os

app = Flask(__name__)

# Configure Gemini API
# Set your API key as an environment variable: GEMINI_API_KEY
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.5-flash' , contents="Explain how AI works in a few words")


@app.route('/api', methods=['GET'])
def hello():
    return 'Hello! Gemini API Flask Server is running.'


@app.route('/api/generate', methods=['POST'])
def generate():
    try:
        data = request.get_json()

        if not data or 'prompt' not in data:
            return jsonify({'error': 'Please provide a prompt in the request body'}), 400

        prompt = data['prompt']

        # Generate content using Gemini
        response = model.generate_content(prompt)

        return jsonify({
            'success': True,
            'prompt': prompt,
            'response': response.text
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/chat', methods=['POST'])
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

        return jsonify({
            'success': True,
            'message': message,
            'response': response.text,
            'history': chat.history
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

    app.run(debug=True, host='0.0.0.0', port=6000)