/**
 * Admin Base Template JavaScript
 * Handles sidebar submenu toggle functionality
 */

function toggleSubmenu(element) {
    const navItem = element.closest('.nav-item');
    const isExpanded = navItem.classList.contains('expanded');
    
    // Close all other submenus
    document.querySelectorAll('.nav-item.has-submenu').forEach(item => {
        if (item !== navItem) {
            item.classList.remove('expanded');
        }
    });
    
    // Toggle current submenu
    if (isExpanded) {
        navItem.classList.remove('expanded');
    } else {
        navItem.classList.add('expanded');
    }
}

// Auto-expand submenu if current page is in that section
document.addEventListener('DOMContentLoaded', function() {
    const currentUrl = window.location.pathname;
    document.querySelectorAll('.nav-item.has-submenu').forEach(item => {
        const submenuLinks = item.querySelectorAll('.submenu .nav-link');
        submenuLinks.forEach(link => {
            if (currentUrl.includes(link.getAttribute('href'))) {
                item.classList.add('expanded');
            }
        });
    });
});

// Make function globally available
window.toggleSubmenu = toggleSubmenu;

