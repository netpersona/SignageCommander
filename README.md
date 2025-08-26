# Digital Signage Platform

## Overview

A web-based digital signage platform designed to display and rotate between UptimeKuma status dashboards and Grafana monitoring dashboards. The application provides a kiosk-style interface with automatic rotation, fullscreen support, and keyboard navigation controls. Built with Python 3.8+ using only standard library modules for maximum compatibility and minimal dependencies.

![MainDash](https://github.com/user-attachments/assets/350fdb79-f1ae-4118-a70c-563e784f386f)

![DashConfig](https://github.com/user-attachments/assets/d75ad46a-be53-414f-a675-c9e05f7ef7ec)


## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Single Page Application (SPA)**: Pure vanilla JavaScript implementation without frameworks
- **Multi-page Structure**: Separate HTML files for main dashboard display (`index.html`) and configuration interface (`config.html`)
- **Component-based JavaScript**: Modular classes (`DigitalSignage`, `ConfigurationManager`) handling specific functionality
- **Responsive Design**: CSS-based responsive layout with fullscreen support and navigation controls

### Backend Architecture
- **Python HTTP Server**: Built on Python's standard library `http.server` module
- **Custom Request Handler**: `DigitalSignageHandler` extends `SimpleHTTPRequestHandler` for API and proxy functionality
- **Static File Serving**: Direct file serving for HTML, CSS, and JavaScript assets
- **API Endpoints**: RESTful endpoints for configuration management and dashboard connection testing
- **Proxy Service**: Built-in HTTP proxy to bypass CORS restrictions when accessing external dashboards

### Configuration Management
- **JSON-based Configuration**: Central `config.json` file storing dashboard URLs, credentials, and application settings
- **Real-time Updates**: Configuration changes applied without server restart
- **Dashboard Management**: Support for multiple dashboard types (UptimeKuma, Grafana) with individual enable/disable controls
- **Settings Management**: Rotation intervals, refresh rates, fullscreen preferences, and UI options

### Authentication & Security
- **Basic Authentication Support**: Username/password credentials stored for dashboard access
- **Proxy Authentication**: Server-side authentication handling to protect credentials from client exposure
- **Connection Testing**: Built-in connectivity validation for dashboard endpoints

### Display Management
- **Automatic Rotation**: Configurable time-based rotation between enabled dashboards
- **Manual Navigation**: Keyboard shortcuts and UI controls for manual dashboard switching
- **Fullscreen Mode**: Dedicated fullscreen support with auto-hide navigation
- **Responsive Iframe Loading**: Dynamic iframe management for embedding external dashboards

## External Dependencies

### Dashboard Systems
- **UptimeKuma**: Status monitoring dashboards accessed via HTTP
- **Grafana**: Data visualization and monitoring dashboards accessed via HTTP

### Network Requirements
- **HTTP/HTTPS Access**: Direct network access to configured dashboard URLs
- **CORS Handling**: Proxy functionality to bypass cross-origin restrictions
- **Local Network**: Typically deployed for internal network dashboard display

### Browser Compatibility
- **Modern Web Browsers**: Requires ES6+ support for JavaScript modules and classes
- **Fullscreen API**: Uses browser fullscreen capabilities for kiosk mode
- **Local Storage**: Browser storage for temporary settings and state management

### Runtime Environment
- **Python 3.8+**: No external Python packages required beyond standard library
- **File System Access**: Read/write access for configuration file management
- **Network Sockets**: HTTP server binding and external HTTP requests
