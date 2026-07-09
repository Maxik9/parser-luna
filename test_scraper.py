import requests
from bs4 import BeautifulSoup

def test_scrape():
    url = "https://lunabag.com.ua/"
    print("Fetching home page...")
    resp = requests.get(url, timeout=10)
    soup = BeautifulSoup(resp.content, "html.parser")
    
    # Let's try to find categories from the menu
    # They seem to be in ds-menu-main-catalog or a tags
    menu = soup.find('div', class_='ds-menu-main-catalog')
    if not menu:
        print("Could not find menu container")
        return
        
    category_links = []
    items = menu.find_all('a', class_='ds-menu-maincategories-item-title')
    for item in items:
        href = item.get('href')
        title = item.get_text(strip=True)
        if href and title:
            category_links.append((title, href))
            
    print(f"Found {len(category_links)} categories:")
    for title, href in category_links[:5]:
        print(f" - {title}: {href}")
        
    if not category_links:
        return
        
    # Pick the first one and fetch its products
    cat_url = category_links[0][1]
    print(f"\nFetching category: {cat_url}")
    cat_resp = requests.get(cat_url, timeout=10)
    cat_soup = BeautifulSoup(cat_resp.content, "html.parser")
    
    # Find all divs and list the classes of the first 20 to see what we have
    divs = cat_soup.find_all('div', class_=True)
    classes = set()
    for d in divs:
        classes.update(d.get('class'))
    print("Found div classes:", list(classes)[:50])
    
    # Finding product links
    product_links = []
    # Opencart themes like oct_deals use 'ds-module-item' or 'ds-product-thumb' 
    items = cat_soup.find_all('div', class_='ds-module-item')
    if not items:
        # let's look for any 'a' with a typical product class
        items = cat_soup.find_all('div', class_=lambda c: c and 'product-layout' in c)
    
    # Actually just look for a with class ds-module-title
    titles = cat_soup.find_all('a', class_='ds-module-title')
    for t in titles:
        product_links.append(t['href'])
    
    if not product_links:
        # fallback
        for a in cat_soup.find_all('a', href=True):
            if 'product_id=' in a['href']:
                product_links.append(a['href'])
                
    product_links = list(set(product_links))
    print(f"Found {len(product_links)} potential product links")
            
    if not product_links:
        print("No product links found to test product page.")
        return
        
    prod_url = product_links[0]
    print(f"\nFetching product: {prod_url}")
    prod_resp = requests.get(prod_url, timeout=10)
    prod_soup = BeautifulSoup(prod_resp.content, "html.parser")
    
    title = prod_soup.find('h1')
    price = prod_soup.find(class_=lambda c: c and 'price' in c.lower())
    
    print(f"Title: {title.text.strip() if title else 'N/A'}")
    print(f"Price: {price.text.strip() if price else 'N/A'}")

if __name__ == "__main__":
    test_scrape()
