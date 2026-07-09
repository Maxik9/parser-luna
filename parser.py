import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import datetime
import time
import re
import html

BASE_URL = "https://lunabag.com.ua/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_price(price_str):
    if not price_str:
        return "0"
    # Remove non-numeric characters except dot/comma
    clean = re.sub(r'[^\d.,]', '', price_str)
    clean = clean.replace(',', '.')
    clean = clean.strip('.')
    return clean

def get_categories():
    print("Fetching categories...")
    try:
        resp = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.content, "lxml")
        
        categories = {}
        menu = soup.find('div', class_='ds-menu-main-catalog')
        if not menu:
            return categories
            
        items = menu.find_all('a', class_='ds-menu-maincategories-item-title')
        for item in items:
            href = item.get('href')
            title = item.get_text(strip=True)
            if href and title:
                # Extract path ID
                match = re.search(r'path=(\d+)', href)
                if match:
                    cat_id = match.group(1)
                    categories[cat_id] = {
                        'id': cat_id,
                        'name': title,
                        'url': href
                    }
        return categories
    except Exception as e:
        print(f"Error fetching categories: {e}")
        return {}

def scrape_category(cat_id, cat_url):
    print(f"Scraping category {cat_id}: {cat_url}")
    product_links = set()
    page = 1
    
    while True:
        url = f"{cat_url}&page={page}" if '?' in cat_url else f"{cat_url}?page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.content, "lxml")
            
            # Find product titles
            titles = soup.find_all('a', class_='ds-module-title')
            new_links = []
            for t in titles:
                href = t.get('href')
                if href and href not in product_links:
                    new_links.append(href)
            
            if not new_links:
                break
                
            for link in new_links:
                product_links.add(link)
                
            page += 1
            time.sleep(1) # Polite delay
        except Exception as e:
            print(f"Error scraping category page {page}: {e}")
            break
            
    return list(product_links)

def scrape_product(url, cat_id):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.content, "lxml")
        
        # Product ID
        prod_id = None
        match = re.search(r'product_id=(\d+)', url)
        if match:
            prod_id = match.group(1)
        else:
            pid_input = soup.find('input', {'name': 'product_id'})
            if pid_input:
                prod_id = pid_input.get('value')
                
        if not prod_id:
            return None
            
        # Title
        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "Без назви"
        
        # Price
        price_val = "0"
        price_new = soup.find(class_=lambda c: c and 'price-new' in c.lower())
        if not price_new:
            price_new = soup.find(class_=lambda c: c and 'product-main-price' in c.lower())
            
        if price_new:
            price_val = clean_price(price_new.get_text())
        else:
            price_meta = soup.find('meta', itemprop='price')
            if price_meta:
                price_val = price_meta.get('content')
                
        if price_val == "0":
            # Just find any div containing price
            pt = soup.find(class_=lambda c: c and 'price' in c.lower())
            if pt: price_val = clean_price(pt.get_text())
                
        # Description
        desc = ""
        desc_div = soup.find('div', id='oct-product-description')
        if not desc_div:
            desc_div = soup.find('div', class_=lambda c: c and 'description' in c.lower() and 'product' in c.lower())
        if not desc_div:
            desc_div = soup.find('div', id='tab-description')
            
        if desc_div:
            desc = "".join([str(c) for c in desc_div.contents])
            
        # Images
        pictures = set()
        
        # In oct_deals they are usually in a tags with data-fancybox
        for a in soup.find_all('a', {'data-fancybox': 'gallery'}):
            href = a.get('href')
            if href:
                pictures.add(href)
                
        if not pictures:
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and 'catalog/' in src and ('-800x800' in src or '-1000x' in src or '-500x' in src):
                    if not src.endswith('32x32.png') and not src.endswith('32x32.jpg'):
                        # remove -800x800.jpg and put original or keep 800x800 depending on what they serve.
                        pictures.add(src)
                        
        if not pictures:
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and 'catalog/' in src and 'cache' not in src:
                    pictures.add(src)

        return {
            'id': prod_id,
            'url': url,
            'price': price_val,
            'categoryId': cat_id,
            'name': title,
            'description': desc.strip(),
            'pictures': list(pictures)
        }
    except Exception as e:
        print(f"Error scraping product {url}: {e}")
        return None

def build_xml(categories, products):
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # We construct the XML string manually because ElementTree escapes CDATA by default
    # and creating raw CDATA nodes in ElementTree is tedious.
    
    xml = []
    xml.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml.append('<!DOCTYPE yml_catalog SYSTEM "shops.dtd">')
    xml.append(f'<yml_catalog date="{date_str}">')
    xml.append('  <shop>')
    xml.append('    <name>LunaBag</name>')
    xml.append('    <company>LunaBag</company>')
    xml.append('    <url>https://lunabag.com.ua</url>')
    xml.append('    <currencies>')
    xml.append('      <currency id="UAH" rate="1"/>')
    xml.append('    </currencies>')
    
    # Categories
    xml.append('    <categories>')
    for cat_id, cat in categories.items():
        xml.append(f'      <category id="{cat_id}">{html.escape(cat["name"])}</category>')
    xml.append('    </categories>')
    
    # Offers
    xml.append('    <offers>')
    for p in products:
        xml.append(f'      <offer id="{p["id"]}" available="true">')
        xml.append(f'        <url>{html.escape(p["url"])}</url>')
        xml.append(f'        <price>{p["price"]}</price>')
        xml.append('        <currencyId>UAH</currencyId>')
        xml.append(f'        <categoryId>{p["categoryId"]}</categoryId>')
        
        for pic in p['pictures']:
            xml.append(f'        <picture>{html.escape(pic)}</picture>')
            
        xml.append(f'        <name>{html.escape(p["name"])}</name>')
        
        # CDATA description
        if p['description']:
            xml.append(f'        <description><![CDATA[{p["description"]}]]></description>')
            
        xml.append('      </offer>')
        
    xml.append('    </offers>')
    xml.append('  </shop>')
    xml.append('</yml_catalog>')
    
    return "\n".join(xml)

def main():
    print("Starting LunaBag parser...")
    categories = get_categories()
    print(f"Found {len(categories)} categories.")
    
    all_products = []
    
    for cat_id, cat in categories.items():
        product_links = scrape_category(cat_id, cat['url'])
        print(f"Category {cat_id} has {len(product_links)} products.")
        
        for link in product_links:
            prod_data = scrape_product(link, cat_id)
            if prod_data:
                all_products.append(prod_data)
            time.sleep(1) # polite delay between products
            
    print(f"Total products scraped: {len(all_products)}")
    
    # SAFETY CHECK: Do not overwrite if we scraped very few products (e.g. site blocked us or changed layout)
    if len(all_products) < 50:
        print("Error: Too few products scraped (less than 50). Aborting to preserve the old feed!")
        return
    
    xml_content = build_xml(categories, all_products)
    
    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(xml_content)
        
    print("Feed saved to feed.xml successfully!")

if __name__ == "__main__":
    main()
