import cloudscraper
from bs4 import BeautifulSoup
import json
import re
import time
import os
import argparse
from random import uniform
from InventoryAPI import get_filtered_inventory


# Define prices for robot parts
PART_PRICES = {
    'Unique Killstreak Item': {'ref': 15.00, 'gbp': 0.35},
    'Unique Specialized Killstreak Item': {'ref': 33.00, 'gbp': 0.84},
    'Battle-Worn Robot Money Furnace': {'ref': 1.11, 'gbp': 0.03},
    'Battle-Worn Robot Taunt Processor': {'ref': 1.11, 'gbp': 0.03},
    'Battle-Worn Robot KB-808': {'ref': 1.11, 'gbp': 0.03},
    'Reinforced Robot Humor Suppression Pump': {'ref': 0.11, 'gbp': 0.02},
    'Reinforced Robot Emotion Detector': {'ref': 0.11, 'gbp': 0.02},
    'Reinforced Robot Bomb Stabilizer': {'ref': 0.11, 'gbp': 0.02},
    'Pristine Robot Currency Digester': {'ref': 2.55, 'gbp': 0.09},
    'Pristine Robot Brainstorm Bulb': {'ref': 2.55, 'gbp': 0.09}
}

REF_TO_GBP = 0.03
MAX_RETRIES = 3
KEY_PRICE = 59.11
DEFAULT_STEAM_ID = "1111111"

def extract_inputs_from_descriptions(descriptions):
    inputs = {}
    collecting_inputs = False
    
    for desc in descriptions:
        text = desc.get('value', '').strip()
        
        if "The following are the inputs" in text:
            collecting_inputs = True
            continue
        elif "You will receive" in text:
            break
            
        if collecting_inputs and 'x ' in text:
            try:
                item_name = text.split(' x ')[0].strip()
                quantity = int(text.split(' x ')[1].strip())
                inputs[item_name] = quantity
            except:
                continue
    
    return inputs

def get_fabricator_inputs(weapon_name, killstreak_type="Specialized Killstreak"):
    formatted_name = weapon_name.replace(" ", "%20")
    url = f"https://steamcommunity.com/market/listings/440/{killstreak_type}%20{formatted_name}%20Kit%20Fabricator"
    
    print(f"\nFetching fabricator inputs from: {url}")
    
    for attempt in range(MAX_RETRIES):
        try:
            browsers = ['chrome', 'firefox', 'safari']
            scraper = cloudscraper.create_scraper(browser=browsers[attempt % len(browsers)])
            response = scraper.get(url)
            
            assets_match = re.search(r'var g_rgAssets = (.+?)};', response.text, re.DOTALL)
            if assets_match:
                assets_json = assets_match.group(1) + "}"
                assets_data = json.loads(assets_json)
                
                tf2_data = assets_data.get('440', {})
                context_data = tf2_data.get('2', {})
                
                if context_data:
                    first_item = next(iter(context_data.values()))
                    descriptions = first_item.get('descriptions', [])
                    inputs = extract_inputs_from_descriptions(descriptions)
                    
                    if inputs:
                        return inputs
            
            print(f"Attempt {attempt + 1} failed, retrying...")
            time.sleep(uniform(1, 3))
            
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(uniform(1, 3))
                continue
            else:
                print("Max retries reached. Please try again later.")
                return None
    
    return None

def calculate_total_cost(inputs):
    if not inputs:
        return 0, 0
        
    total_ref = 0
    total_gbp = 0
    
    print("\nCalculating costs:")
    print(f"{'Item':<40} {'Quantity':<8} {'Cost (ref)':<12} {'Cost (£)':<12}")
    print("-" * 72)
    
    for item, quantity in inputs.items():
        if item in PART_PRICES:
            ref_cost = PART_PRICES[item]['ref'] * quantity
            gbp_cost = PART_PRICES[item]['gbp'] * quantity
            total_ref += ref_cost
            total_gbp += gbp_cost
            print(f"{item:<40} {quantity:<8} {ref_cost:>8.2f} ref  £{gbp_cost:>8.2f}")
        else:
            print(f"Warning: Price not found for {item}")
    
    print("-" * 72)
    print(f"{'TOTAL:':<40} {' ':<8} {total_ref:>8.2f} ref  £{total_gbp:>8.2f}")
    
    return total_ref, total_gbp

def get_key_price():
    """Get key price, using constant if defined"""
    if KEY_PRICE is not None:
        return KEY_PRICE
        
    url = "https://backpack.tf/stats/Unique/Mann%20Co.%20Supply%20Crate%20Key/Tradable/Craftable"
    
    for attempt in range(MAX_RETRIES):
        try:
            browsers = ['chrome', 'firefox']
            scraper = cloudscraper.create_scraper(browser=browsers[attempt % len(browsers)])
            response = scraper.get(url)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            sell_orders_header = soup.find('h4', string='Sell Orders')
            
            if sell_orders_header:
                sell_orders_section = sell_orders_header.find_parent('div')
                if sell_orders_section:
                    listings = sell_orders_section.find_all('li', class_='listing')
                    lowest_price = float('inf')
                    
                    for listing in listings:
                        item_div = listing.find('div', class_='item')
                        if item_div:
                            listing_price = item_div.get('data-listing_price', '0')
                            if listing_price and 'ref' in listing_price:
                                try:
                                    price = float(listing_price.replace(' ref', ''))
                                    lowest_price = min(lowest_price, price)
                                except ValueError:
                                    continue
                    
                    if lowest_price != float('inf'):
                        return lowest_price
            
            print(f"Attempt {attempt + 1} failed to get key price, retrying...")
            time.sleep(uniform(1, 3))
            
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(uniform(1, 3))
                continue
    
    print("Could not fetch key price, using default of 55 ref")
    return 60.0  # Default fallback price

def parse_price(price_str, key_price=None):
    """Parse a price string that might contain keys and ref"""
    if not price_str:
        return 0.0
        
    total_ref = 0.0
    price_str = price_str.lower().strip()
    
    # If price contains "keys" or "key"
    if 'key' in price_str:
        if key_price is None:
            key_price = get_key_price()
            
        # Handle both "X keys" and "X keys, Y ref" formats
        parts = price_str.replace('keys', 'key').split('key,')
        
        # Get number of keys
        try:
            keys = float(parts[0].strip())
            total_ref += keys * key_price
        except ValueError:
            return 0.0
        
        # Add remaining ref if any
        if len(parts) > 1 and 'ref' in parts[1]:
            try:
                ref = float(parts[1].replace('ref', '').strip())
                total_ref += ref
            except ValueError:
                pass
                
    # If price only contains ref
    elif 'ref' in price_str:
        try:
            total_ref = float(price_str.replace('ref', '').strip())
        except ValueError:
            return 0.0
            
    return total_ref

def get_highest_buy_price(weapon_name, killstreak_type):
    """Get highest buy price, handling both ref and key prices"""
    formatted_name = weapon_name.replace(" ", "%20")
    url = f"https://backpack.tf/stats/Unique/{killstreak_type}%20{formatted_name}/Tradable/Craftable"
    
    for attempt in range(MAX_RETRIES):
        try:
            browsers = ['chrome', 'firefox']
            scraper = cloudscraper.create_scraper(browser=browsers[attempt % len(browsers)])
            response = scraper.get(url)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            buy_orders_header = soup.find('h4', string='Buy Orders')
            
            if buy_orders_header:
                buy_orders_section = buy_orders_header.find_parent('div')
                if buy_orders_section:
                    listings = buy_orders_section.find_all('li', class_='listing')
                    highest_price_ref = 0
                    key_price = None  # We'll get key price only if needed
                    
                    for listing in listings:
                        item_div = listing.find('div', class_='item')
                        # Check all possible spell-related attributes
                        has_spells = any(attr for attr in item_div.attrs if 'spell' in attr.lower())
                        
                        if item_div and not has_spells:
                            listing_price = item_div.get('data-listing_price', '0')
                            if listing_price:
                                # Get key price only when we first encounter a key-based price
                                if 'key' in listing_price.lower() and key_price is None:
                                    key_price = get_key_price()
                                
                                try:
                                    price_in_ref = parse_price(listing_price, key_price)
                                    highest_price_ref = max(highest_price_ref, price_in_ref)
                                except ValueError:
                                    continue
                    
                    return highest_price_ref if highest_price_ref > 0 else None
            
            print(f"Attempt {attempt + 1} failed, retrying...")
            time.sleep(uniform(1, 3))
            
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(uniform(1, 3))
                continue
            else:
                print("Max retries reached. Please try again later.")
                return None
    
    return None

def extract_weapon_name(fabricator_name):
    """Modified to handle all killstreak fabricator formats"""
    # Updated patterns to be more comprehensive
    patterns = [
        r"(Professional|Specialized|) ?Killstreak (.*?) Kit Fabricator$",
        r"(Professional|Specialized|) ?Killstreak Fabricator - (.*?)$"
    ]
    
    for pattern in patterns:
        match = re.match(pattern, fabricator_name, re.IGNORECASE)
        if match:
            if len(match.groups()) == 2:
                # Clean up and standardize the killstreak type
                killstreak_type = match.group(1).strip()
                if killstreak_type == "":
                    killstreak_type = "Killstreak"
                else:
                    killstreak_type = f"{killstreak_type} Killstreak"
                
                weapon_name = match.group(2).strip()
                return weapon_name, killstreak_type
    
    # Try one more pattern for direct format
    direct_match = re.match(r"(Professional Killstreak|Specialized Killstreak|Killstreak) (.*) Kit Fabricator$", fabricator_name)
    if direct_match:
        return direct_match.group(2).strip(), direct_match.group(1)
    
    print(f"Debug: Could not parse fabricator name: {fabricator_name}")
    return None, None

def calculate_total_cost(inputs):
    """Modified to handle the new format"""
    if not inputs:
        return 0, 0, {}
        
    total_ref = 0
    total_gbp = 0
    items_cost = {}
    key_price = get_key_price()
    
    print("\nCalculating costs:")
    print(f"{'Item':<40} {'Quantity':<8} {'Cost (ref)':<12} {'Cost (£)':<12}")
    print("-" * 72)
    
    for item, quantity in inputs.items():
        if item in PART_PRICES:
            ref_cost = PART_PRICES[item]['ref'] * quantity
            gbp_cost = PART_PRICES[item]['gbp'] * quantity
            items_cost[item] = {'quantity': quantity, 'ref': ref_cost}
        else:
            print(f"Warning: Price not found for {item}")
            continue
            
        total_ref += ref_cost
        total_gbp += gbp_cost
        print(f"{item:<40} {quantity:<8} {ref_cost:>8.2f} ref  £{gbp_cost:>8.2f}")
    
    print("-" * 72)
    print(f"{'TOTAL:':<40} {' ':<8} {total_ref:>8.2f} ref  £{total_gbp:>8.2f}")
    print(f"Current key price: {key_price:.2f} ref")
    
    return total_ref, total_gbp, items_cost

def analyze_fabricator(fabricator_name):
    """Modified to only show key price if keys were involved"""
    weapon_name, killstreak_type = extract_weapon_name(fabricator_name)
    
    if not weapon_name or not killstreak_type:
        print(f"\nSkipping {fabricator_name} - Could not parse weapon name and killstreak type")
        return None
    
    print(f"\n{'='*80}")
    print(f"Analyzing {killstreak_type} fabricator for {weapon_name}")
    print(f"{'='*80}")
    
    inputs = get_fabricator_inputs(weapon_name, killstreak_type)
    
    if not inputs:
        print("Could not retrieve fabricator inputs")
        return None
        
    total_ref, total_gbp, items_cost = calculate_total_cost(inputs)
    highest_buy = get_highest_buy_price(weapon_name, killstreak_type)
    
    if highest_buy is None:
        print("Could not find any valid buy orders")
        return None
        
    profit_ref = highest_buy - total_ref
    profit_gbp = profit_ref * REF_TO_GBP
    roi = (profit_ref/total_ref*100) if total_ref > 0 else 0
    
    print("\n=== Summary ===")
    print(f"Crafting cost:    {total_ref:>8.2f} ref  (£{total_gbp:.2f})")
    
    # Only get and show key price if needed
    key_price = None
    if 'key' in str(highest_buy).lower():
        key_price = get_key_price()
        print(f"Highest buy:      {highest_buy:>8.2f} ref  ({highest_buy/key_price:.2f} keys)")
        print(f"Current key price: {key_price:.2f} ref")
    else:
        print(f"Highest buy:      {highest_buy:>8.2f} ref")
    
    print(f"Potential profit: {profit_ref:>8.2f} ref  (£{profit_gbp:.2f})")
    
    if profit_ref > 0:
        print("\nProfitable to craft!")
        print(f"ROI: {roi:.1f}%")
    else:
        print("\nNot profitable to craft!")
    
    bp_url = get_backpack_tf_url(weapon_name, killstreak_type)
    print(f"\n{bp_url}")
        
    return {
        'fabricator': fabricator_name,
        'weapon': weapon_name,
        'type': killstreak_type,
        'cost_ref': total_ref,
        'cost_gbp': total_gbp,
        'sell_price_ref': highest_buy,
        'sell_price_keys': highest_buy/key_price if key_price else None,
        'profit_ref': profit_ref,
        'profit_gbp': profit_gbp,
        'roi': roi,
        'url': bp_url,
        'items_cost': items_cost,
        'key_price': key_price
    }

def get_backpack_tf_url(weapon_name, killstreak_type):
    """Generate backpack.tf URL for the item"""
    formatted_name = weapon_name.replace(" ", "%20")
    return f"https://backpack.tf/stats/Unique/{killstreak_type}%20{formatted_name}/Tradable/Craftable"

def main(steam_id=None, choice=None, fabricator=None):
    if steam_id is None:
        steam_id = input("\nEnter Steam ID (press Enter to use default): ").strip()
        if not steam_id:
            steam_id = DEFAULT_STEAM_ID
            print(f"Using default Steam ID: {steam_id}")

    print("\nFetching inventory...")
    fabricators = get_filtered_inventory(steam_id, 440, "Recipe")
    
    if not fabricators:
        print("No fabricators found in inventory!")
        return

    killstreak_fabricators = [f for f in fabricators if "Killstreak" in f and "Fabricator" in f]
    
    if not killstreak_fabricators:
        print("No killstreak fabricators found in inventory!")
        return

    # Handle custom fabricator name provided via -f argument
    if fabricator:
        analyze_fabricator(fabricator)
        return

    if choice is None:
        print("\nAvailable Killstreak Fabricators:")
        print("0. Analyze ALL fabricators")
        for i, fabricator in enumerate(killstreak_fabricators, 1):
            print(f"{i}. {fabricator}")
        print("00. Input custom fabricator name")

        while True:
            try:
                choice = input("\nSelect a fabricator (0 for all, 00 for custom): ").strip()
                if choice == "00" or (choice.isdigit() and 0 <= int(choice) <= len(killstreak_fabricators)):
                    break
                print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number or '00'.")
    
    # Handle choice 00 without fabricator name
    if choice == "00" and not fabricator:
        fabricator = input("Enter the full fabricator name: ").strip()
        analyze_fabricator(fabricator)
        return

    choice = int(choice)
    
    if choice == 0:  # Analyze all fabricators
        print("\nAnalyzing all fabricators... This may take a while.")
        results = []
        for fabricator in killstreak_fabricators:
            result = analyze_fabricator(fabricator)
            if result:
                results.append(result)
                
        if results:
            print("\n=== OVERALL SUMMARY ===")
            print("Most Profitable Fabricators:")
            results.sort(key=lambda x: x['roi'], reverse=True)
            
            print(f"\n{'Weapon':<30} {'Type':<25} {'Cost':<15} {'Sell Price':<15} {'Profit':<15} {'ROI':<10}")
            print("-" * 110)
            
            for result in results:
                if result['profit_ref'] > 0:
                    cost_str = f"{result['cost_ref']:.2f} ref"
                    if result['sell_price_keys'] is not None:
                        sell_str = f"{result['sell_price_keys']:.2f} keys"
                    else:
                        sell_str = f"{result['sell_price_ref']:.2f} ref"
                    
                    print(f"{result['weapon']:<30} {result['type']:<25} "
                          f"{cost_str:<15} {sell_str:<15} "
                          f"{result['profit_ref']:>8.2f} ref  {result['roi']:>6.1f}%")
                    print(f"{result['url']}")
                    print("-" * 110)
                    
    else:  # Analyze single fabricator
        selected_fabricator = killstreak_fabricators[choice - 1]
        analyze_fabricator(selected_fabricator)

    if steam_id is None:
        if input("\nAnalyze more fabricators? (y/n): ").lower() == 'y':
            main()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='TF2 Killstreak Kit Fabricator Analyzer')
    parser.add_argument('-uid', '--userid', help='Steam User ID')
    parser.add_argument('-c', '--choice', help='Selection choice (0 for all, 00 for custom)')
    parser.add_argument('-f', '--fabricator', help='Custom fabricator name (when choice is 00)')
    
    args = parser.parse_args()
    
    # Pass all arguments to main function
    main(args.userid, args.choice, args.fabricator)
