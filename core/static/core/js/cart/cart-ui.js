/**
 * Cart UI Manager
 * Handles all UI updates and display logic
 */

const CartUI = {
    /**
     * Update total display in footer
     */
    updateTotalDisplay: function(total, discount, count) {
        CartUtils.getElement('selectedCount').innerText = count;
        CartUtils.getElement('totalItems').innerText = count;
        
        const originalTotalEl = CartUtils.getElement('originalTotalAmount');
        const discountInfoEl = CartUtils.getElement('discountInfo');
        const discountAmountEl = CartUtils.getElement('discountAmount');
        const totalAmountEl = CartUtils.getElement('totalAmount');
        
        if (discount > 0) {
            originalTotalEl.textContent = CartUtils.formatCurrency(total);
            originalTotalEl.style.display = 'block';
            discountAmountEl.textContent = CartUtils.formatCurrency(discount);
            discountInfoEl.style.display = 'block';
            totalAmountEl.textContent = CartUtils.formatCurrency(total - discount);
        } else {
            originalTotalEl.style.display = 'none';
            discountInfoEl.style.display = 'none';
            totalAmountEl.textContent = CartUtils.formatCurrency(total);
        }
        
        const buyBtn = CartUtils.getElement('buyButton');
        if (buyBtn) buyBtn.disabled = count === 0;
    },
    
    /**
     * Update individual item price display
     */
    updateItemPriceDisplay: function(itemRow, originalPrice, finalPrice, showDiscount) {
        const amountDisplay = itemRow.querySelector('.amount-display');
        const originalPriceDiv = amountDisplay.querySelector('.original-item-price');
        const discountedPriceDiv = amountDisplay.querySelector('.discounted-item-price');
        
        if (showDiscount && finalPrice < originalPrice) {
            originalPriceDiv.style.display = 'none';
            discountedPriceDiv.querySelector('.original-price-display').textContent = 
                CartUtils.formatCurrency(originalPrice);
            discountedPriceDiv.querySelector('.final-price-display').textContent = 
                CartUtils.formatCurrency(finalPrice);
            discountedPriceDiv.style.display = 'block';
        } else {
            originalPriceDiv.style.display = 'block';
            discountedPriceDiv.style.display = 'none';
        }
    },
    
    /**
     * Show applied discount for a store
     */
    showAppliedDiscount: function(storeId, discountText) {
        const appliedDiv = CartUtils.getElement(`applied-discount-${storeId}`);
        const appliedText = CartUtils.getElement(`applied-discount-text-${storeId}`);
        
        if (appliedDiv && appliedText) {
            appliedText.textContent = discountText;
            appliedDiv.style.display = 'block';
        }
    },
    
    /**
     * Update hidden field with applied discounts
     */
    syncDiscountField: function(discounts) {
        const hiddenField = CartUtils.getElement('appliedDiscountsField');
        if (hiddenField) {
            hiddenField.value = JSON.stringify(discounts);
        }
    }
};

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CartUI;
}
