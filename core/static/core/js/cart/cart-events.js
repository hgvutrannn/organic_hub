/**
 * Cart Event Handlers
 * Manages all event delegation and user interactions
 */

const CartEvents = {
    /**
     * Setup all event listeners
     */
    init: function(cartManager) {
        this.cart = cartManager;
        this.setupClickHandlers();
        this.setupChangeHandlers();
        this.setupGlobalHandlers();
    },
    
    /**
     * Setup click event handlers
     */
    setupClickHandlers: function() {
        document.addEventListener('click', (e) => {
            this.handleQuantityButtons(e);
            this.handleRemoveItem(e);
            this.handleShowVouchers(e);
        });
    },
    
    /**
     * Handle quantity increase/decrease buttons
     */
    handleQuantityButtons: function(e) {
        const isDecrease = e.target.classList.contains('quantity-decrease');
        const isIncrease = e.target.classList.contains('quantity-increase');
        
        if (isDecrease || isIncrease) {
            const itemId = CartUtils.parseInt(e.target.dataset.itemId);
            const change = CartUtils.parseInt(e.target.dataset.change);
            this.cart.updateQuantity(itemId, change);
        }
    },
    
    /**
     * Handle remove item button
     */
    handleRemoveItem: function(e) {
        const btn = e.target.closest(CartUtils.SELECTORS.REMOVE_ITEM_BTN);
        if (btn) {
            const itemId = CartUtils.parseInt(btn.dataset.itemId);
            this.cart.removeItem(itemId);
        }
    },
    
    /**
     * Handle show vouchers button
     */
    handleShowVouchers: function(e) {
        const btn = e.target.closest(CartUtils.SELECTORS.SHOW_VOUCHERS_BTN);
        if (btn) {
            const storeId = CartUtils.parseInt(btn.dataset.storeId);
            this.cart.showShopVouchers(storeId);
        }
    },
    
    /**
     * Setup change event handlers
     */
    setupChangeHandlers: function() {
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('quantity-input')) {
                const itemId = CartUtils.parseInt(e.target.dataset.itemId);
                const value = CartUtils.parseInt(e.target.value);
                if (CartUtils.validateQuantity(value)) {
                    this.cart.updateQuantityInput(itemId, value);
                }
            }
        });
    },
    
    /**
     * Setup global handlers (checkboxes, etc.)
     */
    setupGlobalHandlers: function() {
        // Store checkbox handlers are in template with onclick
        // This can be refactored later if needed
    }
};

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CartEvents;
}
