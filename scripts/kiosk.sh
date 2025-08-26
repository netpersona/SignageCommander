#!/bin/bash
# Digital Signage Kiosk Mode Script
# Launches browser in fullscreen kiosk mode

# Configuration
SIGNAGE_URL="http://localhost:5000"
BROWSER_PREFERENCE="chromium"  # chromium, firefox, or auto
DISPLAY="${DISPLAY:-:0}"
LOG_FILE="/var/log/digital-signage-kiosk.log"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[KIOSK]${NC} $1"
    echo "$(date): $1" >> "$LOG_FILE" 2>/dev/null || true
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    echo "$(date): WARNING: $1" >> "$LOG_FILE" 2>/dev/null || true
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    echo "$(date): ERROR: $1" >> "$LOG_FILE" 2>/dev/null || true
    exit 1
}

check_display() {
    if [[ -z "$DISPLAY" ]]; then
        error "DISPLAY environment variable not set"
    fi
    
    if ! xset q &>/dev/null; then
        error "Cannot connect to X server at $DISPLAY"
    fi
    
    log "Connected to display: $DISPLAY"
}

detect_browser() {
    local browsers=()
    
    # Check for available browsers
    if command -v chromium-browser &> /dev/null; then
        browsers+=("chromium-browser")
    fi
    
    if command -v chromium &> /dev/null; then
        browsers+=("chromium")
    fi
    
    if command -v google-chrome &> /dev/null; then
        browsers+=("google-chrome")
    fi
    
    if command -v firefox &> /dev/null; then
        browsers+=("firefox")
    fi
    
    if [[ ${#browsers[@]} -eq 0 ]]; then
        error "No supported browser found. Install chromium or firefox."
    fi
    
    # Return preferred browser if available
    case "$BROWSER_PREFERENCE" in
        chromium)
            for browser in "${browsers[@]}"; do
                if [[ "$browser" =~ chromium ]]; then
                    echo "$browser"
                    return
                fi
            done
            ;;
        firefox)
            for browser in "${browsers[@]}"; do
                if [[ "$browser" == "firefox" ]]; then
                    echo "$browser"
                    return
                fi
            done
            ;;
        auto|*)
            # Return first available browser
            echo "${browsers[0]}"
            return
            ;;
    esac
    
    # Fallback to first available
    echo "${browsers[0]}"
}

wait_for_service() {
    log "Waiting for Digital Signage service to be ready..."
    
    local max_attempts=30
    local attempt=0
    
    while [[ $attempt -lt $max_attempts ]]; do
        if curl -s "$SIGNAGE_URL" > /dev/null 2>&1; then
            log "Service is ready"
            return 0
        fi
        
        ((attempt++))
        log "Attempt $attempt/$max_attempts: Service not ready, waiting..."
        sleep 2
    done
    
    error "Service did not become ready after $max_attempts attempts"
}

setup_environment() {
    log "Setting up kiosk environment..."
    
    # Disable screen saver and power management
    xset s off
    xset -dpms
    xset s noblank
    
    # Hide cursor after 5 seconds of inactivity
    if command -v unclutter &> /dev/null; then
        unclutter -idle 5 -root &
    fi
    
    # Set background to black
    if command -v xsetroot &> /dev/null; then
        xsetroot -solid black
    fi
    
    log "Environment configured"
}

launch_chromium() {
    local browser="$1"
    
    log "Launching Chromium-based browser: $browser"
    
    # Chromium arguments for kiosk mode
    local args=(
        --kiosk
        --no-first-run
        --disable-infobars
        --disable-features=TranslateUI
        --disable-ipc-flooding-protection
        --disable-background-timer-throttling
        --disable-backgrounding-occluded-windows
        --disable-renderer-backgrounding
        --disable-field-trial-config
        --disable-back-forward-cache
        --disable-web-security
        --disable-features=VizDisplayCompositor
        --start-fullscreen
        --window-position=0,0
        --window-size=1920,1080
        --no-sandbox
        --disable-dev-shm-usage
        --disable-gpu-sandbox
        --ignore-certificate-errors
        --ignore-ssl-errors
        --ignore-certificate-errors-spki-list
        --allow-running-insecure-content
        --autoplay-policy=no-user-gesture-required
        --user-data-dir=/tmp/signage-browser
        "$SIGNAGE_URL"
    )
    
    # Clean up any existing browser data
    rm -rf /tmp/signage-browser
    
    # Launch browser
    exec "$browser" "${args[@]}" &
    local browser_pid=$!
    
    log "Browser launched with PID: $browser_pid"
    return $browser_pid
}

launch_firefox() {
    local browser="$1"
    
    log "Launching Firefox: $browser"
    
    # Create Firefox profile for kiosk mode
    local profile_dir="/tmp/signage-firefox-profile"
    rm -rf "$profile_dir"
    mkdir -p "$profile_dir"
    
    # Firefox preferences for kiosk mode
    cat > "$profile_dir/user.js" << EOF
user_pref("browser.dom.window.dump.enabled", true);
user_pref("browser.fullscreen.autohide", true);
user_pref("browser.startup.homepage", "$SIGNAGE_URL");
user_pref("startup.homepage_welcome_url", "");
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.rights.3.shown", true);
user_pref("devtools.toolbox.host", "bottom");
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
user_pref("browser.tabs.warnOnClose", false);
user_pref("browser.tabs.warnOnCloseOtherTabs", false);
user_pref("browser.tabs.warnOnOpen", false);
user_pref("security.tls.insecure_fallback_hosts", "localhost");
user_pref("security.mixed_content.upgrade_display_content", false);
user_pref("media.autoplay.default", 0);
EOF
    
    # Firefox arguments
    local args=(
        -profile "$profile_dir"
        -no-remote
        -new-instance
        "$SIGNAGE_URL"
    )
    
    # Launch Firefox
    exec "$browser" "${args[@]}" &
    local browser_pid=$!
    
    # Wait a moment then enter fullscreen
    sleep 3
    xdotool key F11
    
    log "Firefox launched with PID: $browser_pid"
    return $browser_pid
}

monitor_browser() {
    local browser_pid=$1
    
    log "Monitoring browser process (PID: $browser_pid)"
    
    while kill -0 "$browser_pid" 2>/dev/null; do
        sleep 5
    done
    
    warning "Browser process terminated"
}

cleanup() {
    log "Cleaning up kiosk session..."
    
    # Kill any remaining browser processes
    pkill -f "chromium.*$SIGNAGE_URL" 2>/dev/null || true
    pkill -f "firefox.*signage-firefox-profile" 2>/dev/null || true
    
    # Clean up temp directories
    rm -rf /tmp/signage-browser /tmp/signage-firefox-profile
    
    # Restore screen saver
    xset s on
    xset +dpms
    
    log "Cleanup completed"
}

main() {
    log "Starting Digital Signage Kiosk Mode..."
    
    # Set up signal handlers
    trap cleanup EXIT
    trap 'log "Received interrupt signal"; exit 130' INT TERM
    
    # Check prerequisites
    check_display
    
    # Wait for service to be ready
    wait_for_service
    
    # Set up kiosk environment
    setup_environment
    
    # Detect and launch browser
    local browser
    browser=$(detect_browser)
    log "Selected browser: $browser"
    
    local browser_pid
    if [[ "$browser" =~ chromium|chrome ]]; then
        launch_chromium "$browser"
        browser_pid=$!
    elif [[ "$browser" == "firefox" ]]; then
        launch_firefox "$browser"
        browser_pid=$!
    else
        error "Unsupported browser: $browser"
    fi
    
    # Monitor browser
    monitor_browser "$browser_pid"
    
    # If we get here, browser exited
    warning "Kiosk mode ended"
}

# Handle script arguments
case "${1:-start}" in
    start)
        main
        ;;
    stop)
        log "Stopping kiosk mode..."
        cleanup
        log "Kiosk mode stopped"
        ;;
    restart)
        "$0" stop
        sleep 2
        "$0" start
        ;;
    status)
        if pgrep -f "chromium.*$SIGNAGE_URL" > /dev/null || pgrep -f "firefox.*signage-firefox-profile" > /dev/null; then
            log "Kiosk mode is running"
            exit 0
        else
            log "Kiosk mode is not running"
            exit 1
        fi
        ;;
    *)
        echo "Usage: $0 [start|stop|restart|status]"
        echo
        echo "Environment variables:"
        echo "  SIGNAGE_URL      - URL to display (default: http://localhost:5000)"
        echo "  BROWSER_PREFERENCE - Browser to use: chromium, firefox, or auto (default: chromium)"
        echo "  DISPLAY          - X display to use (default: :0)"
        echo
        echo "Examples:"
        echo "  $0 start                    # Start kiosk mode"
        echo "  SIGNAGE_URL=http://192.168.1.100:5000 $0 start"
        echo "  BROWSER_PREFERENCE=firefox $0 start"
        exit 1
        ;;
esac
