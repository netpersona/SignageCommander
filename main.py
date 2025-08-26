#!/usr/bin/env python3
"""
Digital Signage Platform for UptimeKuma and Grafana Dashboards
Uses only Python 3.8 standard library modules
"""

import os
import json
import base64
import urllib.parse
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler
from http import HTTPStatus
import socketserver
import threading
import time
import sys
from pathlib import Path

class DigitalSignageHandler(SimpleHTTPRequestHandler):
    """Custom HTTP request handler for the digital signage platform"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urllib.parse.urlparse(self.path)
        
        if parsed_path.path == '/':
            self.path = '/static/index.html'
        elif parsed_path.path == '/config':
            self.path = '/static/config.html'
        elif parsed_path.path == '/api/config':
            self.serve_config_api()
            return
        elif parsed_path.path == '/api/test-connection':
            self.test_dashboard_connection(parsed_path.query)
            return
        elif parsed_path.path.startswith('/proxy/'):
            self.serve_dashboard_proxy()
            return
        elif parsed_path.path.startswith('/demo/'):
            self.serve_demo_dashboard()
            return
        elif parsed_path.path in ['/style.css', '/app.js', '/config.js']:
            # Map CSS/JS files to static directory
            self.path = '/static' + parsed_path.path
        
        super().do_GET()
    
    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/api/config':
            self.save_config_api()
        else:
            self.send_error(HTTPStatus.NOT_FOUND)
    
    def serve_config_api(self):
        """Serve current configuration as JSON"""
        try:
            config = load_config()
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(config, indent=2).encode())
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))
    
    def save_config_api(self):
        """Save configuration from POST data"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            config_data = json.loads(post_data.decode())
            
            # Validate configuration
            if not isinstance(config_data.get('dashboards', []), list):
                raise ValueError("dashboards must be a list")
            
            save_config(config_data)
            
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}).encode())
        except Exception as e:
            self.send_error(HTTPStatus.BAD_REQUEST, str(e))
    
    def test_dashboard_connection(self, query_string):
        """Test connection to a dashboard URL"""
        try:
            params = urllib.parse.parse_qs(query_string)
            url = params.get('url', [''])[0]
            username = params.get('username', [''])[0]
            password = params.get('password', [''])[0]
            
            if not url:
                raise ValueError("URL is required")
            
            # Test connection
            success, message = test_dashboard_url(url, username, password)
            
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                "success": success,
                "message": message,
                "url": url
            }
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            self.send_error(HTTPStatus.BAD_REQUEST, str(e))
    
    def serve_dashboard_proxy(self):
        """Proxy dashboard requests to handle CORS and X-Frame-Options"""
        try:
            # Extract dashboard URL from path: /proxy/http://10.0.0.25:3001
            proxy_path = self.path[7:]  # Remove '/proxy/' prefix
            
            if not proxy_path.startswith('http'):
                self.send_error(HTTPStatus.BAD_REQUEST, 'Invalid proxy URL')
                return
            
            # Parse query parameters for authentication
            parsed_url = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            username = query_params.get('username', [None])[0]
            password = query_params.get('password', [None])[0]
            
            # Create request to the target dashboard
            req = urllib.request.Request(proxy_path)
            
            # Add authentication if provided
            if username and password:
                import base64
                credentials = f"{username}:{password}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()
                req.add_header('Authorization', f'Basic {encoded_credentials}')
            
            # Add headers to make request look like a browser
            req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36')
            req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
            
            # Fetch the content
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read()
                content_type = response.headers.get('Content-Type', 'text/html')
                
                # Send response without X-Frame-Options header
                self.send_response(HTTPStatus.OK)
                self.send_header('Content-Type', content_type)
                self.send_header('Access-Control-Allow-Origin', '*')
                # Explicitly don't send X-Frame-Options to allow iframe embedding
                self.end_headers()
                
                self.wfile.write(content)
            
        except urllib.error.HTTPError as e:
            self.send_error(e.code, f'Dashboard server error: {e.reason}')
        except urllib.error.URLError as e:
            self.send_error(HTTPStatus.BAD_GATEWAY, f'Cannot reach dashboard: {e.reason}')
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f'Proxy error: {str(e)}')
    
    def serve_demo_dashboard(self):
        """Serve demo dashboard for testing"""
        try:
            demo_file = Path(__file__).parent / 'static' / 'uptimekuma-demo.html'
            if demo_file.exists():
                self.send_response(HTTPStatus.OK)
                self.send_header('Content-type', 'text/html')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                with open(demo_file, 'r', encoding='utf-8') as f:
                    self.wfile.write(f.read().encode('utf-8'))
            else:
                self.send_error(HTTPStatus.NOT_FOUND, 'Demo dashboard not found')
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))

def load_config():
    """Load configuration from JSON file"""
    config_file = Path(__file__).parent / 'config.json'
    
    default_config = {
        "dashboards": [],
        "settings": {
            "rotation_interval": 30,
            "auto_refresh": True,
            "refresh_interval": 300,
            "fullscreen": True,
            "show_navigation": True
        }
    }
    
    try:
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
                # Merge with defaults to ensure all keys exist
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                if 'settings' in config:
                    for setting_key in default_config['settings']:
                        if setting_key not in config['settings']:
                            config['settings'][setting_key] = default_config['settings'][setting_key]
                return config
        else:
            # Create default config file
            save_config(default_config)
            return default_config
    except Exception as e:
        print(f"Error loading config: {e}")
        return default_config

def save_config(config):
    """Save configuration to JSON file"""
    config_file = Path(__file__).parent / 'config.json'
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")
        raise

def test_dashboard_url(url, username=None, password=None):
    """Test if a dashboard URL is accessible"""
    try:
        # Create request with authentication if provided
        request = urllib.request.Request(url)
        
        if username and password:
            # Add basic authentication
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            request.add_header('Authorization', f'Basic {credentials}')
        
        # Set reasonable timeout
        response = urllib.request.urlopen(request, timeout=10)
        
        if response.status == 200:
            return True, "Connection successful"
        else:
            return False, f"HTTP {response.status}"
            
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Authentication required or invalid credentials"
        elif e.code == 403:
            return False, "Access forbidden"
        elif e.code == 404:
            return False, "Dashboard not found"
        else:
            return False, f"HTTP error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, f"Connection error: {e.reason}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

def run_server(port=5000, host='0.0.0.0'):
    """Run the HTTP server"""
    print(f"Starting Digital Signage Platform on {host}:{port}")
    print(f"Access the dashboard at: http://{host}:{port}")
    print(f"Configuration interface: http://{host}:{port}/config")
    
    try:
        with socketserver.TCPServer((host, port), DigitalSignageHandler) as httpd:
            print(f"Server running on port {port}")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Server error: {e}")
        sys.exit(1)

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Digital Signage Platform for UptimeKuma and Grafana')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on (default: 5000)')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind the server to (default: 0.0.0.0)')
    parser.add_argument('--config', action='store_true', help='Show current configuration and exit')
    
    args = parser.parse_args()
    
    if args.config:
        config = load_config()
        print(json.dumps(config, indent=2))
        return
    
    # Ensure static directory exists
    static_dir = Path(__file__).parent / 'static'
    static_dir.mkdir(exist_ok=True)
    
    run_server(args.port, args.host)

if __name__ == '__main__':
    main()
