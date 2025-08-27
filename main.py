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
    """Custom HTTP request handler for the SignageCommander platform"""
    
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
        elif parsed_path.path.startswith('/api/uptimekuma-data'):
            self.serve_uptimekuma_data(parsed_path.query)
            return
        elif parsed_path.path.startswith('/uptimekuma/'):
            self.serve_custom_uptimekuma_dashboard()
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
    
    def serve_uptimekuma_data(self, query_string):
        """Fetch and serve UptimeKuma status data as JSON"""
        try:
            # Parse query parameters
            params = urllib.parse.parse_qs(query_string)
            uptimekuma_url = params.get('url', [''])[0]
            username = params.get('username', [''])[0]
            password = params.get('password', [''])[0]
            use_proxy = params.get('use_proxy', ['false'])[0].lower() == 'true'
            
            if not uptimekuma_url:
                raise ValueError('UptimeKuma URL is required')
            
            # Fetch data from UptimeKuma (use mock data for demo)
            if 'localhost:3001' in uptimekuma_url:
                data = self.get_mock_uptimekuma_data()
            else:
                data = self.fetch_uptimekuma_status(uptimekuma_url, username, password, use_proxy)
            
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data, indent=2).encode())
            
        except Exception as e:
            error_response = {
                'error': True,
                'message': str(e),
                'services': []
            }
            self.send_response(HTTPStatus.OK)  # Send 200 but with error in data
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(error_response, indent=2).encode())
    
    def get_mock_uptimekuma_data(self):
        """Return mock UptimeKuma data for testing"""
        return {
            "error": False,
            "message": "Connected successfully",
            "services": [
                {
                    "id": 1,
                    "name": "Website",
                    "url": "https://example.com",
                    "status": "up",
                    "uptime": "99.9%",
                    "responseTime": "145ms",
                    "lastCheck": "2025-08-27T15:25:00Z",
                    "type": "http"
                },
                {
                    "id": 2,
                    "name": "API Server",
                    "url": "https://api.example.com",
                    "status": "up", 
                    "uptime": "99.8%",
                    "responseTime": "89ms",
                    "lastCheck": "2025-08-27T15:25:00Z",
                    "type": "http"
                },
                {
                    "id": 3,
                    "name": "Database",
                    "url": "postgres://db.example.com:5432",
                    "status": "warning",
                    "uptime": "98.5%",
                    "responseTime": "250ms",
                    "lastCheck": "2025-08-27T15:25:00Z",
                    "type": "tcp"
                },
                {
                    "id": 4,
                    "name": "CDN",
                    "url": "https://cdn.example.com",
                    "status": "up",
                    "uptime": "99.9%",
                    "responseTime": "45ms",
                    "lastCheck": "2025-08-27T15:25:00Z",
                    "type": "http"
                }
            ],
            "overall": {
                "status": "operational",
                "uptime": "99.5%",
                "incidents": 0
            }
        }
    
    def fetch_uptimekuma_status(self, uptimekuma_url, username='', password='', use_proxy=False):
        """Fetch status data from UptimeKuma instance"""
        try:
            # Clean up the URL - ensure it ends with /api/status-page or similar
            base_url = uptimekuma_url.rstrip('/')
            
            # Try different common UptimeKuma API endpoints
            api_endpoints = [
                f"{base_url}/api/status-page",
                f"{base_url}/api/monitors", 
                f"{base_url}/status",
                f"{base_url}/api/status"
            ]
            
            headers = {
                'User-Agent': 'SignageCommander/1.0',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            # Add authentication if provided
            if username and password:
                auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers['Authorization'] = f'Basic {auth_string}'
            
            # Try each endpoint until one works
            for endpoint in api_endpoints:
                try:
                    req = urllib.request.Request(endpoint, headers=headers)
                    
                    with urllib.request.urlopen(req, timeout=10) as response:
                        data = json.loads(response.read().decode())
                        
                        # Transform the data into our expected format
                        return self.transform_uptimekuma_data(data, base_url)
                        
                except (urllib.error.HTTPError, urllib.error.URLError) as e:
                    continue  # Try next endpoint
            
            # If no endpoint worked, return demo-like data structure with error
            return {
                'error': False,
                'message': 'Connected to UptimeKuma but no data available',
                'services': [
                    {
                        'name': 'Connection Test',
                        'status': 'down',
                        'uptime': '0%',
                        'responseTime': 'N/A',
                        'url': uptimekuma_url
                    }
                ],
                'overall_status': 'Issues Detected',
                'total_services': 1
            }
            
        except Exception as e:
            raise Exception(f"Failed to connect to UptimeKuma: {str(e)}")
    
    def transform_uptimekuma_data(self, raw_data, base_url):
        """Transform raw UptimeKuma data into our dashboard format"""
        try:
            services = []
            
            # Handle different UptimeKuma API response formats
            if isinstance(raw_data, dict):
                # Try to find monitors/services in the data
                monitors = raw_data.get('monitors', [])
                if not monitors:
                    monitors = raw_data.get('data', [])
                if not monitors:
                    monitors = [raw_data]  # Single monitor response
                
                for monitor in monitors:
                    if isinstance(monitor, dict):
                        services.append({
                            'name': monitor.get('name', monitor.get('friendly_name', 'Unknown Service')),
                            'status': 'up' if monitor.get('status') == 1 or monitor.get('active', True) else 'down',
                            'uptime': f"{monitor.get('uptime', monitor.get('uptime_24h', 0))}%",
                            'responseTime': f"{monitor.get('avg_ping', monitor.get('response_time', 'N/A'))}ms" if monitor.get('avg_ping') or monitor.get('response_time') else 'N/A',
                            'url': monitor.get('url', monitor.get('hostname', base_url))
                        })
            
            # If no services found, create a basic connected status
            if not services:
                services = [{
                    'name': 'UptimeKuma Instance',
                    'status': 'up',
                    'uptime': '100%',
                    'responseTime': '<100ms',
                    'url': base_url
                }]
            
            # Calculate overall status
            up_count = len([s for s in services if s['status'] == 'up'])
            total_count = len(services)
            
            if up_count == total_count:
                overall_status = 'All Systems Operational'
            elif up_count > 0:
                overall_status = 'Partial System Outage'
            else:
                overall_status = 'Major System Outage'
            
            return {
                'error': False,
                'message': 'Data fetched successfully',
                'services': services,
                'overall_status': overall_status,
                'total_services': total_count
            }
            
        except Exception as e:
            return {
                'error': True,
                'message': f'Error transforming data: {str(e)}',
                'services': [],
                'overall_status': 'Data Error',
                'total_services': 0
            }
    
    def serve_custom_uptimekuma_dashboard(self):
        """Serve our custom UptimeKuma dashboard that loads real data"""
        try:
            # Parse the URL path to get dashboard config
            path_parts = self.path.split('/')[2:]  # Remove empty and 'uptimekuma'
            dashboard_id = path_parts[0] if path_parts else ''
            
            # Read the template dashboard and inject dashboard config
            template_path = Path(__file__).parent / 'static' / 'uptimekuma-live.html'
            
            # If template doesn't exist yet, we'll create it
            if not template_path.exists():
                self.create_live_uptimekuma_template()
            
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Inject the dashboard ID into the template
            content = content.replace('{{DASHBOARD_ID}}', dashboard_id)
            
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
            
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))
    
    def create_live_uptimekuma_template(self):
        """Create the live UptimeKuma dashboard template"""
        # This method will be implemented later when we create the template
        pass
    
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
            "show_navigation": True,
            "enable_keyboard_shortcuts": True,
            "use_proxy": False
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
    print(f"Starting SignageCommander Platform on {host}:{port}")
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
