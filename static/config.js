/**
 * Digital Signage Platform - Configuration Interface
 * Manages dashboard configuration and settings
 */

class ConfigurationManager {
    constructor() {
        this.config = null;
        this.dashboardCounter = 0;
        
        this.init();
    }
    
    async init() {
        console.log('Initializing Configuration Manager...');
        
        // Load current configuration
        await this.loadConfig();
        
        // Setup UI
        this.setupUI();
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Populate form with current config
        this.populateForm();
        
        console.log('Configuration Manager initialized');
    }
    
    async loadConfig() {
        try {
            const response = await fetch('/api/config');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.config = await response.json();
            console.log('Configuration loaded:', this.config);
            
        } catch (error) {
            console.error('Failed to load configuration:', error);
            this.showStatus('error', `Failed to load configuration: ${error.message}`);
            
            // Use default configuration
            this.config = this.getDefaultConfig();
        }
    }
    
    getDefaultConfig() {
        return {
            dashboards: [],
            settings: {
                rotation_interval: 30,
                auto_refresh: true,
                refresh_interval: 300,
                fullscreen: true,
                show_navigation: true,
                enable_keyboard_shortcuts: true
            }
        };
    }
    
    setupUI() {
        // Update system info
        this.updateSystemInfo();
    }
    
    setupEventListeners() {
        // Save configuration button
        document.getElementById('save-config').addEventListener('click', () => this.saveConfig());
        
        // Add dashboard button
        document.getElementById('add-dashboard').addEventListener('click', () => this.addDashboard());
        
        // Form validation on input
        document.addEventListener('input', (e) => this.validateField(e.target));
        
        // Test connection buttons (delegated event handling)
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('btn-test')) {
                this.testDashboardConnection(e.target);
            } else if (e.target.classList.contains('btn-remove')) {
                this.removeDashboard(e.target);
            }
        });
    }
    
    populateForm() {
        // Clear existing dashboards
        const container = document.getElementById('dashboards-container');
        container.innerHTML = '';
        
        // Add dashboard entries
        this.config.dashboards.forEach(dashboard => {
            this.addDashboard(dashboard);
        });
        
        // If no dashboards, add one empty one
        if (this.config.dashboards.length === 0) {
            this.addDashboard();
        }
        
        // Populate settings
        const settings = this.config.settings || {};
        document.getElementById('rotation-interval').value = settings.rotation_interval || 30;
        document.getElementById('refresh-interval').value = settings.refresh_interval || 300;
        document.getElementById('auto-refresh').checked = settings.auto_refresh !== false;
        document.getElementById('fullscreen').checked = settings.fullscreen !== false;
        document.getElementById('show-navigation').checked = settings.show_navigation !== false;
        document.getElementById('enable-keyboard-shortcuts').checked = settings.enable_keyboard_shortcuts !== false;
    }
    
    addDashboard(dashboardData = null) {
        const template = document.getElementById('dashboard-template');
        const clone = template.content.cloneNode(true);
        
        // Set unique identifier
        const dashboardId = `dashboard-${++this.dashboardCounter}`;
        clone.querySelector('.dashboard-entry').setAttribute('data-dashboard-id', dashboardId);
        
        // Populate with data if provided
        if (dashboardData) {
            clone.querySelector('.dashboard-name').value = dashboardData.name || '';
            clone.querySelector('.dashboard-url').value = dashboardData.url || '';
            clone.querySelector('.dashboard-type').value = dashboardData.type || 'uptimekuma';
            clone.querySelector('.dashboard-username').value = dashboardData.username || '';
            clone.querySelector('.dashboard-password').value = dashboardData.password || '';
            clone.querySelector('.dashboard-enabled').checked = dashboardData.enabled !== false;
        } else {
            // Set default values for new dashboard
            clone.querySelector('.dashboard-enabled').checked = true;
        }
        
        // Add to container
        document.getElementById('dashboards-container').appendChild(clone);
        
        console.log('Dashboard entry added:', dashboardId);
    }
    
    removeDashboard(button) {
        const dashboardEntry = button.closest('.dashboard-entry');
        if (dashboardEntry) {
            dashboardEntry.remove();
            console.log('Dashboard entry removed');
        }
    }
    
    async testDashboardConnection(button) {
        const dashboardEntry = button.closest('.dashboard-entry');
        const resultDiv = dashboardEntry.querySelector('.test-result');
        
        // Get form values
        const url = dashboardEntry.querySelector('.dashboard-url').value.trim();
        const username = dashboardEntry.querySelector('.dashboard-username').value.trim();
        const password = dashboardEntry.querySelector('.dashboard-password').value.trim();
        
        if (!url) {
            this.showTestResult(resultDiv, false, 'URL is required');
            return;
        }
        
        // Show loading state
        button.disabled = true;
        button.textContent = 'Testing...';
        this.showTestResult(resultDiv, null, 'Testing connection...');
        
        try {
            // Build query parameters
            const params = new URLSearchParams({ url });
            if (username) params.append('username', username);
            if (password) params.append('password', password);
            
            const response = await fetch(`/api/test-connection?${params.toString()}`);
            const result = await response.json();
            
            if (response.ok) {
                this.showTestResult(resultDiv, result.success, result.message);
            } else {
                this.showTestResult(resultDiv, false, `Server error: ${response.statusText}`);
            }
            
        } catch (error) {
            console.error('Connection test failed:', error);
            this.showTestResult(resultDiv, false, `Test failed: ${error.message}`);
        } finally {
            // Reset button
            button.disabled = false;
            button.textContent = 'Test Connection';
        }
    }
    
    showTestResult(resultDiv, success, message) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'test-result';
        
        if (success === true) {
            resultDiv.classList.add('success');
            resultDiv.textContent = `✓ ${message}`;
        } else if (success === false) {
            resultDiv.classList.add('error');
            resultDiv.textContent = `✗ ${message}`;
        } else {
            resultDiv.textContent = message;
        }
    }
    
    validateField(field) {
        // Remove any existing validation styling
        field.classList.remove('invalid');
        
        // URL validation
        if (field.classList.contains('dashboard-url')) {
            const url = field.value.trim();
            if (url && !this.isValidUrl(url)) {
                field.classList.add('invalid');
                this.showFieldError(field, 'Please enter a valid URL');
                return false;
            } else {
                this.clearFieldError(field);
            }
        }
        
        // Required field validation
        if (field.hasAttribute('required') && !field.value.trim()) {
            field.classList.add('invalid');
            this.showFieldError(field, 'This field is required');
            return false;
        } else {
            this.clearFieldError(field);
        }
        
        return true;
    }
    
    isValidUrl(string) {
        try {
            new URL(string);
            return true;
        } catch {
            return false;
        }
    }
    
    showFieldError(field, message) {
        // Remove existing error
        this.clearFieldError(field);
        
        // Add error message
        const errorElement = document.createElement('small');
        errorElement.className = 'field-error';
        errorElement.style.color = '#fca5a5';
        errorElement.textContent = message;
        
        field.parentNode.appendChild(errorElement);
    }
    
    clearFieldError(field) {
        const existingError = field.parentNode.querySelector('.field-error');
        if (existingError) {
            existingError.remove();
        }
    }
    
    collectFormData() {
        const dashboards = [];
        const dashboardEntries = document.querySelectorAll('.dashboard-entry');
        
        dashboardEntries.forEach(entry => {
            const name = entry.querySelector('.dashboard-name').value.trim();
            const url = entry.querySelector('.dashboard-url').value.trim();
            const type = entry.querySelector('.dashboard-type').value;
            const username = entry.querySelector('.dashboard-username').value.trim();
            const password = entry.querySelector('.dashboard-password').value.trim();
            const enabled = entry.querySelector('.dashboard-enabled').checked;
            
            // Only include if name and URL are provided
            if (name && url) {
                dashboards.push({
                    name,
                    url,
                    type,
                    username,
                    password,
                    enabled
                });
            }
        });
        
        const settings = {
            rotation_interval: parseInt(document.getElementById('rotation-interval').value) || 30,
            refresh_interval: parseInt(document.getElementById('refresh-interval').value) || 300,
            auto_refresh: document.getElementById('auto-refresh').checked,
            fullscreen: document.getElementById('fullscreen').checked,
            show_navigation: document.getElementById('show-navigation').checked,
            enable_keyboard_shortcuts: document.getElementById('enable-keyboard-shortcuts').checked
        };
        
        return { dashboards, settings };
    }
    
    validateForm() {
        let isValid = true;
        
        // Validate all fields
        const fields = document.querySelectorAll('input[required], .dashboard-url');
        fields.forEach(field => {
            if (!this.validateField(field)) {
                isValid = false;
            }
        });
        
        // Check for at least one dashboard
        const formData = this.collectFormData();
        if (formData.dashboards.length === 0) {
            this.showStatus('error', 'Please configure at least one dashboard');
            isValid = false;
        }
        
        return isValid;
    }
    
    async saveConfig() {
        console.log('Saving configuration...');
        
        // Validate form
        if (!this.validateForm()) {
            return;
        }
        
        // Collect form data
        const configData = this.collectFormData();
        
        try {
            // Save to server
            const response = await fetch('/api/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(configData)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            if (result.status === 'success') {
                this.showStatus('success', 'Configuration saved successfully!');
                this.config = configData;
                console.log('Configuration saved:', configData);
            } else {
                throw new Error('Unexpected server response');
            }
            
        } catch (error) {
            console.error('Failed to save configuration:', error);
            this.showStatus('error', `Failed to save configuration: ${error.message}`);
        }
    }
    
    showStatus(type, message) {
        const statusElement = document.getElementById('status-message');
        statusElement.className = `status-message ${type}`;
        statusElement.textContent = message;
        statusElement.style.display = 'block';
        
        // Auto-hide success messages
        if (type === 'success') {
            setTimeout(() => {
                statusElement.style.display = 'none';
            }, 5000);
        }
        
        // Scroll to top to ensure message is visible
        statusElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    
    updateSystemInfo() {
        // Update dashboard URL
        const dashboardUrl = `${window.location.protocol}//${window.location.host}/`;
        document.getElementById('dashboard-url').textContent = dashboardUrl;
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.configManager = new ConfigurationManager();
});

// Handle form submission with Enter key
document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 's') {
        e.preventDefault();
        if (window.configManager) {
            window.configManager.saveConfig();
        }
    }
});

// Handle uncaught errors
window.addEventListener('error', (event) => {
    console.error('Configuration error:', event.error);
});
