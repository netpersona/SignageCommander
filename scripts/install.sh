#!/bin/bash
# SignageCommander Platform Installation Script
# For RHEL 8 / CentOS 8 / Rocky Linux 8

set -e

# Configuration
SERVICE_NAME="digital-signage"
INSTALL_DIR="/opt/digital-signage"
SERVICE_USER="signage"
SERVICE_PORT="5000"
SERVICE_HOST="0.0.0.0"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root"
    fi
}

check_system() {
    log "Checking system requirements..."
    
    # Check RHEL/CentOS version
    if [[ -f /etc/redhat-release ]]; then
        VERSION=$(cat /etc/redhat-release)
        log "Detected: $VERSION"
        
        if ! echo "$VERSION" | grep -E "(Red Hat Enterprise Linux|CentOS|Rocky Linux).* 8\." > /dev/null; then
            warning "This script is designed for RHEL/CentOS/Rocky Linux 8.x"
        fi
    else
        warning "Not running on RHEL/CentOS/Rocky Linux"
    fi
    
    # Check Python 3.8+
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
        log "Python version: $PYTHON_VERSION"
        
        if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
            success "Python 3.8+ is available"
        else
            error "Python 3.8+ is required but not found"
        fi
    else
        error "Python 3 is not installed"
    fi
    
    # Check systemd
    if ! command -v systemctl &> /dev/null; then
        error "systemd is required but not found"
    fi
    
    success "System requirements met"
}

install_dependencies() {
    log "Installing system dependencies..."
    
    # Update package list
    dnf update -y
    
    # Install required packages
    dnf install -y python3 python3-pip chromium firefox
    
    success "Dependencies installed"
}

create_user() {
    log "Creating service user..."
    
    if id "$SERVICE_USER" &>/dev/null; then
        log "User $SERVICE_USER already exists"
    else
        useradd --system --shell /bin/false --home-dir "$INSTALL_DIR" --create-home "$SERVICE_USER"
        success "Created user: $SERVICE_USER"
    fi
}

install_application() {
    log "Installing SignageCommander Platform..."
    
    # Create installation directory
    mkdir -p "$INSTALL_DIR"
    
    # Copy application files
    cp -r . "$INSTALL_DIR/"
    
    # Create directories
    mkdir -p "$INSTALL_DIR/static"
    mkdir -p "$INSTALL_DIR/logs"
    
    # Set permissions
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
    chmod +x "$INSTALL_DIR/main.py"
    chmod +x "$INSTALL_DIR/scripts/kiosk.sh"
    
    # Create default config if it doesn't exist
    if [[ ! -f "$INSTALL_DIR/config.json" ]]; then
        log "Creating default configuration..."
        cat > "$INSTALL_DIR/config.json" << EOF
{
  "dashboards": [
    {
      "name": "Example Dashboard",
      "url": "http://localhost:3001",
      "type": "uptimekuma",
      "username": "",
      "password": "",
      "enabled": false
    }
  ],
  "settings": {
    "rotation_interval": 30,
    "auto_refresh": true,
    "refresh_interval": 300,
    "fullscreen": true,
    "show_navigation": true,
    "enable_keyboard_shortcuts": true
  }
}
EOF
        chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/config.json"
    fi
    
    success "Application installed to $INSTALL_DIR"
}

install_systemd_service() {
    log "Installing systemd service..."
    
    # Copy service file
    cp "$INSTALL_DIR/services/digital-signage.service" "/etc/systemd/system/"
    
    # Update service file with actual paths
    sed -i "s|/opt/digital-signage|$INSTALL_DIR|g" "/etc/systemd/system/digital-signage.service"
    sed -i "s|User=signage|User=$SERVICE_USER|g" "/etc/systemd/system/digital-signage.service"
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable service
    systemctl enable "$SERVICE_NAME"
    
    success "Systemd service installed and enabled"
}

configure_firewall() {
    log "Configuring firewall..."
    
    if command -v firewall-cmd &> /dev/null; then
        if systemctl is-active --quiet firewalld; then
            firewall-cmd --permanent --add-port="$SERVICE_PORT/tcp"
            firewall-cmd --reload
            success "Firewall configured to allow port $SERVICE_PORT"
        else
            warning "firewalld is not running, skipping firewall configuration"
        fi
    else
        warning "firewalld not found, skipping firewall configuration"
    fi
}

configure_selinux() {
    log "Configuring SELinux..."
    
    if command -v getenforce &> /dev/null && [[ $(getenforce) != "Disabled" ]]; then
        # Allow network connections
        setsebool -P httpd_can_network_connect 1
        
        # Set context for application directory
        semanage fcontext -a -t bin_t "$INSTALL_DIR/main.py" 2>/dev/null || true
        restorecon -R "$INSTALL_DIR" 2>/dev/null || true
        
        success "SELinux configured"
    else
        log "SELinux is disabled, skipping configuration"
    fi
}

start_service() {
    log "Starting SignageCommander service..."
    
    systemctl start "$SERVICE_NAME"
    
    # Wait a moment for service to start
    sleep 2
    
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        success "Service started successfully"
    else
        error "Failed to start service. Check logs with: journalctl -u $SERVICE_NAME"
    fi
}

show_completion_message() {
    echo
    success "SignageCommander Platform installation completed!"
    echo
    echo "Service Information:"
    echo "  - Service name: $SERVICE_NAME"
    echo "  - Installation directory: $INSTALL_DIR"
    echo "  - Service user: $SERVICE_USER"
    echo "  - Web interface: http://localhost:$SERVICE_PORT"
    echo "  - Configuration: http://localhost:$SERVICE_PORT/config"
    echo
    echo "Service Management:"
    echo "  - Start:   systemctl start $SERVICE_NAME"
    echo "  - Stop:    systemctl stop $SERVICE_NAME"
    echo "  - Restart: systemctl restart $SERVICE_NAME"
    echo "  - Status:  systemctl status $SERVICE_NAME"
    echo "  - Logs:    journalctl -u $SERVICE_NAME -f"
    echo
    echo "Kiosk Mode:"
    echo "  - Run: $INSTALL_DIR/scripts/kiosk.sh"
    echo
    echo "Next Steps:"
    echo "  1. Configure your dashboards at: http://localhost:$SERVICE_PORT/config"
    echo "  2. Add UptimeKuma and Grafana URLs with credentials"
    echo "  3. Start kiosk mode for fullscreen display"
    echo
}

# Main installation flow
main() {
    log "Starting SignageCommander Platform installation..."
    
    check_root
    check_system
    install_dependencies
    create_user
    install_application
    install_systemd_service
    configure_firewall
    configure_selinux
    start_service
    show_completion_message
}

# Handle script arguments
case "${1:-install}" in
    install)
        main
        ;;
    uninstall)
        log "Uninstalling SignageCommander Platform..."
        systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        systemctl disable "$SERVICE_NAME" 2>/dev/null || true
        rm -f "/etc/systemd/system/$SERVICE_NAME.service"
        systemctl daemon-reload
        userdel "$SERVICE_USER" 2>/dev/null || true
        rm -rf "$INSTALL_DIR"
        success "Uninstallation completed"
        ;;
    *)
        echo "Usage: $0 [install|uninstall]"
        exit 1
        ;;
esac
