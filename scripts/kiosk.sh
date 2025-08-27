#!/bin/bash
# SignageCommander Platform Kiosk Mode Script
# Launches the digital signage platform in fullscreen kiosk mode

# Configuration
SIGNAGE_URL="http://localhost:5000"
BROWSER_CHOICE="${1:-chromium}"  # Default to chromium, allow override
DISPLAY="${DISPLAY:-:0}"         # Default display

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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
}

# Check if digital signage service is running
check_service() {
    log "Checking SignageCommander service..."
    
    if systemctl is-active --quiet digital-signage 2>/dev/null; then
        success "Digital signage service is running"
        return 0
    elif pgrep -f "python3.*main.py" > /dev/null; then
        success "Digital signage application is running"
        return 0
    else
        warning "Digital signage service is not running"
        log "Starting the service..."
        
        # Try to start systemd service first
        if systemctl start digital-signage 2>/dev/null; then
            sleep 3
            if systemctl is-active --quiet digital-signage; then
                success "Service started successfully"
                return 0
            fi
        fi
        
        # If systemd service fails, try running directly
        warning "Systemd service failed, attempting direct execution..."
        cd /opt/digital-signage 2>/dev/null || cd "$(dirname "$0")/.."
        
        if [[ -f main.py ]]; then
            python3 main.py &
            sleep 3
            if pgrep -f "python3.*main.py" > /dev/null; then
                success "Application started directly"
                return 0
            fi
        fi
        
        error "Failed to start digital signage application"
        exit 1
    fi
}

# Wait for service to be available
wait_for_service() {
    log "Waiting for service to be available at $SIGNAGE_URL..."
    
    for i in {1..30}; do
        if curl -s "$SIGNAGE_URL" > /dev/null 2>&1; then
            success "Service is available"
            return 0
        fi
        sleep 1
    done
    
    error "Service did not become available within 30 seconds"
    exit 1
}

# Launch browser in kiosk mode
launch_kiosk() {
    log "Launching kiosk mode with $BROWSER_CHOICE browser..."
    
    # Set display
    export DISPLAY="$DISPLAY"
    
    case "$BROWSER_CHOICE" in
        chromium|chrome)
            if command -v chromium-browser > /dev/null; then
                BROWSER_CMD="chromium-browser"
            elif command -v chromium > /dev/null; then
                BROWSER_CMD="chromium"
            elif command -v google-chrome > /dev/null; then
                BROWSER_CMD="google-chrome"
            else
                error "Chromium/Chrome not found. Try: $0 firefox"
                exit 1
            fi
            
            log "Starting $BROWSER_CMD in kiosk mode..."
            exec "$BROWSER_CMD" \
                --kiosk \
                --no-first-run \
                --disable-infobars \
                --disable-session-crashed-bubble \
                --disable-translate \
                --disable-features=TranslateUI \
                --disable-ipc-flooding-protection \
                --disable-background-timer-throttling \
                --disable-renderer-backgrounding \
                --disable-backgrounding-occluded-windows \
                --disable-field-trial-config \
                --force-device-scale-factor=1 \
                --autoplay-policy=no-user-gesture-required \
                --disable-web-security \
                --disable-features=VizDisplayCompositor \
                --start-fullscreen \
                "$SIGNAGE_URL"
            ;;
            
        firefox)
            if ! command -v firefox > /dev/null; then
                error "Firefox not found. Try: $0 chromium"
                exit 1
            fi
            
            log "Starting Firefox in kiosk mode..."
            
            # Create temporary Firefox profile for kiosk mode
            PROFILE_DIR="/tmp/firefox-kiosk-$$"
            mkdir -p "$PROFILE_DIR"
            
            # Configure Firefox for kiosk mode
            cat > "$PROFILE_DIR/user.js" << EOF
user_pref("browser.startup.homepage", "$SIGNAGE_URL");
user_pref("startup.homepage_welcome_url", "");
user_pref("browser.startup.page", 1);
user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);
user_pref("full-screen-api.approval-required", false);
user_pref("security.tls.insecure_fallback_hosts", "localhost");
user_pref("browser.dom.window.dump.enabled", true);
user_pref("media.autoplay.default", 0);
user_pref("media.autoplay.allow-extension-background-pages", true);
user_pref("media.autoplay.blocking_policy", 0);
EOF
            
            # Create chrome directory for CSS
            mkdir -p "$PROFILE_DIR/chrome"
            cat > "$PROFILE_DIR/chrome/userChrome.css" << EOF
@namespace url("http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul");
#nav-bar, #TabsToolbar, #PersonalToolbar { visibility: collapse !important; }
EOF
            
            exec firefox \
                --profile "$PROFILE_DIR" \
                --new-instance \
                --kiosk \
                "$SIGNAGE_URL"
            ;;
            
        *)
            error "Unsupported browser: $BROWSER_CHOICE"
            error "Supported browsers: chromium, chrome, firefox"
            exit 1
            ;;
    esac
}

# Cleanup function
cleanup() {
    log "Cleaning up..."
    
    # Remove temporary Firefox profile if it exists
    if [[ -n "$PROFILE_DIR" && -d "$PROFILE_DIR" ]]; then
        rm -rf "$PROFILE_DIR"
    fi
    
    # Kill browser processes if needed
    pkill -f "$BROWSER_CHOICE" 2>/dev/null || true
    
    exit 0
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Show usage
show_usage() {
    echo "SignageCommander Kiosk Mode Launcher"
    echo
    echo "Usage: $0 [browser]"
    echo
    echo "Browsers:"
    echo "  chromium  - Use Chromium browser (default)"
    echo "  firefox   - Use Firefox browser"
    echo
    echo "Examples:"
    echo "  $0           # Use default browser (chromium)"
    echo "  $0 firefox   # Use Firefox browser"
    echo
    echo "Environment Variables:"
    echo "  DISPLAY      - X11 display to use (default: :0)"
    echo
}

# Main execution
main() {
    log "Starting SignageCommander Kiosk Mode..."
    log "Target URL: $SIGNAGE_URL"
    log "Browser: $BROWSER_CHOICE"
    log "Display: $DISPLAY"
    echo
    
    check_service
    wait_for_service
    launch_kiosk
}

# Handle script arguments
case "${1:-}" in
    -h|--help|help)
        show_usage
        exit 0
        ;;
    *)
        main
        ;;
esac