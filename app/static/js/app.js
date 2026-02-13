// CooperApp - Main JavaScript

// Notification system
const notifications = {
    container: null,

    init() {
        this.container = document.getElementById('notifications');
    },

    show(message, type = 'info', duration = 3000) {
        if (!this.container) this.init();

        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;

        this.container.appendChild(notification);

        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(1rem)';
            setTimeout(() => notification.remove(), 300);
        }, duration);
    },

    success(message) {
        this.show(message, 'success');
    },

    error(message) {
        this.show(message, 'error');
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    notifications.init();
});

// htmx event handlers
document.body.addEventListener('htmx:afterSwap', (event) => {
    // Handle successful operations
    if (event.detail.xhr.status === 200) {
        const target = event.detail.target;

        // Handle delete success
        if (event.detail.requestConfig.verb === 'delete') {
            notifications.success('Proyecto eliminado correctamente');
        }
    }
});

document.body.addEventListener('htmx:responseError', (event) => {
    const status = event.detail.xhr.status;
    let message = 'Ha ocurrido un error';

    // Try to get the error message from the response
    try {
        const response = JSON.parse(event.detail.xhr.responseText);
        if (response.detail) {
            message = response.detail;
        }
    } catch (e) {
        // If parsing fails, use default messages
        if (status === 404) {
            message = 'Recurso no encontrado';
        } else if (status === 400) {
            message = 'Datos invalidos';
        } else if (status === 500) {
            message = 'Error del servidor';
        }
    }

    notifications.error(message);
});

// Format currency helper
function formatCurrency(amount) {
    return new Intl.NumberFormat('es-ES', {
        style: 'currency',
        currency: 'EUR'
    }).format(amount);
}

// Format date helper
function formatDate(dateString) {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('es-ES', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    }).format(date);
}

// Debounce helper
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Confirmation dialog
function confirmDelete(message) {
    return confirm(message || '¿Estás seguro de que quieres eliminar este elemento?');
}

// Export for global use
window.CooperApp = {
    notifications,
    formatCurrency,
    formatDate,
    debounce,
    confirmDelete
};
