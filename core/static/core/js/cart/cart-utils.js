/**
 * Cart Utility Functions
 * Contains constants, selectors, and helper functions
 */

const CartUtils = {
    // Constants
    CONSTANTS: {
        MIN_QUANTITY: 1,
        MAX_QUANTITY: 99,
        CURRENCY: 'GBP',
        LOCALE: 'en-GB'
    },
    
    // CSS Selectors
    SELECTORS: {
        QUANTITY_DECREASE: '.quantity-decrease',
        QUANTITY_INCREASE: '.quantity-increase',
        QUANTITY_INPUT: '.quantity-input',
        REMOVE_ITEM_BTN: '.remove-item-btn',
        SHOW_VOUCHERS_BTN: '.show-vouchers-btn',
        ITEM_CHECKBOX: '.item-checkbox',
        STORE_CHECKBOX: '.store-checkbox',
        STORE_SECTION: '.store-section',
        PRODUCT_ITEM: '.product-item'
    },
    
    // API Endpoints
    ENDPOINTS: {
        UPDATE_CART: (itemId) => `/update-cart/${itemId}/`,
        REMOVE_FROM_CART: (itemId) => `/remove-from-cart/${itemId}/`,
        DISCOUNT_CODES: (storeId) => `/api/store/${storeId}/discount-codes/`
    },
    
    // Currency formatter
    formatCurrency: function(amount) {
        return new Intl.NumberFormat(this.CONSTANTS.LOCALE, {
            style: 'currency',
            currency: this.CONSTANTS.CURRENCY
        }).format(amount);
    },
    
    // DOM helpers
    getElement: function(id) {
        return document.getElementById(id);
    },
    
    querySelector: function(selector) {
        return document.querySelector(selector);
    },
    
    querySelectorAll: function(selector) {
        return document.querySelectorAll(selector);
    },
    
    // Storage helpers
    getAppliedDiscounts: function() {
        try {
            return JSON.parse(sessionStorage.getItem('appliedDiscounts') || '{}');
        } catch (e) {
            console.error('Error parsing applied discounts:', e);
            return {};
        }
    },
    
    setAppliedDiscounts: function(discounts) {
        try {
            sessionStorage.setItem('appliedDiscounts', JSON.stringify(discounts));
        } catch (e) {
            console.error('Error saving applied discounts:', e);
        }
    },
    
    // Validation
    validateQuantity: function(value) {
        const num = parseInt(value);
        return num >= this.CONSTANTS.MIN_QUANTITY && num <= this.CONSTANTS.MAX_QUANTITY;
    },
    
    // Parse float helper
    parseFloat: function(value, defaultValue = 0) {
        const parsed = parseFloat(value);
        return isNaN(parsed) ? defaultValue : parsed;
    },
    
    // Parse int helper
    parseInt: function(value, defaultValue = 0) {
        const parsed = parseInt(value);
        return isNaN(parsed) ? defaultValue : parsed;
    }
};

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CartUtils;
}
