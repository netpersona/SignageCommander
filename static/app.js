/**
 * Digital Signage Platform - Main Application
 * Manages dashboard display, rotation, and user interactions
 */

class DigitalSignage {
    constructor() {
        this.config = null;
        this.dashboards = [];
        this.currentIndex = 0;
        this.rotationTimer = null;
        this.refreshTimer = null;
        this.isRotationPaused = false;
        this.isFullscreen = false;
        this.lastActivity = Date.now();
        
        this.init();
    }
    
    async init() {
        console.log('Initializing Digital Signage Platform...');
        
        // Load configuration
        await this.loadConfig();
        
        // Setup UI elements
        this.setupUI();
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Initialize dashboards
        this.initializeDashboards();
        
        // Start the application
        this.start();
        
        console.log('Digital Signage Platform initialized');
    }
    
    async loadConfig() {
        try {
            const response = await fetch('/api/config');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.config = await response.json();
            this.dashboards = this.config.dashboards.filter(d => d.enabled);
            
            console.log('Configuration loaded:', this.config);
            console.log('Active dashboards:', this.dashboards.length);
            
        } catch (error) {
            console.error('Failed to load configuration:', error);
            this.showError('Configuration Error', `Failed to load configuration: ${error.message}`);
        }
    }
    
    setupUI() {
        // Time display
        this.updateClock();
        setInterval(() => this.updateClock(), 1000);
        
        // Hide loading screen
        document.getElementById('loading').style.display = 'none';
        
        // Show error if no dashboards configured
        if (!this.dashboards || this.dashboards.length === 0) {
            document.getElementById('error-state').style.display = 'block';
            return;
        }
        
        // Setup progress indicators
        this.setupProgressIndicators();
        
        // Apply initial settings
        this.applySettings();
    }
    
    setupEventListeners() {
        // Navigation buttons
        document.getElementById('prev-btn').addEventListener('click', () => this.previousDashboard());
        document.getElementById('next-btn').addEventListener('click', () => this.nextDashboard());
        document.getElementById('pause-btn').addEventListener('click', () => this.toggleRotation());
        document.getElementById('refresh-btn').addEventListener('click', () => this.refreshCurrent());
        document.getElementById('fullscreen-btn').addEventListener('click', () => this.toggleFullscreen());
        
        // Retry button for network errors
        const retryBtn = document.getElementById('retry-btn');
        if (retryBtn) {
            retryBtn.addEventListener('click', () => this.retryConnection());
        }
        
        // Keyboard shortcuts
        if (this.config?.settings?.enable_keyboard_shortcuts !== false) {
            document.addEventListener('keydown', (e) => this.handleKeyboard(e));
        }
        
        // Activity tracking for auto-hide
        document.addEventListener('mousemove', () => this.trackActivity());
        document.addEventListener('keydown', () => this.trackActivity());
        
        // Fullscreen change events
        document.addEventListener('fullscreenchange', () => this.handleFullscreenChange());
        document.addEventListener('webkitfullscreenchange', () => this.handleFullscreenChange());
        document.addEventListener('mozfullscreenchange', () => this.handleFullscreenChange());
        document.addEventListener('MSFullscreenChange', () => this.handleFullscreenChange());
        
        // Window focus events for refresh
        document.addEventListener('visibilitychange', () => this.handleVisibilityChange());
        window.addEventListener('focus', () => this.handleWindowFocus());
    }
    
    initializeDashboards() {
        if (!this.dashboards || this.dashboards.length === 0) {
            return;
        }
        
        const container = document.getElementById('dashboard-container');
        
        // Remove existing iframes
        container.querySelectorAll('.dashboard-iframe').forEach(iframe => iframe.remove());
        
        // Create iframe for each dashboard
        this.dashboards.forEach((dashboard, index) => {
            const iframe = document.createElement('iframe');
            iframe.className = 'dashboard-iframe';
            iframe.src = this.buildDashboardUrl(dashboard);
            iframe.setAttribute('loading', 'lazy');
            iframe.setAttribute('sandbox', 'allow-same-origin allow-scripts allow-forms allow-popups allow-top-navigation');
            
            // Error handling for iframe loading
            iframe.addEventListener('error', () => {
                console.error(`Failed to load dashboard: ${dashboard.name}`);
                this.showNetworkError(`Failed to load ${dashboard.name}`, dashboard.url);
            });
            
            iframe.addEventListener('load', () => {
                console.log(`Dashboard loaded: ${dashboard.name}`);
            });
            
            container.appendChild(iframe);
        });
    }
    
    buildDashboardUrl(dashboard) {
        let url = dashboard.url;
        
        // Check if this is an external URL that needs proxying
        const isExternal = url.startsWith('http://') || url.startsWith('https://');
        
        if (isExternal) {
            // Use proxy to bypass X-Frame-Options and CORS restrictions
            let proxyUrl = `/proxy/${url}`;
            
            // Add authentication parameters for proxy if provided
            if (dashboard.username && dashboard.password) {
                const separator = proxyUrl.includes('?') ? '&' : '?';
                proxyUrl += `${separator}username=${encodeURIComponent(dashboard.username)}&password=${encodeURIComponent(dashboard.password)}`;
            }
            
            // Add cache-busting parameter
            const separator = proxyUrl.includes('?') ? '&' : '?';
            proxyUrl += `${separator}_t=${Date.now()}`;
            
            return proxyUrl;
        } else {
            // For local/relative URLs, use original logic
            if (dashboard.username && dashboard.password) {
                try {
                    const urlObj = new URL(url, window.location.origin);
                    urlObj.username = dashboard.username;
                    urlObj.password = dashboard.password;
                    url = urlObj.toString();
                } catch (error) {
                    console.warn('Failed to add authentication to URL:', error);
                }
            }
            
            // Add cache-busting parameter for refreshes
            const separator = url.includes('?') ? '&' : '?';
            url += `${separator}_t=${Date.now()}`;
            
            return url;
        }
    }
    
    setupProgressIndicators() {
        const dotsContainer = document.getElementById('progress-dots');
        dotsContainer.innerHTML = '';
        
        this.dashboards.forEach((_, index) => {
            const dot = document.createElement('div');
            dot.className = 'progress-dot';
            if (index === 0) dot.classList.add('active');
            dotsContainer.appendChild(dot);
        });
    }
    
    applySettings() {
        const settings = this.config?.settings || {};
        
        // Navigation visibility
        if (settings.show_navigation === false) {
            document.getElementById('navigation').style.display = 'none';
        }
        
        // Auto fullscreen
        if (settings.fullscreen && !this.isFullscreen) {
            setTimeout(() => this.enterFullscreen(), 1000);
        }
    }
    
    start() {
        if (!this.dashboards || this.dashboards.length === 0) {
            return;
        }
        
        // Show first dashboard
        this.showDashboard(0);
        
        // Start rotation timer
        this.startRotation();
        
        // Start auto-refresh timer
        if (this.config?.settings?.auto_refresh !== false) {
            this.startAutoRefresh();
        }
    }
    
    showDashboard(index) {
        if (!this.dashboards || index < 0 || index >= this.dashboards.length) {
            return;
        }
        
        const container = document.getElementById('dashboard-container');
        const iframes = container.querySelectorAll('.dashboard-iframe');
        const dots = document.querySelectorAll('.progress-dot');
        
        // Hide all iframes
        iframes.forEach(iframe => iframe.classList.remove('active'));
        dots.forEach(dot => dot.classList.remove('active'));
        
        // Show current iframe
        if (iframes[index]) {
            iframes[index].classList.add('active');
        }
        
        if (dots[index]) {
            dots[index].classList.add('active');
        }
        
        // Update current dashboard display
        const currentDashboard = this.dashboards[index];
        document.getElementById('current-dashboard').textContent = currentDashboard.name;
        
        this.currentIndex = index;
        
        // Hide error states
        document.getElementById('network-error').style.display = 'none';
        
        console.log(`Showing dashboard: ${currentDashboard.name} (${index + 1}/${this.dashboards.length})`);
    }
    
    nextDashboard() {
        if (!this.dashboards || this.dashboards.length === 0) return;
        
        const nextIndex = (this.currentIndex + 1) % this.dashboards.length;
        this.showDashboard(nextIndex);
        this.resetRotationTimer();
    }
    
    previousDashboard() {
        if (!this.dashboards || this.dashboards.length === 0) return;
        
        const prevIndex = this.currentIndex === 0 ? this.dashboards.length - 1 : this.currentIndex - 1;
        this.showDashboard(prevIndex);
        this.resetRotationTimer();
    }
    
    startRotation() {
        if (!this.dashboards || this.dashboards.length <= 1) return;
        
        const interval = (this.config?.settings?.rotation_interval || 30) * 1000;
        
        this.rotationTimer = setInterval(() => {
            if (!this.isRotationPaused) {
                this.nextDashboard();
            }
        }, interval);
        
        this.updateRotationStatus();
    }
    
    stopRotation() {
        if (this.rotationTimer) {
            clearInterval(this.rotationTimer);
            this.rotationTimer = null;
        }
    }
    
    resetRotationTimer() {
        this.stopRotation();
        if (!this.isRotationPaused) {
            this.startRotation();
        }
    }
    
    toggleRotation() {
        this.isRotationPaused = !this.isRotationPaused;
        
        const pauseIcon = document.getElementById('pause-icon');
        const playIcon = document.getElementById('play-icon');
        
        if (this.isRotationPaused) {
            pauseIcon.style.display = 'none';
            playIcon.style.display = 'block';
            this.stopRotation();
        } else {
            pauseIcon.style.display = 'block';
            playIcon.style.display = 'none';
            this.startRotation();
        }
        
        this.updateRotationStatus();
    }
    
    updateRotationStatus() {
        const statusElement = document.getElementById('rotation-status');
        if (this.isRotationPaused) {
            statusElement.textContent = 'Rotation paused';
        } else if (this.dashboards.length > 1) {
            const interval = this.config?.settings?.rotation_interval || 30;
            statusElement.textContent = `Rotating every ${interval}s`;
        } else {
            statusElement.textContent = 'No rotation (single dashboard)';
        }
    }
    
    refreshCurrent() {
        const container = document.getElementById('dashboard-container');
        const currentIframe = container.querySelector('.dashboard-iframe.active');
        
        if (currentIframe && this.dashboards[this.currentIndex]) {
            const dashboard = this.dashboards[this.currentIndex];
            currentIframe.src = this.buildDashboardUrl(dashboard);
            console.log(`Refreshing dashboard: ${dashboard.name}`);
        }
    }
    
    startAutoRefresh() {
        const interval = (this.config?.settings?.refresh_interval || 300) * 1000;
        
        this.refreshTimer = setInterval(() => {
            this.refreshCurrent();
        }, interval);
        
        console.log(`Auto-refresh enabled: every ${interval / 1000} seconds`);
    }
    
    enterFullscreen() {
        const elem = document.documentElement;
        
        if (elem.requestFullscreen) {
            elem.requestFullscreen();
        } else if (elem.webkitRequestFullscreen) {
            elem.webkitRequestFullscreen();
        } else if (elem.mozRequestFullScreen) {
            elem.mozRequestFullScreen();
        } else if (elem.msRequestFullscreen) {
            elem.msRequestFullscreen();
        }
    }
    
    exitFullscreen() {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        } else if (document.mozCancelFullScreen) {
            document.mozCancelFullScreen();
        } else if (document.msExitFullscreen) {
            document.msExitFullscreen();
        }
    }
    
    toggleFullscreen() {
        if (this.isFullscreen) {
            this.exitFullscreen();
        } else {
            this.enterFullscreen();
        }
    }
    
    handleFullscreenChange() {
        this.isFullscreen = !!(document.fullscreenElement || 
                              document.webkitFullscreenElement || 
                              document.mozFullScreenElement || 
                              document.msFullscreenElement);
        
        document.body.classList.toggle('fullscreen', this.isFullscreen);
        console.log('Fullscreen mode:', this.isFullscreen);
    }
    
    handleKeyboard(event) {
        // Don't handle if user is typing in an input
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
            return;
        }
        
        switch (event.code) {
            case 'ArrowLeft':
                event.preventDefault();
                this.previousDashboard();
                break;
            case 'ArrowRight':
                event.preventDefault();
                this.nextDashboard();
                break;
            case 'Space':
                event.preventDefault();
                this.toggleRotation();
                break;
            case 'KeyR':
                event.preventDefault();
                this.refreshCurrent();
                break;
            case 'KeyF':
                event.preventDefault();
                this.toggleFullscreen();
                break;
            case 'KeyH':
                event.preventDefault();
                this.toggleHelp();
                break;
            case 'KeyN':
                event.preventDefault();
                this.toggleNavigation();
                break;
            case 'KeyC':
                event.preventDefault();
                window.location.href = '/config';
                break;
            case 'Escape':
                event.preventDefault();
                this.hideHelp();
                break;
        }
    }
    
    toggleHelp() {
        const helpOverlay = document.getElementById('help-overlay');
        const isVisible = helpOverlay.style.display !== 'none';
        helpOverlay.style.display = isVisible ? 'none' : 'block';
    }
    
    hideHelp() {
        document.getElementById('help-overlay').style.display = 'none';
    }
    
    toggleNavigation() {
        const nav = document.getElementById('navigation');
        const progress = document.getElementById('progress-container');
        
        const isHidden = nav.classList.contains('hidden');
        nav.classList.toggle('hidden', !isHidden);
        progress.style.display = isHidden ? 'flex' : 'none';
    }
    
    trackActivity() {
        this.lastActivity = Date.now();
    }
    
    updateClock() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        const timeElement = document.getElementById('current-time');
        if (timeElement) {
            timeElement.textContent = timeString;
        }
    }
    
    handleVisibilityChange() {
        if (document.hidden) {
            // Page is hidden, pause timers
            this.stopRotation();
        } else {
            // Page is visible, resume timers
            if (!this.isRotationPaused) {
                this.startRotation();
            }
        }
    }
    
    handleWindowFocus() {
        // Refresh current dashboard when window regains focus
        setTimeout(() => this.refreshCurrent(), 1000);
    }
    
    showError(title, message) {
        const errorState = document.getElementById('error-state');
        const errorTitle = errorState.querySelector('h2');
        const errorMessage = errorState.querySelector('p');
        
        if (errorTitle) errorTitle.textContent = title;
        if (errorMessage) errorMessage.textContent = message;
        
        errorState.style.display = 'block';
        document.getElementById('loading').style.display = 'none';
    }
    
    showNetworkError(message, url) {
        const networkError = document.getElementById('network-error');
        const messageElement = document.getElementById('network-error-message');
        
        if (messageElement) {
            messageElement.textContent = `${message}\nURL: ${url}`;
        }
        
        networkError.style.display = 'block';
    }
    
    retryConnection() {
        document.getElementById('network-error').style.display = 'none';
        this.refreshCurrent();
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.digitalSignage = new DigitalSignage();
});

// Handle uncaught errors
window.addEventListener('error', (event) => {
    console.error('Application error:', event.error);
});

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
});
