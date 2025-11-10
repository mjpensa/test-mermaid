"""
Web interface for LLM Diagram Processor
Provides a simple Flask web app for uploading and processing LLM output
"""

from flask import Flask, render_template, request, send_file, jsonify
import os
import tempfile
from llm_diagram_processor import LLMOutputProcessor
from pathlib import Path

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create temp directory for processing
TEMP_DIR = tempfile.mkdtemp()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/process', methods=['POST'])
def process_file():
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Read file content
        content = file.read().decode('utf-8')
        
        # Get output format from form
        output_format = request.form.get('format', 'html')
        
        # Process the content
        processor = LLMOutputProcessor(output_format=output_format)
        
        # Create output filename
        output_filename = f"processed_output.{output_format}"
        output_path = os.path.join(TEMP_DIR, output_filename)
        
        # Process
        stats = processor.process(content, output_path)
        
        # Return the processed file
        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename,
            mimetype='text/html' if output_format == 'html' else 'text/markdown'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/process-text', methods=['POST'])
def process_text():
    try:
        data = request.get_json()
        
        if 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400
        
        text = data['text']
        output_format = data.get('format', 'html')
        
        # Process the content
        processor = LLMOutputProcessor(output_format=output_format)
        
        # Create output filename
        output_filename = f"processed_output_{os.urandom(4).hex()}.{output_format}"
        output_path = os.path.join(TEMP_DIR, output_filename)
        
        # Process
        stats = processor.process(text, output_path)
        
        # Read the output file
        with open(output_path, 'r', encoding='utf-8') as f:
            output_content = f.read()
        
        return jsonify({
            'success': True,
            'output': output_content,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
