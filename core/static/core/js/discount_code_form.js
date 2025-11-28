/**
 * Discount Code Form JavaScript
 * Handles discount code form functionality including product selection
 */

let selectedProductIds = new Set();

// Initialize selected products from Django template
function initializeSelectedProducts(productIds) {
    if (productIds && productIds.length > 0) {
        selectedProductIds = new Set(productIds);
    }
}

// Handle discount type change
function setupDiscountTypeHandler() {
    const discountTypeSelect = document.getElementById('discountType');
    if (!discountTypeSelect) return;

    discountTypeSelect.addEventListener('change', function() {
        const unit = this.value === 'percentage' ? '%' : 'GBP';
        const unitElement = document.getElementById('discountUnit');
        const maxDiscountContainer = document.getElementById('maxDiscountContainer');
        
        if (unitElement) {
            unitElement.textContent = unit;
        }
        if (maxDiscountContainer) {
            maxDiscountContainer.style.display = this.value === 'percentage' ? 'block' : 'none';
        }
    });
}

function openProductSelector() {
    loadProducts();
    const modalElement = document.getElementById('productSelectorModal');
    if (modalElement) {
        const modal = new bootstrap.Modal(modalElement);
        modal.show();
    }
}

function loadProducts(search = '') {
    const url = window.storeProductsAjaxUrl || `/store/${window.storeId}/products/ajax/`;
    const fullUrl = `${url}?search=${encodeURIComponent(search)}`;
    
    fetch(fullUrl)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayProducts(data.products);
            }
        })
        .catch(error => {
            console.error('Error loading products:', error);
        });
}

function displayProducts(products) {
    const grid = document.getElementById('products-grid');
    if (!grid) return;

    grid.innerHTML = '';
    
    products.forEach(product => {
        const isSelected = selectedProductIds.has(product.product_id);
        const productCard = `
            <div class="col-md-3">
                <div class="card border ${isSelected ? 'border-primary' : ''} product-select-card" 
                     data-product-id="${product.product_id}"
                     onclick="toggleProductCardSelection(${product.product_id})"
                     style="cursor: pointer;">
                    <div class="card-body p-2">
                        <div class="position-relative">
                            ${product.image_url ? 
                                `<img src="${product.image_url}" class="card-img-top square-image" style="width: 100%; height: 120px; object-fit: cover;">` :
                                `<div class="bg-light d-flex align-items-center justify-content-center" style="height: 120px;">
                                    <i class="fas fa-image fa-2x text-muted"></i>
                                </div>`
                            }
                            ${isSelected ? 
                                `<div class="position-absolute top-0 end-0 m-2">
                                    <span class="badge bg-primary"><i class="fas fa-check"></i></span>
                                </div>` : ''
                            }
                        </div>
                        <h6 class="card-title mt-2 small">${escapeHtml(product.name)}</h6>
                        <p class="card-text small text-primary mb-0">${product.price.toLocaleString('vi-VN')} VNĐ</p>
                    </div>
                </div>
            </div>
        `;
        grid.innerHTML += productCard;
    });
}

function toggleProductCardSelection(productId) {
    if (selectedProductIds.has(productId)) {
        selectedProductIds.delete(productId);
    } else {
        selectedProductIds.add(productId);
    }
    const searchInput = document.getElementById('productSearchInput');
    const searchValue = searchInput ? searchInput.value : '';
    loadProducts(searchValue);
}

function confirmProductSelection() {
    const selectedList = document.getElementById('selected-products-list');
    if (!selectedList) return;

    const existingIds = new Set();
    
    // Get existing product IDs
    document.querySelectorAll('.selected-product-item').forEach(item => {
        const pid = item.getAttribute('data-product-id');
        if (pid) {
            existingIds.add(parseInt(pid));
        }
    });
    
    // Add new products
    selectedProductIds.forEach(productId => {
        if (!existingIds.has(productId)) {
            // Fetch product details and add to form
            const url = window.storeProductsAjaxUrl || `/store/${window.storeId}/products/ajax/`;
            fetch(`${url}?search=`)
                .then(response => response.json())
                .then(data => {
                    const product = data.products.find(p => p.product_id === productId);
                    if (product) {
                        addProductToForm(product);
                    }
                });
        }
    });
    
    // Close modal
    const modalElement = document.getElementById('productSelectorModal');
    if (modalElement) {
        const modal = bootstrap.Modal.getInstance(modalElement);
        if (modal) {
            modal.hide();
        }
    }
}

function addProductToForm(product) {
    const selectedList = document.getElementById('selected-products-list');
    if (!selectedList) return;
    
    // Remove empty message if exists
    const emptyMsg = selectedList.querySelector('.text-center');
    if (emptyMsg) {
        emptyMsg.remove();
    }
    
    const productItem = `
        <div class="border rounded-3 p-3 mb-3 selected-product-item" data-product-id="${product.product_id}">
            <div class="row align-items-center">
                <div class="col-md-1">
                    ${product.image_url ? 
                        `<img src="${product.image_url}" alt="${escapeHtml(product.name)}" class="img-fluid rounded square-image" style="width: 60px; height: 60px; object-fit: cover;">` :
                        `<div class="bg-light rounded d-flex align-items-center justify-content-center" style="width: 60px; height: 60px;">
                            <i class="fas fa-image text-muted"></i>
                        </div>`
                    }
                </div>
                <div class="col-md-10">
                    <strong>${escapeHtml(product.name)}</strong>
                    <br><small class="text-muted">Giá: ${product.price.toLocaleString('vi-VN')} VNĐ</small>
                </div>
                <div class="col-md-1 text-end">
                    <button type="button" class="btn btn-sm btn-outline-danger" 
                            onclick="removeProduct(${product.product_id})">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            <input type="hidden" name="products" value="${product.product_id}">
        </div>
    `;
    selectedList.innerHTML += productItem;
}

function removeProduct(productId) {
    selectedProductIds.delete(productId);
    const item = document.querySelector(`.selected-product-item[data-product-id="${productId}"]`);
    if (item) {
        item.remove();
    }
    
    // Show empty message if no products
    const selectedList = document.getElementById('selected-products-list');
    if (selectedList && selectedList.querySelectorAll('.selected-product-item').length === 0) {
        selectedList.innerHTML = `
            <div class="text-center py-4 text-muted">
                <i class="fas fa-box fa-2x mb-2"></i>
                <p class="mb-0">Chưa có sản phẩm nào. Nhấn "Thêm sản phẩm" để chọn.</p>
            </div>
        `;
    }
}

function searchProducts() {
    const searchInput = document.getElementById('productSearchInput');
    if (searchInput) {
        const search = searchInput.value;
        loadProducts(search);
    }
}

// Escape HTML helper
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    setupDiscountTypeHandler();
    
    // Initialize max discount container visibility based on current discount type
    const discountTypeSelect = document.getElementById('discountType');
    const maxDiscountContainer = document.getElementById('maxDiscountContainer');
    if (discountTypeSelect && maxDiscountContainer) {
        maxDiscountContainer.style.display = discountTypeSelect.value === 'percentage' ? 'block' : 'none';
    }
    
    // Auto-uppercase code input
    const codeInput = document.querySelector('input[name="code"]');
    if (codeInput) {
        codeInput.addEventListener('input', function() {
            this.value = this.value.toUpperCase();
        });
    }
});

// Make functions globally available
window.toggleProductCardSelection = toggleProductCardSelection; // For product card selection
window.openProductSelector = openProductSelector;
window.confirmProductSelection = confirmProductSelection;
window.removeProduct = removeProduct;
window.searchProducts = searchProducts;
window.initializeSelectedProducts = initializeSelectedProducts;

