#!/usr/bin/env python
"""
UI Automation Script for Adding Products
Automates product creation through web UI using Selenium
"""
import os
import sys
import time
import argparse
from typing import Dict, List, Any, Optional

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'organic_hub.settings')

try:
    import django
    django.setup()
    from core.models import Category
    DJANGO_AVAILABLE = True
except:
    DJANGO_AVAILABLE = False
    Category = None

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import Select
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Error: selenium is not installed. Please install it with: pip install selenium")
    sys.exit(1)


# Hardcoded login credentials
LOGIN_PHONE = "0902131151"
LOGIN_PASSWORD = "Customer123"


def setup_driver(headless: bool = False):
    """Initialize Chrome WebDriver with options"""
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.maximize_window()
        return driver
    except Exception as e:
        print(f"Error setting up Chrome driver: {str(e)}")
        print("Make sure ChromeDriver is installed and in PATH")
        sys.exit(1)


def wait_for_element(driver, by, value, timeout: int = 10):
    """Utility for waiting elements"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return element
    except TimeoutException:
        return None


def login(driver, base_url: str):
    """Login with hardcoded credentials"""
    print(f"\n{'='*60}")
    print("Logging in...")
    print(f"{'='*60}\n")
    
    try:
        # Navigate to login page
        login_url = f"{base_url}/login/"
        driver.get(login_url)
        time.sleep(2)  # Wait for page to load
        
        # Find and fill phone number field
        phone_input = wait_for_element(driver, By.NAME, "phone_number", timeout=10)
        if not phone_input:
            # Try alternative selectors
            phone_input = driver.find_element(By.ID, "id_phone_number")
        
        phone_input.clear()
        phone_input.send_keys(LOGIN_PHONE)
        print(f"  ✓ Filled phone number: {LOGIN_PHONE}")
        
        # Find and fill password field
        password_input = wait_for_element(driver, By.NAME, "password", timeout=10)
        if not password_input:
            password_input = driver.find_element(By.ID, "id_password")
        
        password_input.clear()
        password_input.send_keys(LOGIN_PASSWORD)
        print(f"  ✓ Filled password")
        
        # Find and click submit button
        submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_button.click()
        print(f"  ✓ Clicked login button")
        
        # Wait for redirect (check if we're redirected away from login page)
        time.sleep(3)
        current_url = driver.current_url
        if "/login/" not in current_url:
            print(f"  ✓ Login successful! Redirected to: {current_url}")
            return True
        else:
            print(f"  ⚠ Warning: Still on login page. Login may have failed.")
            return False
            
    except Exception as e:
        print(f"  ✗ Error during login: {str(e)}")
        return False


def create_product(driver, base_url: str, store_id: int, product_data: Dict[str, Any]) -> bool:
    """
    Create a product through UI
    
    Args:
        driver: Selenium WebDriver instance
        base_url: Base URL of the application
        store_id: Store ID
        product_data: Dictionary with product information
            - name: Product name
            - description: Product description
            - category_id: Category ID (or None to find by name)
            - category_name: Category name (if category_id is None)
            - is_active: True/False
            - variants: List of variant dicts
    
    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"\n  Creating product: {product_data['name']}")
        
        # Navigate to add product page
        add_product_url = f"{base_url}/store/{store_id}/products/add/"
        driver.get(add_product_url)
        time.sleep(2)
        
        # Fill product name
        name_input = wait_for_element(driver, By.ID, "name", timeout=10)
        if name_input:
            name_input.clear()
            name_input.send_keys(product_data['name'])
            print(f"    ✓ Filled product name")
        else:
            print(f"    ✗ Could not find name field")
            return False
        
        # Fill description
        description_input = wait_for_element(driver, By.ID, "description", timeout=10)
        if description_input:
            description_input.clear()
            description_input.send_keys(product_data.get('description', ''))
            print(f"    ✓ Filled description")
        
        # Select is_active dropdown
        is_active_select = wait_for_element(driver, By.NAME, "is_active", timeout=10)
        if is_active_select:
            select = Select(is_active_select)
            if product_data.get('is_active', True):
                select.select_by_value('on')
            else:
                select.select_by_value('')
            print(f"    ✓ Set is_active: {product_data.get('is_active', True)}")
        
        # Select category - Auto-detect from product name/description
        category_select = wait_for_element(driver, By.ID, "category", timeout=10)
        if category_select:
            select = Select(category_select)
            category_id = product_data.get('category_id')
            
            # Auto-detect category from product name and description
            product_name = product_data.get('name', '').lower()
            product_desc = product_data.get('description', '').lower()
            combined_text = f"{product_name} {product_desc}"
            
            # Category mapping based on keywords
            category_keywords = {
                'Vegetables': ['vegetable', 'lettuce', 'spinach', 'cabbage', 'broccoli', 'carrot', 'tomato', 'cucumber', 'onion', 'garlic', 'leafy', 'greens', 'da lat'],
                'Fruits': ['fruit', 'mango', 'apple', 'orange', 'banana', 'dragon fruit', 'pineapple', 'papaya', 'watermelon', 'seasonal', 'tropical'],
                'Meat & Eggs': ['pork', 'beef', 'chicken', 'meat', 'belly', 'shoulder', 'loin', 'cut', 'organic pork', 'free-range'],
                'Seafood': ['fish', 'salmon', 'tuna', 'shrimp', 'crab', 'seafood', 'caught', 'fresh fish', 'atlantic'],
                'Cereals': ['rice', 'grain', 'cereal', 'wheat', 'barley', 'oats', 'sticky rice', 'nếp'],
                'Beverages': ['juice', 'milk', 'yogurt', 'drink', 'beverage', 'fresh juice', 'whole milk']
            }
            
            category_selected = False
            detected_category = None
            
            # Try to detect category from keywords
            for category_name, keywords in category_keywords.items():
                if any(keyword in combined_text for keyword in keywords):
                    detected_category = category_name
                    break
            
            # Try to select detected category
            if detected_category:
                try:
                    # Get all available options
                    options = select.options
                    for option in options:
                        option_text = option.text.strip()
                        # Try exact match first
                        if option_text.lower() == detected_category.lower():
                            select.select_by_visible_text(option_text)
                            print(f"    ✓ Auto-selected category: {option_text}")
                            category_selected = True
                            break
                        # Try partial match
                        elif detected_category.lower() in option_text.lower() or option_text.lower() in detected_category.lower():
                            select.select_by_visible_text(option_text)
                            print(f"    ✓ Auto-selected category (partial match): {option_text}")
                            category_selected = True
                            break
                except Exception as e:
                    print(f"    ⚠ Could not select detected category '{detected_category}': {str(e)}")
            
            # If category_id is provided, try to use it
            if not category_selected and category_id:
                try:
                    select.select_by_value(str(category_id))
                    print(f"    ✓ Selected category by ID: {category_id}")
                    category_selected = True
                except Exception as e:
                    print(f"    ⚠ Could not select category by ID {category_id}: {str(e)}")
            
            # Fallback: select first available category
            if not category_selected:
                try:
                    options = select.options
                    if len(options) > 1:  # Skip first empty option
                        select.select_by_index(1)
                        selected_option = options[1]
                        print(f"    ✓ Selected first available category as fallback: {selected_option.text}")
                    else:
                        print(f"    ⚠ No categories available in dropdown")
                except Exception as e:
                    print(f"    ✗ Could not select any category: {str(e)}")
        
        # Check has_variants checkbox
        has_variants_checkbox = wait_for_element(driver, By.ID, "has_variants", timeout=10)
        if has_variants_checkbox and product_data.get('variants'):
            if not has_variants_checkbox.is_selected():
                # Scroll element into view
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", has_variants_checkbox)
                time.sleep(0.5)
                
                # Wait for element to be clickable
                try:
                    WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.ID, "has_variants"))
                    )
                    # Try JavaScript click if regular click fails
                    try:
                        has_variants_checkbox.click()
                    except:
                        driver.execute_script("arguments[0].click();", has_variants_checkbox)
                    print(f"    ✓ Checked 'has_variants' checkbox")
                    time.sleep(1)  # Wait for variants form to appear
                except Exception as e:
                    print(f"    ⚠ Could not click checkbox: {str(e)}")
                    # Try JavaScript click as fallback
                    try:
                        driver.execute_script("arguments[0].click();", has_variants_checkbox)
                        print(f"    ✓ Checked 'has_variants' checkbox (using JavaScript)")
                        time.sleep(1)
                    except:
                        print(f"    ✗ Failed to check checkbox")
            
            # Wait for variants form container
            variants_container = wait_for_element(driver, By.ID, "variants-form-container", timeout=5)
            if variants_container:
                # Add variants
                variants = product_data.get('variants', [])
                for idx, variant in enumerate(variants, start=1):
                    print(f"    Adding variant {idx}: {variant.get('variant_name', 'N/A')}")
                    
                    # Click "Thêm biến thể" button
                    add_variant_btn = wait_for_element(driver, By.ID, "add-variant-btn", timeout=5)
                    if add_variant_btn:
                        # Scroll button into view
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", add_variant_btn)
                        time.sleep(0.3)
                        
                        # Wait for button to be clickable
                        try:
                            WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.ID, "add-variant-btn"))
                            )
                            try:
                                add_variant_btn.click()
                            except:
                                driver.execute_script("arguments[0].click();", add_variant_btn)
                            time.sleep(0.5)  # Wait for form to appear
                        except:
                            # Fallback to JavaScript click
                            driver.execute_script("arguments[0].click();", add_variant_btn)
                            time.sleep(0.5)
                        
                        # Find the last variant form (most recently added)
                        variant_forms = driver.find_elements(By.CSS_SELECTOR, ".variant-form-item")
                        if variant_forms:
                            variant_form = variant_forms[-1]  # Get the last one
                            
                            # Fill variant name
                            variant_name_input = variant_form.find_element(
                                By.CSS_SELECTOR, 
                                'input[name*="[variant_name]"]'
                            )
                            variant_name_input.clear()
                            variant_name_input.send_keys(variant.get('variant_name', ''))
                            
                            # Fill price
                            price_input = variant_form.find_element(
                                By.CSS_SELECTOR,
                                'input[name*="[price]"]'
                            )
                            price_input.clear()
                            price_input.send_keys(str(variant.get('price', 0)))
                            
                            # Fill stock
                            stock_input = variant_form.find_element(
                                By.CSS_SELECTOR,
                                'input[name*="[stock]"]'
                            )
                            stock_input.clear()
                            stock_input.send_keys(str(variant.get('stock', 0)))
                            
                            # Fill SKU (if provided)
                            if variant.get('sku_code'):
                                sku_inputs = variant_form.find_elements(
                                    By.CSS_SELECTOR,
                                    'input[name*="[sku_code]"]'
                                )
                                if sku_inputs:
                                    sku_inputs[0].clear()
                                    sku_inputs[0].send_keys(variant.get('sku_code'))
                            
                            # Fill variant description (if provided)
                            if variant.get('variant_description'):
                                desc_textareas = variant_form.find_elements(
                                    By.CSS_SELECTOR,
                                    'textarea[name*="[variant_description]"]'
                                )
                                if desc_textareas:
                                    desc_textareas[0].clear()
                                    desc_textareas[0].send_keys(variant.get('variant_description'))
                            
                            print(f"      ✓ Filled variant {idx} fields")
                        else:
                            print(f"      ✗ Could not find variant form")
                    else:
                        print(f"      ✗ Could not find 'Add Variant' button")
            else:
                print(f"    ⚠ Variants container not found, skipping variants")
        
        # Submit form
        submit_button = wait_for_element(
            driver, 
            By.CSS_SELECTOR, 
            'button[type="submit"][name="save"]',
            timeout=10
        )
        if submit_button:
            # Scroll button into view
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", submit_button)
            time.sleep(0.5)
            
            # Wait for button to be clickable
            try:
                WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"][name="save"]'))
                )
                try:
                    submit_button.click()
                except:
                    driver.execute_script("arguments[0].click();", submit_button)
                print(f"    ✓ Submitted form")
            except Exception as e:
                # Fallback to JavaScript click
                try:
                    driver.execute_script("arguments[0].click();", submit_button)
                    print(f"    ✓ Submitted form (using JavaScript)")
                except:
                    print(f"    ✗ Could not submit form: {str(e)}")
                    return False
            
            # Wait for redirect or success message
            time.sleep(3)
            current_url = driver.current_url
            if f"/store/{store_id}/products" in current_url:
                print(f"    ✓ Product created successfully!")
                return True
            else:
                print(f"    ⚠ Unexpected redirect: {current_url}")
                return True  # Assume success if redirected
        else:
            print(f"    ✗ Could not find submit button")
            return False
            
    except Exception as e:
        print(f"    ✗ Error creating product: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def get_sample_products() -> List[Dict[str, Any]]:
    """Return list of 10 sample products with 2-3 variants each (all in English)
    Products include detailed information about meat cuts, fish types, vegetable varieties, etc.
    """
    
    products = [
        {
            'name': 'Organic Rice Dien Bien - Sticky Rice',
            'description': 'Premium sticky rice (nếp) grown in Dien Bien province using organic methods. No chemicals or pesticides used. Rich in nutrients, naturally fragrant, perfect for traditional Vietnamese dishes. Variety: Sticky rice (Nếp cẩm).',
            'category_id': None,
            'is_active': True,
            'variants': [
                {
                    'variant_name': '1kg Bag',
                    'price': 50000,
                    'stock': 100,
                    'sku_code': 'RICE-STICKY-1KG-001',
                    'variant_description': '1kg bag, suitable for small families'
                },
                {
                    'variant_name': '5kg Bag',
                    'price': 230000,
                    'stock': 50,
                    'sku_code': 'RICE-STICKY-5KG-001',
                    'variant_description': '5kg bag, economical for large families'
                },
                {
                    'variant_name': '10kg Bag',
                    'price': 450000,
                    'stock': 30,
                    'sku_code': 'RICE-STICKY-10KG-001'
                }
            ]
        },
        {
            'name': 'Fresh Vegetables Da Lat - Leafy Greens Combo',
            'description': 'Fresh leafy vegetables grown in Da Lat highlands. Includes: Lettuce (Xà lách), Spinach (Rau mồng tôi), Water spinach (Rau muống), and Mustard greens (Cải xanh). No pesticides used, safe for health. Grown using organic farming methods.',
            'category_id': None,
            'is_active': True,
            'variants': [
                {
                    'variant_name': 'Small Combo (2kg)',
                    'price': 80000,
                    'stock': 75,
                    'sku_code': 'VEG-LEAFY-2KG',
                    'variant_description': 'Diverse leafy vegetable combo: lettuce, spinach, water spinach'
                },
                {
                    'variant_name': 'Large Combo (5kg)',
                    'price': 180000,
                    'stock': 40,
                    'sku_code': 'VEG-LEAFY-5KG',
                    'variant_description': 'Large combo with more variety'
                }
            ]
        },
        {
            'name': 'Organic Pork - Belly Cut (Ba chỉ)',
            'description': 'Premium pork belly (Ba chỉ) from free-range pigs raised using organic methods. No antibiotics or growth hormones. Fresh cut, perfect for grilling or braising. Cut type: Belly (Ba chỉ) - the most popular cut with layers of meat and fat. Breed: Local Vietnamese pig.',
            'category_id': None,
            'is_active': True,
            'variants': [
                {
                    'variant_name': 'Pork Belly (500g)',
                    'price': 120000,
                    'stock': 60,
                    'sku_code': 'PORK-BELLY-500G',
                    'variant_description': 'Fresh cut pork belly, perfect for grilling'
                },
                {
                    'variant_name': 'Pork Belly (1kg)',
                    'price': 230000,
                    'stock': 40,
                    'sku_code': 'PORK-BELLY-1KG',
                    'variant_description': 'Larger cut, better value'
                },
                {
                    'variant_name': 'Pork Shoulder (500g)',
                    'price': 100000,
                    'stock': 50,
                    'sku_code': 'PORK-SHOULDER-500G',
                    'variant_description': 'Pork shoulder cut, tender and flavorful'
                }
            ]
        },
        {
            'name': 'Fresh Fish - Atlantic Salmon',
            'description': 'Fresh Atlantic salmon (Cá hồi) caught from clean waters, never frozen. Rich in omega-3 fatty acids, high-quality protein. Fish type: Atlantic Salmon. Caught using sustainable fishing methods. Perfect for grilling, baking, or sashimi.',
            'category_id': None,
            'is_active': True,
            'variants': [
                {
                    'variant_name': 'Salmon Fillet (300g)',
                    'price': 150000,
                    'stock': 30,
                    'sku_code': 'FISH-SALMON-300G',
                    'variant_description': 'Fresh salmon fillet, rich in omega-3'
                },
                {
                    'variant_name': 'Salmon Fillet (500g)',
                    'price': 240000,
                    'stock': 25,
                    'sku_code': 'FISH-SALMON-500G',
                    'variant_description': 'Larger fillet, perfect for family meals'
                }
            ]
        },
        {
            'name': 'Seasonal Fruits - Tropical Mix',
            'description': 'Seasonal tropical fruits grown naturally without pesticides. Includes: Mango (Xoài), Dragon fruit (Thanh long), Pineapple (Dứa), and Papaya (Đu đủ). Sweet and nutritious, no preservatives. Grown in Mekong Delta region.',
            'category_id': None,
            'is_active': True,
            'variants': [
                {
                    'variant_name': 'Small Fruit Combo (1kg)',
                    'price': 90000,
                    'stock': 80,
                    'sku_code': 'FRUIT-TROPICAL-1KG',
                    'variant_description': 'Mix of mango, dragon fruit, pineapple'
                },
                {
                    'variant_name': 'Large Fruit Combo (3kg)',
                    'price': 250000,
                    'stock': 45,
                    'sku_code': 'FRUIT-TROPICAL-3KG',
                    'variant_description': 'More variety, includes papaya'
                },
                {
                    'variant_name': 'Premium Fruit Combo (5kg)',
                    'price': 400000,
                    'stock': 20,
                    'sku_code': 'FRUIT-TROPICAL-5KG',
                    'variant_description': 'Premium selection with best quality fruits'
                }
            ]
        },
        {
            'name': 'Fresh Whole Milk - Free Range Cow',
            'description': 'Fresh whole milk from free-range cows raised on organic farms. Not heat-treated (pasteurized but not UHT), rich in natural nutrients and probiotics. Source: Local Vietnamese dairy cows. No antibiotics or hormones.',
            'category_id': None,
            'is_active': True,
            'variants': [
                {
                    'variant_name': '500ml Bottle',
                    'price': 35000,
                    'stock': 120,
                    'sku_code': 'MILK-FRESH-500ML',
                    'variant_description': 'Glass bottle 500ml, fresh daily'
                },
                {
                    'variant_name': '1L Bottle',
                    'price': 65000,
                    'stock': 90,
                    'sku_code': 'MILK-FRESH-1L',
                    'variant_description': 'Larger bottle, better value'
                }
            ]
        },
        {
            'name': 'Natural Honey - Wildflower',
            'description': 'Pure natural wildflower honey (Mật ong hoa rừng), unadulterated, harvested from natural hives in forest areas. No additives or processing. Honey type: Wildflower honey from various forest flowers. Rich in enzymes and antioxidants.',
            'category_id': None,
            'is_active': True,
            'variants': [
                {
                    'variant_name': '250g Jar',
                    'price': 120000,
                    'stock': 70,
                    'sku_code': 'HONEY-WILDFLOWER-250G',
                    'variant_description': 'Small jar, perfect for daily use'
                },
                {
                    'variant_name': '500g Jar',
                    'price': 220000,
                    'stock': 50,
                    'sku_code': 'HONEY-WILDFLOWER-500G',
                    'variant_description': 'Medium jar, good value'
                },
                {
                    'variant_name': '1kg Jar',
                    'price': 420000,
                    'stock': 30,
                    'sku_code': 'HONEY-WILDFLOWER-1KG',
                    'variant_description': 'Large jar, best value for families'
                }
            ]
        },
        {
            'name': 'Organic Baked Bread - Whole Wheat',
            'description': 'Delicious whole wheat bread (Bánh mì nguyên cám) made from organic whole wheat flour. No preservatives, artificial additives, or bleaching agents. Bread type: Whole wheat bread. Baked fresh daily using traditional methods.',
            'category_id': None,
            'is_active': True,
            'variants': [
                {
                    'variant_name': 'Small Loaf (200g)',
                    'price': 25000,
                    'stock': 150,
                    'sku_code': 'BREAD-WHOLEWHEAT-200G',
                    'variant_description': 'Small loaf, perfect for 1-2 people'
                },
                {
                    'variant_name': 'Large Loaf (400g)',
                    'price': 45000,
                    'stock': 100,
                    'sku_code': 'BREAD-WHOLEWHEAT-400G',
                    'variant_description': 'Large loaf, great for families'
                }
            ]
        },
        {
            'name': 'Fresh Fruit Juice - Orange & Apple Blend',
            'description': 'Fresh fruit juice blend made from 100% natural fruits. No artificial sweeteners, no preservatives, rich in vitamins C and A. Juice types: Orange juice (Nước cam) and Apple juice (Nước táo) blend. Cold-pressed to preserve nutrients.',
            'category_id': None,
            'is_active': True,
            'variants': [
                {
                    'variant_name': '330ml Bottle',
                    'price': 40000,
                    'stock': 100,
                    'sku_code': 'JUICE-ORANGE-APPLE-330ML',
                    'variant_description': 'Orange and apple juice blend'
                },
                {
                    'variant_name': '500ml Bottle',
                    'price': 55000,
                    'stock': 80,
                    'sku_code': 'JUICE-ORANGE-APPLE-500ML',
                    'variant_description': 'Larger bottle, more servings'
                },
                {
                    'variant_name': '1L Bottle',
                    'price': 95000,
                    'stock': 60,
                    'sku_code': 'JUICE-ORANGE-APPLE-1L',
                    'variant_description': 'Family size bottle'
                }
            ]
        },
        {
            'name': 'Organic Yogurt - Greek Style',
            'description': 'Organic Greek-style yogurt (Sữa chua Hy Lạp) rich in probiotics, good for digestion. Made from fresh whole milk, no artificial sweeteners or preservatives. Yogurt type: Greek-style yogurt - thick and creamy. Contains live active cultures.',
            'category_id': None,
            'is_active': True,
            'variants': [
                {
                    'variant_name': '100g Container',
                    'price': 20000,
                    'stock': 200,
                    'sku_code': 'YOGURT-GREEK-100G',
                    'variant_description': 'Single serving container'
                },
                {
                    'variant_name': '200g Container',
                    'price': 35000,
                    'stock': 150,
                    'sku_code': 'YOGURT-GREEK-200G',
                    'variant_description': 'Double serving container'
                }
            ]
        }
    ]
    
    return products


def main():
    parser = argparse.ArgumentParser(description='Automate product creation through UI')
    parser.add_argument('--store-id', type=int, default=1, help='Store ID (default: 1)')
    parser.add_argument('--base-url', type=str, default='http://127.0.0.1:8000', help='Base URL (default: http://127.0.0.1:8000)')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--delay', type=float, default=2.0, help='Delay between products in seconds (default: 2.0)')
    
    args = parser.parse_args()
    
    if not SELENIUM_AVAILABLE:
        print("Error: Selenium is not available")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print("UI Automation Script for Adding Products")
    print(f"{'='*60}")
    print(f"Store ID: {args.store_id}")
    print(f"Base URL: {args.base_url}")
    print(f"Headless mode: {args.headless}")
    print(f"{'='*60}\n")
    
    driver = None
    try:
        # Setup driver
        print("Setting up Chrome driver...")
        driver = setup_driver(headless=args.headless)
        print("✓ Driver initialized")
        
        # Login
        login_success = login(driver, args.base_url)
        if not login_success:
            print("\n⚠ Warning: Login may have failed, but continuing...")
        
        # Get sample products
        products = get_sample_products()
        print(f"\n{'='*60}")
        print(f"Creating {len(products)} products...")
        print(f"{'='*60}\n")
        
        # Create products
        success_count = 0
        failure_count = 0
        
        for idx, product_data in enumerate(products, 1):
            print(f"[{idx}/{len(products)}] Processing...")
            success = create_product(driver, args.base_url, args.store_id, product_data)
            
            if success:
                success_count += 1
            else:
                failure_count += 1
            
            # Delay between products
            if idx < len(products):
                time.sleep(args.delay)
        
        # Summary
        print(f"\n{'='*60}")
        print("Summary")
        print(f"{'='*60}")
        print(f"Total products: {len(products)}")
        print(f"Success: {success_count}")
        print(f"Failed: {failure_count}")
        print(f"{'='*60}\n")
        
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user")
    except Exception as e:
        print(f"\n\nError: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            print("Closing browser...")
            driver.quit()
            print("✓ Browser closed")


if __name__ == '__main__':
    main()

