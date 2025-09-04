// Coffee Redis Management System - Core JavaScript utilities

// Global configuration
window.CoffeeRedisConfig = {
    apiBase: '/api/v1',
    refreshInterval: 30000, // 30 seconds
    defaultPageSize: 20
};

// API utility functions
class CoffeeAPI {
    static async request(endpoint, options = {}) {
        const url = `${window.CoffeeRedisConfig.apiBase}${endpoint}`;
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin'
        };
        
        const config = { ...defaultOptions, ...options };
        
        try {
            const response = await fetch(url, config);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error?.message || 'API request failed');
            }
            
            return data;
        } catch (error) {
            console.error('API request failed:', error);
            showToast('Error: ' + error.message, 'error');
            throw error;
        }
    }
    
    static async get(endpoint, params = {}) {
        const query = new URLSearchParams(params).toString();
        const url = query ? `${endpoint}?${query}` : endpoint;
        return this.request(url);
    }
    
    static async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    static async put(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }
    
    static async delete(endpoint) {
        return this.request(endpoint, {
            method: 'DELETE'
        });
    }
}

// UI utility functions
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container') || createToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} alert-dismissible fade show`;
    toast.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    toastContainer.appendChild(toast);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 5000);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'position-fixed top-0 end-0 p-3';
    container.style.zIndex = '9999';
    document.body.appendChild(container);
    return container;
}

function showLoading(element, show = true) {
    if (show) {
        element.innerHTML = `
            <div class="spinner-container">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        `;
    } else {
        // This should be handled by the calling function to restore content
    }
}

function formatTimestamp(timestamp, includeTime = true) {
    const date = new Date(timestamp * 1000);
    const options = {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    };
    
    if (includeTime) {
        options.hour = '2-digit';
        options.minute = '2-digit';
    }
    
    return date.toLocaleString('zh-CN', options);
}

function formatCurrency(cents) {
    return `¥${(cents / 100).toFixed(2)}`;
}

function formatBytes(bytes) {
    const sizes = ['B', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 B';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
}

function formatDuration(seconds) {
    if (seconds < 60) return `${seconds}秒`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟`;
    return `${Math.floor(seconds / 3600)}小时`;
}

function getStatusBadge(status) {
    const statusMap = {
        'online': { class: 'status-online', text: '在线' },
        'offline': { class: 'status-offline', text: '离线' },
        'maintenance': { class: 'status-maintenance', text: '维护' },
        'error': { class: 'status-error', text: '故障' }
    };
    
    const config = statusMap[status] || { class: 'status-offline', text: status };
    return `<span class="status-badge ${config.class}">${config.text}</span>`;
}

function getLastSeenText(lastSeenTs) {
    const now = Math.floor(Date.now() / 1000);
    const diff = now - lastSeenTs;
    
    let text, className;
    if (diff < 300) { // 5 minutes
        text = '刚刚';
        className = 'recent';
    } else if (diff < 3600) { // 1 hour
        text = `${Math.floor(diff / 60)}分钟前`;
        className = 'recent';
    } else if (diff < 86400) { // 24 hours
        text = `${Math.floor(diff / 3600)}小时前`;
        className = 'old';
    } else {
        text = `${Math.floor(diff / 86400)}天前`;
        className = 'old';
    }
    
    return `<span class="last-seen ${className}">${text}</span>`;
}

// Table utility functions
function createDataTable(tableId, data, columns, options = {}) {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    // Clear existing content
    table.innerHTML = '';
    
    // Create header
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    
    columns.forEach(col => {
        const th = document.createElement('th');
        th.textContent = col.title;
        if (col.width) th.style.width = col.width;
        headerRow.appendChild(th);
    });
    
    thead.appendChild(headerRow);
    table.appendChild(thead);
    
    // Create body
    const tbody = document.createElement('tbody');
    
    if (data.length === 0) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = columns.length;
        cell.className = 'text-center text-muted py-4';
        cell.textContent = options.emptyText || '暂无数据';
        row.appendChild(cell);
        tbody.appendChild(row);
    } else {
        data.forEach(item => {
            const row = document.createElement('tr');
            
            columns.forEach(col => {
                const td = document.createElement('td');
                
                if (col.render) {
                    td.innerHTML = col.render(item[col.field], item);
                } else {
                    td.textContent = item[col.field] || '-';
                }
                
                if (col.className) {
                    td.className = col.className;
                }
                
                row.appendChild(td);
            });
            
            tbody.appendChild(row);
        });
    }
    
    table.appendChild(tbody);
    
    // Add table classes
    table.className = 'table table-hover';
}

// Form utility functions
function serializeForm(formElement) {
    const formData = new FormData(formElement);
    const data = {};
    
    for (let [key, value] of formData.entries()) {
        data[key] = value;
    }
    
    return data;
}

function resetForm(formElement) {
    formElement.reset();
    
    // Clear validation states
    const fields = formElement.querySelectorAll('.form-control');
    fields.forEach(field => {
        field.classList.remove('is-valid', 'is-invalid');
    });
    
    const feedback = formElement.querySelectorAll('.invalid-feedback, .valid-feedback');
    feedback.forEach(el => el.remove());
}

function showFieldError(fieldElement, message) {
    fieldElement.classList.add('is-invalid');
    
    // Remove existing feedback
    const existingFeedback = fieldElement.parentNode.querySelector('.invalid-feedback');
    if (existingFeedback) {
        existingFeedback.remove();
    }
    
    // Add new feedback
    const feedback = document.createElement('div');
    feedback.className = 'invalid-feedback';
    feedback.textContent = message;
    fieldElement.parentNode.appendChild(feedback);
}

// Modal utility functions
function showModal(modalId) {
    const modal = new bootstrap.Modal(document.getElementById(modalId));
    modal.show();
    return modal;
}

// Auto-refresh functionality
let refreshInterval = null;

function startAutoRefresh(callback, interval = window.CoffeeRedisConfig.refreshInterval) {
    stopAutoRefresh();
    refreshInterval = setInterval(callback, interval);
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// Page visibility handling for auto-refresh
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        stopAutoRefresh();
    } else if (typeof window.currentPageRefresh === 'function') {
        window.currentPageRefresh();
        startAutoRefresh(window.currentPageRefresh);
    }
});

// Chart utility functions
function createChart(canvasId, type, data, options = {}) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    
    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: true,
                position: 'top'
            }
        }
    };
    
    return new Chart(ctx, {
        type: type,
        data: data,
        options: { ...defaultOptions, ...options }
    });
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Set active nav link based on current path
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.sidebar .nav-link');
    
    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (href && currentPath.startsWith(href) && href !== '/') {
            link.classList.add('active');
        } else if (href === '/' && currentPath === '/dashboard') {
            link.classList.add('active');
        }
    });
});

// Export global utilities
window.CoffeeAPI = CoffeeAPI;
window.CoffeeUI = {
    showToast,
    showLoading,
    formatTimestamp,
    formatCurrency,
    formatBytes,
    formatDuration,
    getStatusBadge,
    getLastSeenText,
    createDataTable,
    serializeForm,
    resetForm,
    showFieldError,
    showModal,
    startAutoRefresh,
    stopAutoRefresh,
    createChart
};