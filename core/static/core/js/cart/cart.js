/**
 * Main Cart Manager
 * Coordinates all cart functionality
 */

const CartManager = function() {
    // Initialize components
    this.discountCalculator = DiscountCalculator;
    
    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => this.init());
    } else {
        this.init();
    }
};

CartManager.prototype = {
    /**
     * Initialize cart manager
     */
    init: function() {
        this.loadAppliedDiscounts();
        this.updateTotal();
        CartEvents.init(this);
    },
    
    /**
     * Load applied discounts from sessionStorage and update UI
     */
    loadAppliedDiscounts: function() {
        const appliedDiscounts = CartUtils.getAppliedDiscounts();
        
        Object.keys(appliedDiscounts).forEach(storeId => {
            const discount = appliedDiscounts[storeId];
            const discountText = DiscountCalculator.getDiscountText(discount);
            CartUI.showAppliedDiscount(storeId, discountText);
        });
        
        CartUI.syncDiscountField(appliedDiscounts);
    },
    
    /**
     * Update store and master checkboxes state
     */
    updateStoreAndMasterCheckboxes: function() {
        const stores = CartUtils.querySelectorAll(CartUtils.SELECTORS.STORE_SECTION);
        let allItemsChecked = true;
        let hasItems = false;
        
        stores.forEach(store => {
            const items = store.querySelectorAll(CartUtils.SELECTORS.ITEM_CHECKBOX);
            const storeCb = store.querySelector(CartUtils.SELECTORS.STORE_CHECKBOX);
            if (items.length > 0) {
                hasItems = true;
                const allStoreItemsChecked = Array.from(items).every(cb => cb.checked);
                storeCb.checked = allStoreItemsChecked;
                if (!allStoreItemsChecked) allItemsChecked = false;
            }
        });
        
        const selectAllState = hasItems && allItemsChecked;
        const selectAll = CartUtils.getElement('selectAll');
        const selectAllFooter = CartUtils.getElement('selectAllFooter');
        
        if (selectAll) selectAll.checked = selectAllState;
        if (selectAllFooter) selectAllFooter.checked = selectAllState;
    },
    
    /**
     * Calculate store totals for checked items
     */
    calculateStoreTotals: function() {
        const storeTotals = {};
        CartUtils.querySelectorAll(CartUtils.SELECTORS.STORE_SECTION).forEach(storeSection => {
            const storeId = storeSection.dataset.storeId;
            let storeTotal = 0;
            
            storeSection.querySelectorAll(CartUtils.SELECTORS.ITEM_CHECKBOX + ':checked').forEach(cb => {
                const itemRow = cb.closest(CartUtils.SELECTORS.PRODUCT_ITEM);
                const rawPrice = CartUtils.parseFloat(itemRow.querySelector('.amount-raw').innerText);
                storeTotal += rawPrice;
            });
            
            if (storeTotal > 0) {
                storeTotals[storeId] = storeTotal;
            }
        });
        
        return storeTotals;
    },
    
    /**
     * Update individual item prices based on discounts
     */
    updateItemPrices: function() {
        const appliedDiscounts = CartUtils.getAppliedDiscounts();
        const storeTotals = this.calculateStoreTotals();
        
        CartUtils.querySelectorAll(CartUtils.SELECTORS.PRODUCT_ITEM).forEach(itemRow => {
            const storeSection = itemRow.closest(CartUtils.SELECTORS.STORE_SECTION);
            const storeId = storeSection.dataset.storeId;
            const discount = appliedDiscounts[storeId];
            
            const rawPrice = CartUtils.parseFloat(itemRow.querySelector('.amount-raw').innerText);
            const isChecked = itemRow.querySelector(CartUtils.SELECTORS.ITEM_CHECKBOX).checked;
            const storeTotal = storeTotals[storeId] || 0;
            
            if (discount && isChecked && storeTotal > 0) {
                const storeDiscount = DiscountCalculator.calculateStoreDiscount(discount, storeTotal);
                const itemDiscount = DiscountCalculator.calculateItemDiscount(
                    discount, rawPrice, storeTotal, storeDiscount
                );
                const finalPrice = Math.max(0, rawPrice - itemDiscount);
                
                CartUI.updateItemPriceDisplay(itemRow, rawPrice, finalPrice, true);
            } else {
                CartUI.updateItemPriceDisplay(itemRow, rawPrice, rawPrice, false);
            }
        });
    },
    
    /**
     * Update total calculation and display
     */
    updateTotal: function() {
        let total = 0;
        let count = 0;
        let totalDiscount = 0;
        const appliedDiscounts = CartUtils.getAppliedDiscounts();
        const storeOriginalTotals = {};
        
        // Calculate original totals for each store
        CartUtils.querySelectorAll(CartUtils.SELECTORS.STORE_SECTION).forEach(storeSection => {
            const storeId = storeSection.dataset.storeId;
            let storeOriginalTotal = 0;
            
            storeSection.querySelectorAll(CartUtils.SELECTORS.ITEM_CHECKBOX + ':checked').forEach(cb => {
                count++;
                const itemRow = cb.closest(CartUtils.SELECTORS.PRODUCT_ITEM);
                const rawPrice = CartUtils.parseFloat(itemRow.querySelector('.amount-raw').innerText);
                storeOriginalTotal += rawPrice;
                total += rawPrice;
            });
            
            if (storeOriginalTotal > 0) {
                storeOriginalTotals[storeId] = storeOriginalTotal;
            }
        });
        
        // Calculate discount for each store
        Object.keys(storeOriginalTotals).forEach(storeId => {
            const discount = appliedDiscounts[storeId];
            if (discount) {
                const discountAmount = DiscountCalculator.calculateStoreDiscount(
                    discount, 
                    storeOriginalTotals[storeId]
                );
                totalDiscount += discountAmount;
            }
        });
        
        // Update UI
        CartUI.updateTotalDisplay(total, totalDiscount, count);
        this.updateStoreAndMasterCheckboxes();
        this.updateItemPrices();
    },
    
    /**
     * Update quantity for an item
     */
    updateQuantity: function(itemId, change) {
        const input = CartUtils.querySelector(`.quantity-input[data-item-id="${itemId}"]`);
        if (!input) return;
        
        let newVal = CartUtils.parseInt(input.value) + change;
        if (newVal >= CartUtils.CONSTANTS.MIN_QUANTITY && 
            newVal <= CartUtils.CONSTANTS.MAX_QUANTITY) {
            input.value = newVal;
            this.updateQuantityInput(itemId, newVal);
        }
    },
    
    /**
     * Submit quantity update to backend
     */
    updateQuantityInput: function(itemId, val) {
        this.submitHiddenForm(`/update-cart/${itemId}/`, { quantity: val });
    },
    
    /**
     * Remove item from cart
     */
    removeItem: function(itemId) {
        if (confirm('Are you sure you want to remove this product?')) {
            this.submitHiddenForm(`/remove-from-cart/${itemId}/`, {});
        }
    },
    
    /**
     * Delete selected items
     */
    deleteSelected: function() {
        const selected = CartUtils.querySelectorAll(CartUtils.SELECTORS.ITEM_CHECKBOX + ':checked');
        if (selected.length === 0) {
            alert('Please select products to remove');
            return;
        }
        
        if (confirm(`Delete ${selected.length} selected items?`)) {
            // Delete first item to trigger reload (backend should have bulk delete)
            this.removeItem(selected[0].dataset.itemId);
        }
    },
    
    /**
     * Submit hidden form to backend
     */
    submitHiddenForm: function(actionUrl, data) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = actionUrl;
        
        const csrfToken = CartUtils.querySelector('[name=csrfmiddlewaretoken]').value;
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = csrfToken;
        form.appendChild(csrfInput);
        
        for (const [key, value] of Object.entries(data)) {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = key;
            input.value = value;
            form.appendChild(input);
        }
        
        document.body.appendChild(form);
        form.submit();
    },
    
    /**
     * Show shop vouchers modal
     */
    async showShopVouchers(storeId) {
        const modal = new bootstrap.Modal(CartUtils.getElement('discountCodeModal'));
        const listContainer = CartUtils.getElement('discountCodeList');
        
        // Show loading
        listContainer.innerHTML = `
            <div class="text-center py-4">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2 text-muted">Loading discount codes...</p>
            </div>
        `;
        modal.show();
        
        // Load discount codes
        const discountCodes = await DiscountCalculator.loadDiscountCodes(storeId);
        
        // Clear and update content
        listContainer.innerHTML = '';
        
        if (discountCodes.length === 0) {
            listContainer.innerHTML = `
                <div class="text-center py-4 text-muted">
                    <i class="fas fa-ticket-alt fa-3x mb-3 opacity-25"></i>
                    <p>No discount codes available</p>
                </div>
            `;
        } else {
            discountCodes.forEach((discount, index) => {
                const discountItem = document.createElement('div');
                discountItem.className = 'list-group-item';
                discountItem.innerHTML = `
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <div class="d-flex align-items-center mb-2">
                                <span class="badge bg-primary me-2">${discount.code}</span>
                                ${discount.discount_type === 'percentage' 
                                    ? `<span class="badge bg-success">-${discount.discount_value}%</span>` 
                                    : `<span class="badge bg-success">-${discount.discount_value.toLocaleString('en-GB', { style: 'currency', currency: 'GBP' })}</span>`
                                }
                            </div>
                            <p class="mb-1 small text-muted">${discount.description || discount.name}</p>
                        </div>
                        <button class="btn btn-primary btn-sm ms-3 apply-discount-btn" 
                                data-store-id="${storeId}" 
                                data-discount-index="${index}">
                            <i class="fas fa-check me-1"></i>Apply
                        </button>
                    </div>
                `;
                discountItem.dataset.storeId = storeId;
                discountItem.dataset.discountIndex = index;
                listContainer.appendChild(discountItem);
            });
            
            // Store discount codes for apply function
            listContainer.dataset.currentStoreId = storeId;
            listContainer.dataset.discountCodes = JSON.stringify(discountCodes);
            
            // Add event listener for apply buttons
            listContainer.querySelectorAll('.apply-discount-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const storeId = CartUtils.parseInt(btn.dataset.storeId);
                    const index = CartUtils.parseInt(btn.dataset.discountIndex);
                    this.applyDiscountCode(storeId, index);
                });
            });
        }
    },
    
    /**
     * Apply discount code
     */
    applyDiscountCode: function(storeId, discountIndex) {
        const listContainer = CartUtils.getElement('discountCodeList');
        const discountCodes = JSON.parse(listContainer.dataset.discountCodes || '[]');
        const discount = discountCodes[discountIndex];
        
        if (!discount) {
            alert('Invalid discount code');
            return;
        }
        
        // Close modal
        const modal = bootstrap.Modal.getInstance(CartUtils.getElement('discountCodeModal'));
        modal.hide();
        
        // Update UI
        const discountText = DiscountCalculator.getDiscountText(discount);
        CartUI.showAppliedDiscount(storeId, discountText);
        
        // Store in sessionStorage
        const appliedDiscounts = CartUtils.getAppliedDiscounts();
        appliedDiscounts[storeId] = discount;
        CartUtils.setAppliedDiscounts(appliedDiscounts);
        CartUI.syncDiscountField(appliedDiscounts);
        
        // Update totals
        this.updateTotal();
        
        // Show success message
        alert(`Discount code applied: ${discount.code}`);
    }
};

// Global functions for template compatibility
window.toggleSelectAll = function() {
    const isChecked = event.target.checked;
    CartUtils.getElement('selectAll').checked = isChecked;
    const selectAllFooter = CartUtils.getElement('selectAllFooter');
    if (selectAllFooter) selectAllFooter.checked = isChecked;
    
    CartUtils.querySelectorAll(CartUtils.SELECTORS.ITEM_CHECKBOX + ', ' + CartUtils.SELECTORS.STORE_CHECKBOX)
        .forEach(cb => cb.checked = isChecked);
    
    if (window.cartManager) {
        window.cartManager.updateTotal();
    }
};

window.toggleStoreItems = function(storeCb) {
    const storeSection = CartUtils.querySelector(`.store-section[data-store-id="${storeCb.dataset.storeId}"]`);
    storeSection.querySelectorAll(CartUtils.SELECTORS.ITEM_CHECKBOX)
        .forEach(cb => cb.checked = storeCb.checked);
    
    if (window.cartManager) {
        window.cartManager.updateTotal();
    }
};

window.deleteSelected = function() {
    if (window.cartManager) {
        window.cartManager.deleteSelected();
    }
};

// Global function for updateTotal (used in template onchange)
window.updateTotal = function() {
    if (window.cartManager) {
        window.cartManager.updateTotal();
    }
};

// Global function for applyDiscountCode (used in modal buttons)
window.applyDiscountCode = function(storeId, discountIndex) {
    if (window.cartManager) {
        window.cartManager.applyDiscountCode(storeId, discountIndex);
    }
};

// Initialize cart manager
window.cartManager = new CartManager();
