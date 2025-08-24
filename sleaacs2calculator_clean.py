import requests
import urllib.parse
import time
import re
import json
import random
from bs4 import BeautifulSoup
import cloudscraper  # pip install cloudscraper
try:
    import winsound
except ImportError:
    winsound = None

# Configuration - ADD YOUR API KEYS HERE
API_KEYS = {
    'skinport': None,  # Get from https://skinport.com/api
    'csfloat': None,   # Get from https://csfloat.com/api
    'steam': None,     # Steam Web API key from https://steamcommunity.com/dev/apikey
    'bitskins': None,  # BitSkins API key
    'dmarket': None    # DMarket API key
}

skins = [
    "AK-47 | Redline (Field-Tested)",
    "M4A4 | Howl (Factory New)",
    "★ Karambit | Doppler (Factory New)",
    "AWP | Dragon Lore (Field-Tested)",
    "AK-47 | Fire Serpent (Field-Tested)",
    "M4A4 | Asiimov (Field-Tested)",
    "AWP | Asiimov (Field-Tested)",
    "Glock-18 | Fade (Factory New)",
    "USP-S | Kill Confirmed (Field-Tested)",
    "★ Butterfly Knife | Fade (Factory New)"
]

# Rotating headers to avoid detection
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
]

def get_headers():
    """Get randomized headers to avoid getting blocked"""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://skinport.com/',
        'Origin': 'https://skinport.com',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site'
    }

# Rate limiting system
last_request_times = {}

def rate_limit_request(platform, min_delay=2.0):
    """Rate limit requests to avoid getting blocked"""
    current_time = time.time()
    last_time = last_request_times.get(platform, 0)
    elapsed = current_time - last_time
    
    if elapsed < min_delay:
        sleep_time = min_delay - elapsed + random.uniform(0.5, 1.5)
        print(f"    ⏳ Rate limiting {platform}: waiting {sleep_time:.1f}s")
        time.sleep(sleep_time)
    
    last_request_times[platform] = time.time()

def clean_skin_name_for_url(name):
    """Clean skin name for URL encoding"""
    # Remove star symbol
    name = name.replace("★ ", "")
    # URL encode
    return urllib.parse.quote(name.strip())

def get_steam_market_price(skin_name):
    """Get price from Steam Community Market with better error handling"""
    try:
        rate_limit_request('steam', 2.0)
        
        # Use the correct Steam Market API endpoint
        url = "https://steamcommunity.com/market/priceoverview/"
        params = {
            'appid': 730,  # CS:GO/CS2 app ID
            'currency': 1,  # USD
            'market_hash_name': skin_name
        }
        
        # Add better headers to avoid blocking
        steam_headers = get_headers()
        steam_headers.update({
            'Referer': 'https://steamcommunity.com/market/',
            'Origin': 'https://steamcommunity.com',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        })
        
        response = requests.get(url, params=params, headers=steam_headers, timeout=15)
        
        print(f"    Steam API Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"    Steam Response: {data}")
                
                if data.get('success') == True:
                    # Try multiple price fields - Steam API can return different formats
                    lowest_price = data.get('lowest_price')
                    median_price = data.get('median_price')
                    
                    # Clean and parse lowest_price
                    price_to_use = None
                    if lowest_price and str(lowest_price) not in ['None', '--', '']:
                        try:
                            price_str = str(lowest_price).replace('$', '').replace(',', '').strip()
                            price_to_use = float(price_str)
                        except (ValueError, TypeError):
                            pass
                    
                    # Fall back to median_price if lowest_price is not available
                    if not price_to_use and median_price and str(median_price) not in ['None', '--', '']:
                        try:
                            price_str = str(median_price).replace('$', '').replace(',', '').strip()
                            price_to_use = float(price_str)
                            print(f"    Steam: Using median_price as fallback: ${price_to_use:.2f}")
                        except (ValueError, TypeError):
                            pass
                    
                    if price_to_use and price_to_use > 0:
                        # Parse volume if available
                        volume = data.get('volume', 'N/A')
                        return {
                            'price_usd': price_to_use,
                            'name': skin_name,
                            'url': f"https://steamcommunity.com/market/listings/730/{urllib.parse.quote(skin_name)}",
                            'volume': volume
                        }
                    else:
                        print(f"    Steam: No price data (lowest_price: '{lowest_price}', median_price: '{median_price}')")
                        
            except json.JSONDecodeError as e:
                print(f"    Steam: JSON decode error - {e}")
                print(f"    Response text: {response.text[:200]}...")
        elif response.status_code == 429:
            print(f"    Steam: Rate limited - waiting...")
            time.sleep(10 + random.uniform(0, 5))
        else:
            print(f"    Steam: HTTP {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"    Steam Market Request Error: {e}")
    except Exception as e:
        print(f"    Steam Market Error: {e}")
    
    return None

def get_steamapis_price(skin_name):
    """Alternative price source using SteamApis.com"""
    try:
        rate_limit_request('steamapis', 2.0)
        
        # Try multiple SteamApis endpoints
        endpoints = [
            f"https://api.steamapis.com/market/item/730/{urllib.parse.quote(skin_name)}",
            f"https://api.steamapis.com/steam/market/730/{urllib.parse.quote(skin_name)}"
        ]
        
        for url in endpoints:
            try:
                response = requests.get(url, headers=get_headers(), timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Try different price field names
                    price_fields = ['lowest_price', 'price', 'median_price', 'current_price']
                    
                    for field in price_fields:
                        price_value = data.get(field)
                        if price_value and str(price_value) not in ['None', '--', '']:
                            try:
                                if isinstance(price_value, str):
                                    price_str = price_value.replace('$', '').replace(',', '').strip()
                                    price_to_use = float(price_str)
                                else:
                                    price_to_use = float(price_value)
                                
                                if price_to_use > 0:
                                    return {
                                        'price_usd': price_to_use,
                                        'name': skin_name,
                                        'url': f"https://steamcommunity.com/market/listings/730/{urllib.parse.quote(skin_name)}"
                                    }
                            except (ValueError, TypeError):
                                continue
                
            except Exception as e:
                print(f"    SteamApis endpoint error: {e}")
                continue
                
    except Exception as e:
        print(f"    SteamApis Error: {e}")
    
    return None

def get_buff163_price(skin_name):
    """Get price from Buff163 as primary reference"""
    try:
        rate_limit_request('buff163', 3.0)
        
        # Clean skin name for Buff URL
        clean_name = skin_name.replace("★ ", "").replace(" | ", " ").replace(" (", " ").replace(")", "")
        
        # Buff163 uses different API - you may need to use web scraping approach
        url = f"https://buff.163.com/api/market/goods"
        params = {
            'game': 'csgo',
            'search': clean_name,
            'page_num': 1
        }
        
        response = requests.get(url, params=params, headers=get_headers(), timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('data', {}).get('items'):
                items = data['data']['items']
                for item in items:
                    if clean_name.lower() in item.get('name', '').lower():
                        price_cny = float(item.get('sell_min_price', 0))
                        # Convert CNY to USD (approximate rate: 1 USD = 7.2 CNY)
                        price_usd = price_cny / 7.2
                        return {
                            'price_usd': price_usd,
                            'name': skin_name,
                            'url': f"https://buff.163.com/goods/{item.get('id', '')}"
                        }
    except Exception as e:
        print(f"    Buff163 Error: {e}")
    
    return None

def get_buff163_price_scraping(skin_name):
    """Buff163 via web scraping with CloudFlare bypass"""
    try:
        print("    ⏳ Trying Buff163 (web scraping)...")
        rate_limit_request('buff163_scraping', 5.0)
        
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )
        
        # Search URL for Buff163
        search_term = skin_name.replace('★ ', '').replace(' | ', ' ')
        encoded_search = urllib.parse.quote(search_term)
        url = f"https://buff.163.com/market/csgo#tab=selling&page_num=1&search={encoded_search}"
        
        response = scraper.get(url, timeout=20)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for price elements (this would need to be customized based on actual HTML structure)
            price_elements = soup.find_all(['span', 'div'], class_=re.compile(r'price|cost', re.I))
            
            for elem in price_elements[:3]:  # Check first 3 price elements
                price_text = elem.get_text(strip=True)
                # Look for CNY prices
                price_match = re.search(r'¥(\d+\.?\d*)', price_text)
                if price_match:
                    price_cny = float(price_match.group(1))
                    price_usd = price_cny / 7.2  # Convert CNY to USD
                    if price_usd > 1:  # Reasonable price check
                        return {
                            'price_usd': price_usd,
                            'name': skin_name,
                            'url': url
                        }
                        
    except Exception as e:
        print(f"    Buff163 scraping Error: {e}")
    
    return None

def get_pricempire_price(skin_name):
    """Try Pricempire API if available"""
    try:
        rate_limit_request('pricempire', 2.0)
        
        # Simple approach - try to get basic price data
        clean_name = skin_name.replace("★ ", "").replace(" | ", "-").replace(" (", "-").replace(")", "").replace(" ", "-").lower()
        url = f"https://pricempire.com/api/v1/market/items/{clean_name}"
        
        response = requests.get(url, headers=get_headers(), timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('steam') and data['steam'].get('last_24h'):
                return {
                    'price_usd': float(data['steam']['last_24h']),
                    'name': skin_name,
                    'url': f"https://pricempire.com/item/cs2/{clean_name}"
                }
    except Exception as e:
        print(f"    Pricempire Error: {e}")
    
    return None

def get_csgostash_price(skin_name):
    """Try CSGOStash as fallback price source"""
    try:
        rate_limit_request('csgostash', 2.0)
        
        # Clean skin name for CSGOStash URL format
        clean_name = skin_name.replace("★ ", "").replace(" | ", "-").replace(" (", "-").replace(")", "").replace(" ", "-").lower()
        url = f"https://csgostash.com/api/v2/prices/{clean_name}"
        
        response = requests.get(url, headers=get_headers(), timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('steam_price'):
                return {
                    'price_usd': float(data['steam_price']),
                    'name': skin_name,
                    'url': f"https://csgostash.com/skin/{clean_name}"
                }
    except Exception as e:
        print(f"    CSGOStash Error: {e}")
    
    return None

def get_steamlytics_price(skin_name):
    """Alternative price source - SteamLytics"""
    try:
        rate_limit_request('steamlytics', 3.0)
        
        # Clean skin name for URL
        clean_name = skin_name.replace('★ ', '').replace(' | ', '-').replace(' (', '-').replace(')', '').replace(' ', '-').lower()
        url = f"https://steamlytics.xyz/api/v2/pricelist"
        
        params = {
            'currency': 'USD',
            'search': skin_name
        }
        
        response = requests.get(url, params=params, headers=get_headers(), timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('items'):
                for item in data['items']:
                    if skin_name.lower() in item.get('name', '').lower():
                        price = item.get('price', {}).get('steam', {}).get('last_24h')
                        if price:
                            return {
                                'price_usd': float(price),
                                'name': skin_name,
                                'url': f"https://steamlytics.xyz/item/{clean_name}"
                            }
                            
    except Exception as e:
        print(f"    SteamLytics Error: {e}")
    
    return None

def get_simple_steam_price(skin_name):
    """Simple Steam market price checker - different approach"""
    try:
        rate_limit_request('steam_simple', 3.0)
        
        # Use Steam's market search page to get price info
        search_url = "https://steamcommunity.com/market/search/render/"
        params = {
            'appid': 730,
            'currency': 1,
            'start': 0,
            'count': 5,
            'search_descriptions': 0,
            'sort_column': 'price',
            'sort_dir': 'asc',
            'query': skin_name
        }
        
        response = requests.get(search_url, params=params, headers=get_headers(), timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('results'):
                results = data['results']
                
                for item in results:
                    item_name = item.get('name', '').strip()
                    hash_name = item.get('hash_name', '').strip()
                    
                    # Check if this is the skin we're looking for
                    if (skin_name.lower() in item_name.lower() or 
                        skin_name.lower() in hash_name.lower()):
                        
                        # Try to extract price from sell_price_text
                        price_text = item.get('sell_price_text', '')
                        if price_text and '$' in price_text:
                            try:
                                # Extract price from text like "$12.34" or "Starting at: $12.34"
                                price_match = re.search(r'\$(\d+\.?\d*)', price_text)
                                if price_match:
                                    price_value = float(price_match.group(1))
                                    if price_value > 0:
                                        return {
                                            'price_usd': price_value,
                                            'name': skin_name,
                                            'url': f"https://steamcommunity.com/market/listings/730/{urllib.parse.quote(skin_name)}"
                                        }
                            except (ValueError, AttributeError):
                                continue
                                
    except Exception as e:
        print(f"    Steam Simple Error: {e}")
    
    return None

def get_reference_price(skin_name):
    """Get reference price from multiple sources with improved fallbacks"""
    print(f"  🔍 Getting reference price for {skin_name}...")
    
    # Try Buff163 first (your preferred reference)
    print("    ⏳ Trying Buff163...")
    buff_price = get_buff163_price(skin_name)
    if buff_price:
        print(f"    ✅ Buff163: ${buff_price['price_usd']:.2f}")
        return buff_price
    
    # Try Buff163 scraping as backup
    buff_scraping = get_buff163_price_scraping(skin_name)
    if buff_scraping:
        print(f"    ✅ Buff163 (scraping): ${buff_scraping['price_usd']:.2f}")
        return buff_scraping
    
    # Then fall back to Steam Market...
    print("    ❌ Buff163 failed, trying Steam Community Market...")
    steam_price = get_steam_market_price(skin_name)
    if steam_price:
        print(f"    ✅ Steam Market: ${steam_price['price_usd']:.2f} (Volume: {steam_price.get('volume', 'N/A')})")
        return steam_price
    
    print("    ❌ Steam Market failed, trying Steam Simple Search...")
    
    # Try Steam Simple Search as immediate fallback
    steam_simple = get_simple_steam_price(skin_name)
    if steam_simple:
        print(f"    ✅ Steam Simple: ${steam_simple['price_usd']:.2f}")
        return steam_simple
    
    print("    ❌ Steam Simple failed, trying SteamApis...")
    
    # Try SteamApis as backup
    steamapis_price = get_steamapis_price(skin_name)
    if steamapis_price:
        print(f"    ✅ SteamApis: ${steamapis_price['price_usd']:.2f}")
        return steamapis_price
    
    print("    ❌ SteamApis failed, trying SteamLytics...")
    
    # Try SteamLytics as backup
    steamlytics_price = get_steamlytics_price(skin_name)
    if steamlytics_price:
        print(f"    ✅ SteamLytics: ${steamlytics_price['price_usd']:.2f}")
        return steamlytics_price
    
    print("    ❌ SteamLytics failed, trying Pricempire...")
    
    # Try Pricempire as backup
    pricempire_price = get_pricempire_price(skin_name)
    if pricempire_price:
        print(f"    ✅ Pricempire: ${pricempire_price['price_usd']:.2f}")
        return pricempire_price
    
    print("    ❌ Pricempire failed, trying CSGOStash...")
    
    # Try CSGOStash as final fallback
    csgostash_price = get_csgostash_price(skin_name)
    if csgostash_price:
        print(f"    ✅ CSGOStash: ${csgostash_price['price_usd']:.2f}")
        return csgostash_price
    
    print("    ❌ All price sources failed")
    return None

def get_skinport_listings_web_scraping(skin_name):
    """Web scraping approach for Skinport with CloudFlare bypass"""
    try:
        print("  🔍 Fetching Skinport via web scraping...")
        rate_limit_request('skinport_web', 5.0)
        
        # Use cloudscraper to bypass CloudFlare
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )
        
        # Search URL format
        search_query = urllib.parse.quote(skin_name.replace('★ ', ''))
        url = f"https://skinport.com/market/730?search={search_query}"
        
        response = scraper.get(url, timeout=20)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for item cards/listings (these selectors would need to be updated based on actual HTML)
            item_cards = soup.find_all(['div', 'a'], class_=re.compile(r'item|card|listing', re.I))
            
            listings = []
            for card in item_cards[:5]:  # Get first 5
                try:
                    # Try to extract price
                    price_elem = card.find(['span', 'div'], string=re.compile(r'\$\d+', re.I))
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        price_match = re.search(r'\$(\d+\.?\d*)', price_text.replace(',', ''))
                        
                        if price_match:
                            price = float(price_match.group(1))
                            
                            # Extract other info if available
                            float_elem = card.find(['span', 'div'], string=re.compile(r'float|wear', re.I))
                            wear_elem = card.find(['span', 'div'], class_=re.compile(r'wear|condition', re.I))
                            
                            listings.append({
                                'price': price,
                                'float': float_elem.get_text(strip=True) if float_elem else 'N/A',
                                'wear': wear_elem.get_text(strip=True) if wear_elem else 'Unknown',
                                'url': f"https://skinport.com{card.get('href', '')}" if card.get('href') else url,
                                'platform': 'Skinport',
                                'id': 'scraped',
                                'stickers': [],
                                'screenshot': ''
                            })
                            
                except Exception as parse_error:
                    continue
            
            if listings:
                print(f"  ✅ Found {len(listings)} Skinport listings via scraping")
                return listings
                
    except Exception as e:
        print(f"  ❌ Skinport scraping error: {e}")
    
    return []

def get_skinport_listings_complete(skin_name):
    """
    Complete Skinport API implementation with all error handling
    Uses the actual working Skinport endpoints
    """
    try:
        print(f"  🔍 Fetching from Skinport API...")
        rate_limit_request('skinport', 10.0)  # Conservative rate limiting
        
        # Clean the skin name for search
        search_term = skin_name.lower().replace('|', '').replace('(', '').replace(')', '').replace('-', ' ').strip()
        search_encoded = '+'.join(search_term.split())
        
        # Try multiple endpoint approaches
        endpoints = [
            # Method 1: Direct search
            {
                'url': f'https://skinport.com/api/data/730',
                'params': {'search': search_encoded},
                'method': 'search'
            },
            # Method 2: Get all items for weapon type
            {
                'url': f'https://skinport.com/api/data/730',
                'params': {},
                'method': 'filter_locally'
            }
        ]
        
        for attempt, endpoint_config in enumerate(endpoints, 1):
            try:
                print(f"    Attempt {attempt}: {endpoint_config['method']}")
                
                headers = {
                    'User-Agent': random.choice(USER_AGENTS),
                    'Accept': 'application/json',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Referer': 'https://skinport.com/',
                    'Origin': 'https://skinport.com'
                }
                
                response = requests.get(
                    endpoint_config['url'],
                    params=endpoint_config['params'],
                    headers=headers,
                    timeout=20
                )
                
                print(f"    Response: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"    Data keys: {list(data.keys()) if isinstance(data, dict) else 'List response'}")
                    
                    # Handle different response formats
                    items = []
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        # Try different possible keys
                        items = (data.get('items') or 
                                data.get('data') or 
                                data.get('results') or
                                [data] if 'market_hash_name' in data else [])
                    
                    print(f"    Found {len(items)} total items")
                    
                    # Filter items that match our skin
                    matching_items = []
                    skin_keywords = skin_name.lower().replace('|', '').replace('(', '').replace(')', '').split()
                    
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                            
                        item_name = item.get('market_hash_name', '').lower()
                        item_name_clean = item_name.replace('|', '').replace('(', '').replace(')', '')
                        
                        # Check if all keywords from our skin are in the item name
                        if all(keyword in item_name_clean for keyword in skin_keywords):
                            matching_items.append(item)
                    
                    print(f"    Matching items: {len(matching_items)}")
                    
                    if matching_items:
                        listings = []
                        
                        for item in matching_items[:10]:  # Get top 10 matches
                            try:
                                # Skinport price structure analysis
                                price_fields = [
                                    'suggested_price',
                                    'min_price', 
                                    'starting_at',
                                    'price',
                                    'avg_price'
                                ]
                                
                                price_value = None
                                for field in price_fields:
                                    if field in item and item[field]:
                                        price_raw = item[field]
                                        # Handle different price formats
                                        if isinstance(price_raw, (int, float)):
                                            # Prices might be in cents
                                            if price_raw > 100:
                                                price_value = price_raw / 100
                                            else:
                                                price_value = price_raw
                                            break
                                        elif isinstance(price_raw, str):
                                            # Extract number from string
                                            price_match = re.search(r'(\d+\.?\d*)', price_raw.replace(',', ''))
                                            if price_match:
                                                price_value = float(price_match.group(1))
                                                if price_value > 100:
                                                    price_value = price_value / 100
                                                break
                                
                                if price_value and price_value > 0:
                                    # Extract additional item info
                                    float_value = item.get('wear_value') or item.get('float')
                                    exterior = item.get('exterior') or item.get('condition') or 'Unknown'
                                    item_id = item.get('id') or item.get('item_id') or 'unknown'
                                    
                                    listing = {
                                        'price': float(price_value),
                                        'float': float_value,
                                        'url': f"https://skinport.com/item/{item_id}",
                                        'wear': exterior,
                                        'id': str(item_id),
                                        'stickers': item.get('stickers', []),
                                        'screenshot': item.get('image') or item.get('screenshot', ''),
                                        'platform': 'Skinport'
                                    }
                                    listings.append(listing)
                                    
                            except Exception as parse_error:
                                print(f"    Error parsing item: {parse_error}")
                                continue
                        
                        if listings:
                            # Sort by price
                            listings.sort(key=lambda x: x['price'])
                            print(f"  ✅ Skinport: Found {len(listings)} listings")
                            return listings[:5]  # Return top 5
                
                elif response.status_code == 429:
                    print(f"    Rate limited, waiting 30 seconds...")
                    time.sleep(30)
                    continue
                    
            except requests.exceptions.RequestException as e:
                print(f"    Request error: {e}")
                continue
        
        print(f"  ❌ Skinport: All API methods failed, trying web scraping...")
        return get_skinport_listings_web_scraping(skin_name)
        
    except Exception as e:
        print(f"  ❌ Skinport Error: {e}")
        return get_skinport_listings_web_scraping(skin_name)

def get_skinport_listings(skin_name):
    """Get listings from Skinport with comprehensive error handling"""
    try:
        print(f"  🔍 Fetching Skinport listings...")
        rate_limit_request('skinport', 3.0)  # Longer delay for Skinport
        
        # Try multiple API approaches with better parameters
        api_attempts = [
            # Method 1: Search query (more reliable)
            {
                'url': 'https://api.skinport.com/v1/items',
                'params': {
                    'app_id': 730,
                    'currency': 'USD',
                    'tradable': 1,
                    'search': clean_skin_name_for_url(skin_name)
                }
            },
            # Method 2: Direct market hash name
            {
                'url': 'https://api.skinport.com/v1/items',
                'params': {
                    'app_id': 730,
                    'currency': 'USD',
                    'tradable': 1,
                    'market_hash_name': skin_name
                }
            },
            # Method 3: Clean search
            {
                'url': 'https://api.skinport.com/v1/items',
                'params': {
                    'app_id': 730,
                    'currency': 'USD',
                    'tradable': 1,
                    'search': clean_skin_name_for_url(skin_name)
                }
            }
        ]
        
        headers = get_headers()
        if API_KEYS.get('skinport'):
            headers['Authorization'] = f"Bearer {API_KEYS['skinport']}"
        
        for attempt_num, api_call in enumerate(api_attempts, 1):
            try:
                print(f"    Attempt {attempt_num}: {api_call['params']}")
                response = requests.get(api_call['url'], params=api_call['params'], headers=headers, timeout=15)
                
                print(f"    Response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"    Response data length: {len(data) if data else 0}")
                    
                    if data and len(data) > 0:
                        listings = []
                        for item in data[:5]:  # Get top 5 listings
                            try:
                                price = item.get('suggested_price', item.get('price', 0))
                                if isinstance(price, (int, float)):
                                    if price > 100:  # Assume it's in cents
                                        price = price / 100
                                    
                                    listings.append({
                                        'price': float(price),
                                        'float': item.get('float_value', item.get('float')),
                                        'url': f"https://skinport.com/item/{item.get('id', 'unknown')}",
                                        'wear': item.get('exterior', item.get('wear_name', 'Unknown')),
                                        'id': item.get('id', 'unknown'),
                                        'stickers': item.get('stickers', []),
                                        'screenshot': item.get('screenshot', '')
                                    })
                            except (ValueError, TypeError) as e:
                                print(f"    Error parsing item: {e}")
                                continue
                        
                        if listings:
                            print(f"  ✅ Found {len(listings)} Skinport listings")
                            return listings
                        
                elif response.status_code == 400:
                    print(f"  ⚠️ Skinport API method {attempt_num} returned 400, trying next...")
                    continue
                elif response.status_code == 429:
                    print(f"  ⚠️ Skinport API rate limited, waiting longer...")
                    time.sleep(15 + random.uniform(0, 10))
                    continue
                else:
                    print(f"  ❌ Skinport API method {attempt_num}: HTTP {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                print(f"  ❌ Skinport API method {attempt_num} request error: {e}")
                continue
        
        print("  ❌ All Skinport API methods failed, trying web scraping...")
        return get_skinport_listings_web_scraping(skin_name)
        
    except Exception as e:
        print(f"[Skinport Error] {skin_name}: {e}")
        return get_skinport_listings_web_scraping(skin_name)

def get_csfloat_listings(skin_name):
    """Get listings from CSFloat with comprehensive error handling"""
    try:
        print(f"  🔍 Fetching CSFloat listings...")
        rate_limit_request('csfloat', 2.0)
        
        # Try multiple API approaches
        api_attempts = [
            # Method 1: Market listings endpoint
            {
                'url': 'https://csfloat.com/api/v1/listings',
                'params': {
                    'market_hash_name': skin_name,
                    'limit': 5,
                    'sort_by': 'price',
                    'sort_order': 'asc'
                }
            },
            # Method 2: Search endpoint
            {
                'url': 'https://csfloat.com/api/v1/listings/search',
                'params': {
                    'search': skin_name,
                    'limit': 5,
                    'sort': 'price_asc'
                }
            },
            # Method 3: Alternative search
            {
                'url': 'https://csfloat.com/api/v1/market/search',
                'params': {
                    'query': skin_name.replace('★ ', ''),
                    'limit': 5,
                    'sort_by': 'price',
                    'order': 'asc'
                }
            },
            # Method 4: Updated CSFloat API
            {
                'url': 'https://api.csfloat.com/v1/market/items',
                'params': {
                    'market_hash_name': skin_name,
                    'sort_by': 'price',
                    'order': 'asc',
                    'limit': 5
                }
            }
        ]
        
        headers = get_headers()
        if API_KEYS.get('csfloat'):
            headers['Authorization'] = f"Bearer {API_KEYS['csfloat']}"
        
        for attempt_num, api_call in enumerate(api_attempts, 1):
            try:
                print(f"    Attempt {attempt_num}: {api_call['params']}")
                response = requests.get(api_call['url'], params=api_call['params'], headers=headers, timeout=15)
                
                print(f"    Response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"    Raw response keys: {data.keys() if isinstance(data, dict) else 'List response'}")
                    
                    # Handle different response formats
                    items = []
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        items = data.get('data', data.get('items', data.get('results', data.get('listings', []))))
                    
                    print(f"    Found {len(items)} items")
                    
                    if items and len(items) > 0:
                        listings = []
                        for item in items[:5]:  # Get top 5 listings
                            try:
                                price = item.get('price', item.get('suggested_price', item.get('listing_price', 0)))
                                if isinstance(price, (int, float)):
                                    if price > 100:  # Assume it's in cents
                                        price = price / 100
                                    
                                    listings.append({
                                        'price': float(price),
                                        'float': item.get('float_value', item.get('float', item.get('wear_value'))),
                                        'url': f"https://csfloat.com/item/{item.get('id', item.get('listing_id', 'unknown'))}",
                                        'wear': item.get('wear_name', item.get('exterior', item.get('condition', 'Unknown'))),
                                        'id': item.get('id', item.get('listing_id', 'unknown')),
                                        'stickers': item.get('stickers', []),
                                        'screenshot': item.get('screenshot', item.get('image_url', ''))
                                    })
                            except (ValueError, TypeError) as e:
                                print(f"    Error parsing item: {e}")
                                continue
                        
                        if listings:
                            print(f"  ✅ Found {len(listings)} CSFloat listings")
                            return listings
                
                elif response.status_code == 404:
                    print(f"  ⚠️ CSFloat API method {attempt_num}: Item not found, trying next...")
                    continue
                elif response.status_code == 429:
                    print(f"  ⚠️ CSFloat API rate limited, waiting...")
                    time.sleep(10 + random.uniform(0, 5))
                    continue
                else:
                    print(f"  ❌ CSFloat API method {attempt_num}: HTTP {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                print(f"  ❌ CSFloat API method {attempt_num} request error: {e}")
                continue
        
        print("  ❌ All CSFloat API methods failed")
        
    except Exception as e:
        print(f"[CSFloat Error] {skin_name}: {e}")
    
    return []

def get_bitskins_listings(skin_name):
    """Get listings from BitSkins (if API available)"""
    try:
        print(f"  🔍 Fetching BitSkins listings...")
        rate_limit_request('bitskins', 2.0)
        
        # BitSkins API endpoint (requires API key)
        url = "https://bitskins.com/api/v1/get_inventory_on_sale/"
        params = {
            'app_id': 730,
            'market_hash_name': skin_name,
            'sort_by': 'price',
            'order': 'asc'
        }
        
        headers = get_headers()
        if API_KEYS.get('bitskins'):
            params['api_key'] = API_KEYS['bitskins']
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success' and data.get('data'):
                items = data['data']['items'][:5]  # Top 5
                listings = []
                
                for item in items:
                    try:
                        listings.append({
                            'price': float(item.get('price', 0)),
                            'float': item.get('float_value'),
                            'url': f"https://bitskins.com/view_item?item_id={item.get('item_id', 'unknown')}",
                            'wear': item.get('exterior', 'Unknown'),
                            'id': item.get('item_id', 'unknown'),
                            'stickers': item.get('stickers', []),
                            'screenshot': item.get('image', '')
                        })
                    except (ValueError, TypeError):
                        continue
                
                if listings:
                    print(f"  ✅ Found {len(listings)} BitSkins listings")
                    return listings
        
    except Exception as e:
        print(f"  ❌ BitSkins Error: {e}")
    
    return []

def get_dmarket_listings(skin_name):
    """Get listings from DMarket with fixed parameters"""
    try:
        print(f"  🔍 Fetching DMarket listings...")
        rate_limit_request('dmarket', 2.0)
        
        # DMarket API endpoint with corrected parameters
        url = "https://api.dmarket.com/exchange/v1/market/items"
        params = {
            'side': 'market',
            'orderBy': 'price',
            'orderDir': 'asc',
            'title': skin_name,
            'priceFrom': 0,
            'priceTo': 50000,  # $500 max in cents
            'gameId': 'a8db3d44-6c42-4b44-b9c3-e1dff1a9ed3c',  # CS:GO game ID
            'currency': 'USD',
            'platform': 'browser',
            'limit': 5
        }
        
        headers = get_headers()
        headers.update({
            'Accept': 'application/json',
            'Origin': 'https://dmarket.com',
            'Referer': 'https://dmarket.com/'
        })
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        print(f"    DMarket Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('objects'):
                listings = []
                
                for item in data['objects'][:5]:
                    try:
                        # DMarket prices are in cents
                        price_cents = item.get('price', {}).get('USD', 0)
                        if price_cents > 0:
                            price_usd = float(price_cents) / 100
                            
                            listings.append({
                                'price': price_usd,
                                'float': item.get('extra', {}).get('floatValue'),
                                'url': f"https://dmarket.com/ingame-items/item-detail/{item.get('itemId', 'unknown')}",
                                'wear': item.get('extra', {}).get('exterior', 'Unknown'),
                                'id': item.get('itemId', 'unknown'),
                                'stickers': item.get('extra', {}).get('stickers', []),
                                'screenshot': item.get('image', '')
                            })
                    except (ValueError, TypeError, KeyError):
                        continue
                
                if listings:
                    print(f"  ✅ Found {len(listings)} DMarket listings")
                    return listings
            else:
                print(f"    DMarket: No objects in response")
                
        elif response.status_code == 429:
            print(f"  ⚠️ DMarket API rate limited, waiting...")
            time.sleep(15)
        else:
            print(f"  ❌ DMarket: HTTP {response.status_code}")
            print(f"  Response: {response.text[:200]}")
                    
    except Exception as e:
        print(f"  ❌ DMarket Error: {e}")
    
    return []

def calculate_profit_margin(market_price, reference_price, platform="Unknown"):
    """Calculate if the deal is profitable (market price <= 90% of reference price)"""
    if not reference_price or reference_price == 0 or not market_price or market_price == 0:
        return False, 0, 0
    
    target_price = reference_price * 0.9  # 90% of reference price
    profit_potential = reference_price - market_price
    
    # Avoid division by zero
    if market_price > 0:
        profit_percentage = ((reference_price - market_price) / market_price) * 100
    else:
        profit_percentage = 0
    
    is_profitable = market_price <= target_price
    
    return is_profitable, profit_potential, profit_percentage

def calculate_roi(purchase_price, sell_price, fees_percentage=0.15):
    """Calculate return on investment accounting for platform fees"""
    if not purchase_price or purchase_price == 0:
        return 0
    
    net_sell_price = sell_price * (1 - fees_percentage)  # After fees
    roi = ((net_sell_price - purchase_price) / purchase_price) * 100
    return roi

def alert_profitable_deal(skin_name, platform, listing, reference_info, profit_potential, profit_percentage):
    """Alert when a profitable deal is found"""
    print(f"\n" + "="*60)
    print(f"🚨💰 PROFITABLE DEAL FOUND! 💰🚨")
    print(f"="*60)
    print(f"📦 Skin: {skin_name}")
    print(f"🏪 Platform: {platform}")
    print(f"💲 Market Price: ${listing['price']:.2f}")
    print(f"📊 Reference Price: ${reference_info['price_usd']:.2f}")
    print(f"🎯 Float Value: {listing.get('float', 'N/A')}")
    print(f"👕 Wear: {listing.get('wear', 'N/A')}")
    print(f"💰 Profit Potential: ${profit_potential:.2f} ({profit_percentage:.1f}%)")
    
    # Calculate ROI with typical platform fees
    roi = calculate_roi(listing['price'], reference_info['price_usd'])
    print(f"📈 ROI (after 15% fees): {roi:.1f}%")
    
    print(f"🛒 BUY NOW: {listing['url']}")
    print(f"📈 Reference: {reference_info['url']}")
    
    # Add sticker info if available
    if listing.get('stickers'):
        print(f"🏷️  Stickers: {len(listing['stickers'])} stickers")
    
    print(f"="*60)
    
    # Sound alert - triple beep for profit
    try:
        if winsound:
            for i in range(3):
                winsound.Beep(1200, 300)
                time.sleep(0.1)
        else:
            print("🔊🔊🔊 PROFIT ALERT! 🔊🔊🔊")
    except:
        print("🔊🔊🔊 PROFIT ALERT! 🔊🔊🔊")

def check_skin_arbitrage(skin_name):
    """Main function to check arbitrage opportunities for a skin"""
    print(f"\n{'='*60}")
    print(f"🔍 ANALYZING: {skin_name}")
    print(f"{'='*60}")
    
    # Get reference price from Steam Market or other sources
    reference_info = get_reference_price(skin_name)
    if not reference_info:
        print(f"❌ Could not get reference price for {skin_name}")
        print(f"⚠️ Skipping arbitrage check...")
        return False
    
    print(f"📊 Reference Price: ${reference_info['price_usd']:.2f} USD")
    target_price = reference_info['price_usd'] * 0.9
    print(f"🎯 Target Price (90%): ${target_price:.2f} USD")
    print(f"💰 Looking for deals under ${target_price:.2f} with $2+ profit...")
    
    profitable_found = False
    
    # List of platforms to check
    platforms = [
        ("Skinport", get_skinport_listings_complete),
        ("CSFloat", get_csfloat_listings),
        ("BitSkins", get_bitskins_listings),
        ("DMarket", get_dmarket_listings)
    ]
    
    for platform_name, get_listings_func in platforms:
        print(f"\n🏪 CHECKING {platform_name.upper()}:")
        print("-" * 40)
        
        listings = get_listings_func(skin_name)
        
        if listings:
            for i, listing in enumerate(listings, 1):
                is_profitable, profit_potential, profit_percentage = calculate_profit_margin(
                    listing['price'], reference_info['price_usd'], platform_name
                )
                
                status = "✅ PROFITABLE!" if (is_profitable and profit_potential > 2) else "❌ Not profitable"
                float_info = f"Float: {listing.get('float', 'N/A')}"
                sticker_info = f"Stickers: {len(listing.get('stickers', []))}" if listing.get('stickers') else ""
                
                print(f"  [{i}] ${listing['price']:.2f} | {float_info} | {sticker_info} | {status}")
                
                if is_profitable and profit_potential > 2:  # At least $2 profit
                    alert_profitable_deal(skin_name, platform_name, listing, reference_info, profit_potential, profit_percentage)
                    save_opportunity_to_log(skin_name, platform_name, listing, reference_info, profit_potential)
                    profitable_found = True
        else:
            print(f"  ❌ No {platform_name} listings found")
    
    # Summary
    if not profitable_found:
        print(f"\n❌ No profitable deals found for {skin_name}")
    else:
        print(f"\n✅ Found profitable opportunities for {skin_name}!")
    
    return profitable_found

def save_opportunity_to_log(skin_name, platform, listing, reference_info, profit_potential):
    """Save profitable opportunities to a log file"""
    try:
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        log_entry = {
            'timestamp': timestamp,
            'skin': skin_name,
            'platform': platform,
            'market_price': listing['price'],
            'reference_price': reference_info['price_usd'],
            'profit_potential': profit_potential,
            'url': listing['url'],
            'float': listing.get('float'),
            'wear': listing.get('wear')
        }
        
        with open('arbitrage_opportunities.json', 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
            
    except Exception as e:
        print(f"Error saving to log: {e}")

def display_statistics(total_opportunities, cycle_count, start_time):
    """Display bot statistics"""
    runtime = time.time() - start_time
    runtime_hours = runtime / 3600
    avg_opportunities_per_hour = total_opportunities / runtime_hours if runtime_hours > 0 else 0
    
    print(f"\n📊 BOT STATISTICS")
    print(f"⏱️  Runtime: {runtime_hours:.2f} hours")
    print(f"🔄 Cycles completed: {cycle_count}")
    print(f"💰 Total opportunities: {total_opportunities}")
    print(f"📈 Avg opportunities/hour: {avg_opportunities_per_hour:.2f}")

def test_skinport_api():
    """Test the Skinport API fix"""
    print("="*50)
    print("🧪 TESTING SKINPORT API FIX")
    print("="*50)
    
    test_skins = [
        "AK-47 | Redline (Field-Tested)",
        "AWP | Dragon Lore (Field-Tested)",
        "Glock-18 | Water Elemental (Field-Tested)"
    ]
    
    for skin in test_skins:
        print(f"\n🔍 Testing: {skin}")
        listings = get_skinport_listings_complete(skin)
        
        if listings:
            print(f"✅ Success! Found {len(listings)} listings")
            for i, listing in enumerate(listings, 1):
                print(f"  [{i}] ${listing['price']:.2f} - {listing['wear']} - Float: {listing.get('float', 'N/A')}")
        else:
            print(f"❌ No listings found")

def main():
    """Main loop with enhanced monitoring"""
    print("="*70)
    print("🤖 CS:GO SKIN ARBITRAGE BOT v3.0 (COMPLETE RESTORATION)")
    print("="*70)
    print("💡 Strategy: Find skins ≤90% of reference market prices")
    print("💰 Minimum profit threshold: $2.00")
    print("📊 Reference source: Buff163 + Steam Market + fallbacks")
    print("🏪 Target platforms: Skinport + CSFloat + BitSkins + DMarket")
    print("🔄 Monitoring cycle: 90 seconds")
    print("📝 Logging: arbitrage_opportunities.json")
    print("🎲 Enhanced rate limiting and randomized requests")
    print("🔧 Web scraping fallbacks for failed APIs")
    print("="*70)
    
    cycle = 1
    total_opportunities = 0
    start_time = time.time()
    
    try:
        while True:
            cycle_start = time.time()
            print(f"\n🔄 CYCLE #{cycle} STARTING - {time.strftime('%H:%M:%S')}")
            print(f"📈 Total opportunities found so far: {total_opportunities}")
            
            cycle_opportunities = 0
            
            for i, skin in enumerate(skins, 1):
                print(f"\n[{i}/{len(skins)}] Processing: {skin}")
                if check_skin_arbitrage(skin):
                    cycle_opportunities += 1
                    total_opportunities += 1
                
                # Random delay between skins to look more human
                time.sleep(random.uniform(5, 10))
            
            cycle_duration = time.time() - cycle_start
            
            print(f"\n" + "="*70)
            print(f"⏱️ CYCLE #{cycle} COMPLETE")
            print(f"🕒 Duration: {cycle_duration:.1f} seconds")
            print(f"🎯 Opportunities this cycle: {cycle_opportunities}")
            print(f"📊 Total opportunities: {total_opportunities}")
            
            # Display extended statistics every 10 cycles
            if cycle % 10 == 0:
                display_statistics(total_opportunities, cycle, start_time)
            
            print(f"⏰ Next cycle in 90 seconds...")
            print("="*70)
            
            cycle += 1
            time.sleep(90)  # Wait 90 seconds between cycles
            
    except KeyboardInterrupt:
        print(f"\n🛑 Bot stopped by user after {cycle-1} cycles")
        print(f"📊 Total opportunities found: {total_opportunities}")
        display_statistics(total_opportunities, cycle-1, start_time)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print(f"📊 Total opportunities found before crash: {total_opportunities}")
        display_statistics(total_opportunities, cycle-1, start_time)

def test_single_skin(skin_name):
    """Test function to check a single skin manually"""
    print("="*70)
    print("🧪 SINGLE SKIN TEST MODE")
    print("="*70)
    
    result = check_skin_arbitrage(skin_name)
    
    if result:
        print(f"\n✅ Test completed - Found opportunities for {skin_name}")
    else:
        print(f"\n❌ Test completed - No opportunities for {skin_name}")

def add_skin_to_monitor(skin_name):
    """Add a new skin to the monitoring list"""
    if skin_name not in skins:
        skins.append(skin_name)
        print(f"✅ Added '{skin_name}' to monitoring list")
        print(f"📊 Now monitoring {len(skins)} skins total")
    else:
        print(f"⚠️ '{skin_name}' is already being monitored")

def remove_skin_from_monitor(skin_name):
    """Remove a skin from the monitoring list"""
    if skin_name in skins:
        skins.remove(skin_name)
        print(f"✅ Removed '{skin_name}' from monitoring list")
        print(f"📊 Now monitoring {len(skins)} skins total")
    else:
        print(f"⚠️ '{skin_name}' is not in the monitoring list")

def list_monitored_skins():
    """Display all currently monitored skins"""
    print("="*70)
    print("📋 CURRENTLY MONITORED SKINS")
    print("="*70)
    
    for i, skin in enumerate(skins, 1):
        print(f"  [{i}] {skin}")
    
    print(f"\n📊 Total: {len(skins)} skins")
    print("="*70)

def interactive_mode():
    """Interactive mode for manual control"""
    print("="*70)
    print("🎮 INTERACTIVE MODE")
    print("="*70)
    print("Commands:")
    print("  1. test <skin_name> - Test a single skin")
    print("  2. add <skin_name> - Add skin to monitoring")
    print("  3. remove <skin_name> - Remove skin from monitoring")
    print("  4. list - Show all monitored skins")
    print("  5. start - Start automatic monitoring")
    print("  6. quit - Exit program")
    print("="*70)
    
    while True:
        try:
            command = input("\n🎮 Enter command: ").strip().lower()
            
            if command.startswith('test '):
                skin_name = command[5:].strip()
                if skin_name:
                    test_single_skin(skin_name)
                else:
                    print("❌ Please provide a skin name")
            
            elif command.startswith('add '):
                skin_name = command[4:].strip()
                if skin_name:
                    add_skin_to_monitor(skin_name)
                else:
                    print("❌ Please provide a skin name")
            
            elif command.startswith('remove '):
                skin_name = command[7:].strip()
                if skin_name:
                    remove_skin_from_monitor(skin_name)
                else:
                    print("❌ Please provide a skin name")
            
            elif command == 'list':
                list_monitored_skins()
            
            elif command == 'start':
                print("🚀 Starting automatic monitoring...")
                main()
                break
            
            elif command in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            else:
                print("❌ Unknown command. Type 'start' to begin monitoring or 'quit' to exit.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

def load_config():
    """Load configuration from file if it exists"""
    try:
        with open('bot_config.json', 'r') as f:
            config = json.load(f)
            
        global skins
        if config.get('skins'):
            skins = config['skins']
            print(f"✅ Loaded {len(skins)} skins from config")
            
        return config
    except FileNotFoundError:
        print("📝 No config file found, using defaults")
        return {}
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return {}

def save_config():
    """Save current configuration to file"""
    try:
        config = {
            'skins': skins,
            'last_updated': time.strftime('%Y-%m-%d %H:%M:%S'),
            'api_keys': {k: '***' if v else None for k, v in API_KEYS.items()}  # Don't save actual keys
        }
        
        with open('bot_config.json', 'w') as f:
            json.dump(config, f, indent=2)
            
        print("✅ Configuration saved")
    except Exception as e:
        print(f"❌ Error saving config: {e}")

def check_platform_status():
    """Check if all trading platforms are accessible"""
    print("="*70)
    print("🔍 PLATFORM STATUS CHECK")
    print("="*70)
    
    platforms = [
        ("Steam Market", "https://steamcommunity.com/market/"),
        ("Skinport", "https://skinport.com/"),
        ("CSFloat", "https://csfloat.com/"),
        ("BitSkins", "https://bitskins.com/"),
        ("DMarket", "https://dmarket.com/"),
        ("Buff163", "https://buff.163.com/"),
        ("SteamLytics", "https://steamlytics.xyz/"),
        ("Pricempire", "https://pricempire.com/"),
        ("CSGOStash", "https://csgostash.com/")
    ]
    
    for platform_name, url in platforms:
        try:
            response = requests.get(url, headers=get_headers(), timeout=10)
            status = "✅ Online" if response.status_code == 200 else f"⚠️ HTTP {response.status_code}"
            print(f"  {platform_name}: {status}")
        except Exception as e:
            print(f"  {platform_name}: ❌ Error - {str(e)[:50]}...")
    
    print("="*70)

def setup_api_keys():
    """Interactive setup for API keys"""
    print("="*70)
    print("🔑 API KEY SETUP")
    print("="*70)
    print("To improve success rates, you can add API keys:")
    print("1. Skinport API: https://skinport.com/api")
    print("2. CSFloat API: https://csfloat.com/api")  
    print("3. Steam Web API: https://steamcommunity.com/dev/apikey")
    print("4. BitSkins API: https://bitskins.com/api")
    print("5. DMarket API: https://dmarket.com/docs")
    print("="*70)
    
    for platform in API_KEYS:
        current = API_KEYS[platform]
        if current:
            print(f"✅ {platform.capitalize()}: Already set")
        else:
            key = input(f"Enter {platform.capitalize()} API key (or press Enter to skip): ").strip()
            if key:
                API_KEYS[platform] = key
                print(f"✅ {platform.capitalize()} API key saved")

def startup_banner():
    """Display startup banner with options"""
    print("="*70)
    print("🤖 CS:GO SKIN ARBITRAGE BOT v3.0 (COMPLETE RESTORATION)")
    print("="*70)
    print("🎯 FEATURES:")
    print("  • Multi-platform price monitoring (9 sources)")
    print("  • Real-time arbitrage detection")
    print("  • Profitable deal alerts with sound")
    print("  • Comprehensive logging system")
    print("  • Interactive controls and testing")
    print("  • Enhanced rate limiting")
    print("  • Randomized request patterns")
    print("  • Web scraping fallbacks")
    print("  • CloudFlare bypass capabilities")
    print("  • API key support for better access")
    print("="*70)
    print("🚀 STARTUP OPTIONS:")
    print("  1. start - Begin automatic monitoring")
    print("  2. interactive - Manual control mode")
    print("  3. status - Check platform availability")
    print("  4. config - Load/save configuration")
    print("  5. test - Test with sample skin")
    print("  6. setup - Configure API keys")
    print("  7. skinport-test - Test Skinport API specifically")
    print("="*70)

def check_dependencies():
    """Check if required dependencies are installed"""
    missing_deps = []
    
    try:
        import cloudscraper
    except ImportError:
        missing_deps.append('cloudscraper')
    
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        missing_deps.append('beautifulsoup4')
    
    if missing_deps:
        print("❌ Missing dependencies:")
        for dep in missing_deps:
            print(f"   - {dep}")
        print("\n🔧 Install with: pip install " + " ".join(missing_deps))
        return False
    
    return True

def run_comprehensive_test():
    """Run comprehensive test of all systems"""
    print("="*70)
    print("🧪 COMPREHENSIVE SYSTEM TEST")
    print("="*70)
    
    test_skin = "AK-47 | Redline (Field-Tested)"
    
    print(f"Testing with: {test_skin}")
    print("-" * 50)
    
    # Test reference price sources
    print("🔍 Testing reference price sources...")
    reference_price = get_reference_price(test_skin)
    if reference_price:
        print(f"✅ Reference price obtained: ${reference_price['price_usd']:.2f}")
    else:
        print("❌ Could not obtain reference price")
    
    print("\n🏪 Testing marketplace APIs...")
    
    # Test each platform
    platforms = [
        ("Skinport", get_skinport_listings_complete),
        ("CSFloat", get_csfloat_listings),
        ("BitSkins", get_bitskins_listings),
        ("DMarket", get_dmarket_listings)
    ]
    
    for platform_name, get_listings_func in platforms:
        print(f"\n  Testing {platform_name}...")
        listings = get_listings_func(test_skin)
        if listings:
            print(f"  ✅ {platform_name}: Found {len(listings)} listings")
            for i, listing in enumerate(listings[:3], 1):
                print(f"    [{i}] ${listing['price']:.2f} - {listing.get('wear', 'N/A')}")
        else:
            print(f"  ❌ {platform_name}: No listings found")
    
    print("\n" + "="*70)
    print("🧪 Test completed!")

if __name__ == "__main__":
    # Check dependencies first
    if not check_dependencies():
        exit(1)
    
    config = load_config()
    startup_banner()
    
    try:
        choice = input("🎮 Select option (1-7): ").strip()
        
        if choice == '1' or choice == 'start':
            main()
        elif choice == '2' or choice == 'interactive':
            interactive_mode()
        elif choice == '3' or choice == 'status':
            check_platform_status()
        elif choice == '4' or choice == 'config':
            save_config()
            list_monitored_skins()
        elif choice == '5' or choice == 'test':
            test_single_skin("AK-47 | Redline (Field-Tested)")
        elif choice == '6' or choice == 'setup':
            setup_api_keys()
            print("\n🚀 Starting monitoring with configured API keys...")
            main()
        elif choice == '7' or choice == 'skinport-test':
            test_skinport_api()
        elif choice == 'comprehensive' or choice == 'full-test':
            run_comprehensive_test()
        else:
            print("🚀 Starting automatic monitoring (default)...")
            main()
            
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Startup error: {e}")
        print("🚀 Falling back to automatic monitoring...")

        main()
