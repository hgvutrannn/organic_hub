/**
 * Discount Calculator
 * Handles discount code loading and calculation logic
 */

const DiscountCalculator = {
    cache: {},
    
    /**
     * Load discount codes for a store
     */
    async loadDiscountCodes(storeId) {
        // Check cache first
        if (this.cache[storeId]) {
            return this.cache[storeId];
        }
        
        try {
            const response = await fetch(`/api/store/${storeId}/discount-codes/`);
            const data = await response.json();
            
            if (data.success) {
                this.cache[storeId] = data.discount_codes;
                return data.discount_codes;
            } else {
                console.error('Error loading discount codes:', data.error);
                return [];
            }
        } catch (error) {
            console.error('Error fetching discount codes:', error);
            return [];
        }
    },
    
    /**
     * Calculate discount amount for a store
     */
    calculateStoreDiscount: function(discount, storeTotal) {
        if (!discount || storeTotal <= 0) return 0;
        
        let discountAmount = 0;
        
        if (discount.discount_type === 'percentage') {
            discountAmount = (storeTotal * discount.discount_value) / 100;
            // Apply max discount if specified (only for percentage type)
            if (discount.max_discount && discountAmount > discount.max_discount) {
                discountAmount = discount.max_discount;
            }
        } else if (discount.discount_type === 'fixed') {
            discountAmount = discount.discount_value;
        }
        
        return discountAmount;
    },
    
    /**
     * Calculate proportional discount for an item
     */
    calculateItemDiscount: function(discount, itemPrice, storeTotal, storeDiscount) {
        if (!discount || storeTotal <= 0) return 0;
        
        const itemRatio = itemPrice / storeTotal;
        return storeDiscount * itemRatio;
    },
    
    /**
     * Get discount text for display
     */
    getDiscountText: function(discount) {
        if (!discount) return '';
        
        let text = discount.code || '';
        if (discount.discount_type === 'percentage') {
            text += ` - Discount ${discount.discount_value}%`;
        } else if (discount.discount_type === 'fixed') {
            text += ` - Discount ${discount.discount_value.toLocaleString('en-GB', { style: 'currency', currency: 'GBP' })}`;
        }
        
        return text;
    }
};

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DiscountCalculator;
}
