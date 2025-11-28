/**
 * Product Detail Page JavaScript
 * Handles product gallery, variant selection, and add to cart functionality
 */

// Send product message to chat
function sendProductMessage(productName, storeOwnerId) {
    // Lưu thông tin sản phẩm vào localStorage để sử dụng trong chat
    console.log('Saving to localStorage:', productName, storeOwnerId);
    localStorage.setItem('productName', productName);
    localStorage.setItem('storeOwnerId', storeOwnerId);
    console.log('Saved to localStorage');
}

// Handle add to cart form submission
document.addEventListener('DOMContentLoaded', function() {
    const addToCartForm = document.getElementById('add-to-cart-form');
    const cartToast = document.getElementById('cart-toast');
    const toastMessage = document.getElementById('toast-message');
    
    if (!addToCartForm || !cartToast || !toastMessage) return;
    
    const toastHeader = cartToast.querySelector('.toast-header');
    const toastIcon = toastHeader.querySelector('i');
    
    addToCartForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Get form data
        const formData = new FormData(addToCartForm);
        
        // Send AJAX request
        fetch(addToCartForm.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => {
            if (response.ok) {
                // Success - show green toast
                toastIcon.className = 'fas fa-check-circle me-2 text-success';
                toastHeader.className = 'toast-header';
                toastMessage.textContent = 'Product added to cart successfully!';
            } else {
                // Error - show red toast
                toastIcon.className = 'fas fa-exclamation-triangle me-2 text-danger';
                toastHeader.className = 'toast-header bg-danger text-white';
                toastMessage.textContent = 'Error adding product to cart.';
            }
            
            // Show toast
            const toast = new bootstrap.Toast(cartToast);
            toast.show();
        })
        .catch(error => {
            console.error('Error:', error);
            // Show error toast
            toastIcon.className = 'fas fa-exclamation-triangle me-2 text-danger';
            toastHeader.className = 'toast-header bg-danger text-white';
            toastMessage.textContent = 'Có lỗi xảy ra khi thêm sản phẩm vào giỏ hàng.';
            
            const toast = new bootstrap.Toast(cartToast);
            toast.show();
        });
    });
});

// Image Gallery Functionality
function changeMainImage(imageUrl, imageNumber, variantId = null) {
    const mainImage = document.getElementById('main-image');
    const currentImageSpan = document.getElementById('current-image');
    
    if (!mainImage) return;
    
    // Update main image
    mainImage.src = imageUrl;
    
    // Update current image counter
    if (currentImageSpan) {
        currentImageSpan.textContent = imageNumber;
    }
    
    // Update thumbnail active state
    document.querySelectorAll('.thumbnail-img').forEach(img => {
        img.classList.remove('active');
    });
    
    // Add active class to clicked thumbnail
    if (event && event.target) {
        event.target.classList.add('active');
    } else {
        // Fallback: tìm thumbnail theo imageNumber
        const thumbnail = document.querySelector(`.thumbnail-img[data-image-index="${imageNumber}"]`);
        if (thumbnail) {
            thumbnail.classList.add('active');
        }
    }
    
    // Nếu click vào hình variant, tự động chọn variant đó
    if (variantId) {
        const variantBtn = document.querySelector(`.variant-btn[data-variant-id="${variantId}"]`);
        if (variantBtn) {
            handleVariantSelection(variantBtn);
            // Scroll đến variant selector nếu cần
            setTimeout(() => {
                variantBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 100);
        }
    }
}

// Variant Selection Handler
function handleVariantSelection(variantBtn) {
    const variantId = variantBtn.getAttribute('data-variant-id');
    const variantPrice = variantBtn.getAttribute('data-variant-price');
    const variantImage = variantBtn.getAttribute('data-variant-image');
    const variantStock = parseInt(variantBtn.getAttribute('data-variant-stock'));
    
    // Update selected variant ID
    const selectedVariantId = document.getElementById('selected-variant-id');
    const formVariantId = document.getElementById('form-variant-id');
    if (selectedVariantId) selectedVariantId.value = variantId;
    if (formVariantId) formVariantId.value = variantId;
    
    // Update price
    const priceElement = document.getElementById('product-price');
    if (priceElement) {
        priceElement.textContent = '£' + parseFloat(variantPrice).toFixed(2);
    }
    
    // Update main image if variant has its own image
    if (variantImage) {
        const mainImage = document.getElementById('main-image');
        if (mainImage) {
            mainImage.src = variantImage;
            // Tìm và highlight thumbnail tương ứng
            const variantThumbnail = document.querySelector(`.thumbnail-img[data-variant-id="${variantId}"]`);
            if (variantThumbnail) {
                // Update image counter
                const imageIndex = variantThumbnail.getAttribute('data-image-index');
                const currentImageSpan = document.getElementById('current-image');
                if (currentImageSpan) {
                    currentImageSpan.textContent = imageIndex;
                }
                // Update active thumbnail
                document.querySelectorAll('.thumbnail-img').forEach(img => {
                    img.classList.remove('active');
                });
                variantThumbnail.classList.add('active');
            }
        }
    }
    
    // Update stock message
    const stockMessage = document.getElementById('stock-message');
    const quantityInput = document.getElementById('quantity-input');
    const addToCartBtn = document.getElementById('add-to-cart-btn');
    
    if (stockMessage && quantityInput && addToCartBtn) {
        if (variantStock <= 0) {
            stockMessage.innerHTML = '<span class="text-danger"><i class="fas fa-exclamation-circle"></i> Out of Stock</span>';
            quantityInput.disabled = true;
            addToCartBtn.disabled = true;
            addToCartBtn.classList.add('disabled');
        } else {
            if (variantStock < 10) {
                stockMessage.innerHTML = `<span class="text-warning"><i class="fas fa-info-circle"></i> ${variantStock} left</span>`;
            } else {
                stockMessage.innerHTML = '<span class="text-success"><i class="fas fa-check-circle"></i> In Stock</span>';
            }
            quantityInput.disabled = false;
            quantityInput.max = variantStock;
            addToCartBtn.disabled = false;
            addToCartBtn.classList.remove('disabled');
        }
    }
    
    // Update active state
    document.querySelectorAll('.variant-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    variantBtn.classList.add('active');
}

// Add hover effects to thumbnails and handle variant selection
document.addEventListener('DOMContentLoaded', function() {
    const thumbnails = document.querySelectorAll('.thumbnail-img');
    thumbnails.forEach(thumbnail => {
        thumbnail.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.05)';
            this.style.transition = 'transform 0.2s ease';
        });
        
        thumbnail.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
        });
    });
    
    // Handle variant selection
    const variantButtons = document.querySelectorAll('.variant-btn');
    variantButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            handleVariantSelection(this);
            // Khi chọn variant, cập nhật hình ảnh chính nếu variant có hình riêng
            const variantImage = this.getAttribute('data-variant-image');
            const variantId = this.getAttribute('data-variant-id');
            if (variantImage && variantId) {
                const variantThumbnail = document.querySelector(`.thumbnail-img[data-variant-id="${variantId}"]`);
                if (variantThumbnail) {
                    const imageIndex = variantThumbnail.getAttribute('data-image-index');
                    changeMainImage(variantImage, imageIndex);
                }
            }
        });
    });
    
    // Initialize stock message for default variant
    const defaultBtn = document.querySelector('.variant-btn.active');
    if (defaultBtn) {
        handleVariantSelection(defaultBtn);
    }
});

// Make functions globally available
window.sendProductMessage = sendProductMessage;
window.changeMainImage = changeMainImage;
window.handleVariantSelection = handleVariantSelection;

