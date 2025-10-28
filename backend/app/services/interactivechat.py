import torch
import torch.nn as nn
import os
import pickle
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel
from typing import Optional, Dict, List, Any
import re
from datetime import datetime, timedelta
import csv
import requests
from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
import time

# ---- CONFIG ----
TOP_K_PER_MARKET = 3  # number of latest rows per market to average
MAX_RETRY_ATTEMPTS = 3  # maximum retry attempts for stale elements
WAIT_TIMEOUT = 30  # explicit wait timeout in seconds

# ---------------- Text Classifier Components ----------------
class SentenceEncoder(nn.Module):
    def __init__(self, model_name):
        super().__init__()
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        for param in self.model.parameters():
            param.requires_grad = False
        self.model.eval()

    def forward(self, texts):
        inputs = self.tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
        with torch.no_grad():
            outputs = self.model(**inputs)
        embeddings = mean_pooling(outputs, inputs["attention_mask"])
        return F.normalize(embeddings, p=2, dim=1)

class ClassifierHead(nn.Module):
    def __init__(self, emb_dim=384, hidden_dim=256, num_classes=2, p_dropout=0.2):
        super().__init__()
        self.fc1 = nn.Linear(emb_dim, hidden_dim)
        self.dropout = nn.Dropout(p_dropout)
        self.fc2 = nn.Linear(hidden_dim, num_classes)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        return self.fc2(x)

def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0]
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

class TextClassifierInference:
    def __init__(self, model_dir=r"D:\maxgush_s_application\backend\models\text_classifier"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        with open(os.path.join(model_dir, "config.pkl"), "rb") as f:
            self.config = pickle.load(f)
        with open(os.path.join(model_dir, "label_encoder.pkl"), "rb") as f:
            self.label_encoder = pickle.load(f)
        self.encoder = SentenceEncoder(self.config["MODEL_NAME"]).to(self.device)
        head_kwargs = {
            "emb_dim":     self.config["emb_dim"],
            "hidden_dim":  self.config["hidden_dim"],
            "num_classes": self.config["num_classes"],
        }
        if "p_dropout" in self.config:
            head_kwargs["p_dropout"] = self.config["p_dropout"]
        self.classifier = ClassifierHead(**head_kwargs).to(self.device)
        checkpoint = torch.load(os.path.join(model_dir, "classifier_weights.pth"), map_location=self.device)
        self.classifier.load_state_dict(checkpoint)
        self.classifier.eval()
        print(f"✅ Model loaded successfully!")
        print(f"   Classes: {self.config['classes']}")

    def predict(self, text):
        with torch.no_grad():
            embeddings = self.encoder([text])
            logits = self.classifier(embeddings)
            probabilities = F.softmax(logits, dim=1)
            predicted_class_idx = torch.argmax(logits, dim=1).item()
            predicted_class = self.label_encoder.inverse_transform([predicted_class_idx])[0]
            confidence = probabilities[0][predicted_class_idx].item()
            return {
                "prediction": predicted_class,
                "confidence": confidence,
                "probabilities": {
                    class_name: prob.item()
                    for class_name, prob in zip(self.config['classes'], probabilities[0])
                }
            }

# Initialize the classifier
classifier = TextClassifierInference()

# ---------------- Slot Filler ----------------
class SlotFiller:
    """Slot filler with a pattern-matching feedback loop."""
    def __init__(self,
                 commodity_file: str = r"D:\maxgush_s_application\backend\commodity_mappings.csv",
                 district_file: str = r"D:\maxgush_s_application\backend\up_districts.csv"):
        self.commodity_list, self.commodity_map = self._load_from_csv(commodity_file, "Name", "Code")
        self.up_cities, self.district_map = self._load_from_csv(district_file, "District Name", "District Code")
        self.global_patterns = [
            re.compile(r'\bprice\s+of\s+(?P<commodity>\w+)(?:\s+in\s+(?P<area>[\w\s]+?))?(?:\s+(?:on|for|at)\s*(?P<time>.+))?\b', re.I),
            re.compile(r'^(?P<commodity>\w+)\s+price(?:\s+in\s+(?P<area>[\w\s]+?))?(?:\s+(?:on|for|at)\s*(?P<time>.+))?$', re.I),
            re.compile(r'\bget\s+(?P<commodity>\w+)\s+(?:rates?|prices?)\s+(?:in|for)\s+(?P<area>[\w\s]+?)(?:\s+(?:on|for|at)\s*(?P<time>.+))?\b', re.I),
        ]
        self.slot_patterns = {
            'commodity': [
                lambda t: self._match_from_list(t, self.commodity_list),
                re.compile(r'\bcommodity[:\s]+(?P<commodity>\w+)\b', re.I),
                re.compile(r'\bhow\s+much\s+is\s+(?P<commodity>\w+)\b', re.I),
            ],
            'area': [
                lambda t: self._match_from_list(t, self.up_cities),
                re.compile(r'\b(?:in|at|for)\s+(?P<area>[\w\s]+?)\b', re.I),
            ],
            'time': [
                re.compile(r'\b(?P<time>today|tomorrow|yesterday|now|day after tomorrow|day before yesterday|next week|last week|this week|next month|next year)\b', re.I),
                re.compile(r'(?P<time>\d{4}-\d{2}-\d{2})'),
                re.compile(r'(?P<time>\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'),
            ]
        }

    def _load_from_csv(self, filename: str, name_col: str, code_col: str):
        names, mapping = [], {}
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    name = row[name_col].lower().strip()
                    code = row[code_col].strip()
                    if name:
                        names.append(name)
                        mapping[name] = code
            return names, mapping
        except FileNotFoundError:
            print(f"Warning: {filename} not found. Using empty list.")
            return [], {}

    def _match_from_list(self, text: str, lst: List[str]) -> Optional[str]:
        if not text or not lst:
            return None
        text_low = text.lower()
        matches = []
        for w in lst:
            if re.search(r'\b' + re.escape(w) + r'\b', text_low):
                matches.append(w)
        if not matches:
            return None
        matches.sort(key=lambda x: -len(x))
        return matches[0]

    def normalize_time(self, text: str) -> Optional[str]:
        if not text:
            return None
        today = datetime.now().date()
        t = text.lower().strip()
        if t in ('today','tod','now'):
            return str(today.isoformat())
        if t in ('yesterday','yest'):
            return str((today - timedelta(days=1)).isoformat())
        if t in ('tomorrow','tmw'):
            return str((today + timedelta(days=1)).isoformat())
        if 'day after tomorrow' in t:
            return str((today + timedelta(days=2)).isoformat())
        if 'day before yesterday' in t:
            return str((today - timedelta(days=2)).isoformat())
        m = re.search(r'in\s+(\d+)\s+days?', t)
        if m:
            return str((today + timedelta(days=int(m.group(1)))).isoformat())
        m = re.search(r'in\s+(\d+)\s+weeks?', t)
        if m:
            return str((today + timedelta(weeks=int(m.group(1)))).isoformat())
        if 'next week' in t:
            return str((today + timedelta(weeks=1)).isoformat())
        if 'last week' in t:
            return str((today - timedelta(weeks=1)).isoformat())
        if 'this week' in t:
            return str(today.isoformat())
        m = re.search(r'(\d{4}-\d{2}-\d{2})', t)
        if m:
            return m.group(1)
        m = re.search(r'(\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b)', t)
        if m:
            s = m.group(1)
            parts = re.split(r'[/\-]', s)
            d, mo, y = parts
            if len(y) == 2:
                y = '20' + y
            try:
                dt = datetime(int(y), int(mo), int(d)).date()
                return dt.isoformat()
            except Exception:
                pass
        return None

    def _validate_slot(self, slot: str, value: str) -> bool:
        if not value:
            return False
        if slot == 'commodity':
            return value.lower() in self.commodity_list
        elif slot == 'area':
            return value.lower() in self.up_cities
        elif slot == 'time':
            return self.normalize_time(value) is not None or bool(re.match(r'\d{4}-\d{2}-\d{2}', value))
        return True

    def _get_invalid_slot_message(self, slot: str, value: str) -> str:
        if slot == 'commodity':
            return f"Sorry, '{value}' is not available. Please choose a valid commodity."
        elif slot == 'area':
            return f"Sorry, '{value}' is not a UP city in our database. Please provide a valid UP city."
        elif slot == 'time':
            return f"Sorry, I couldn't understand the date '{value}'. Please provide a valid date (e.g. today, tomorrow, 25/08/2025)."
        return f"Sorry, '{value}' is not valid for {slot}."

    def extract_slots(self, text: str, current_slots: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
        text = text.strip()
        for pat in self.global_patterns:
            m = pat.search(text)
            if m:
                gd = m.groupdict()
                if gd.get('commodity'):
                    cand = gd['commodity'].lower().strip()
                    found = self._match_from_list(cand, self.commodity_list)
                    if found:
                        current_slots['commodity'] = found
                if gd.get('area'):
                    cand = gd['area'].lower().strip()
                    found = self._match_from_list(cand, self.up_cities)
                    if found:
                        current_slots['area'] = found
                if gd.get('time'):
                    norm = self.normalize_time(gd['time'])
                    if norm:
                        current_slots['time'] = norm
                    else:
                        current_slots['time'] = gd['time'].strip()
        for slot, pats in self.slot_patterns.items():
            if current_slots.get(slot):
                continue
            for pat in pats:
                if callable(pat):
                    found = pat(text)
                    if found:
                        if slot == 'time':
                            norm_found = self.normalize_time(found)
                            current_slots[slot] = norm_found or found
                        else:
                            current_slots[slot] = found
                        break
                else:
                    m = pat.search(text)
                    if m:
                        val = (m.group(slot) if slot in m.groupdict() else m.group(1)).strip()
                        if val:
                            if slot == 'time':
                                norm_time = self.normalize_time(val)
                                current_slots[slot] = norm_time or val
                            elif slot == 'area':
                                found = self._match_from_list(val, self.up_cities)
                                current_slots[slot] = found or val.lower()
                            else:
                                current_slots[slot] = val.lower()
                        break
        return current_slots

    def next_missing_slot(self, slots: Dict[str, Optional[str]]) -> Optional[str]:
        for s in ['commodity','area','time']:
            if not slots.get(s):
                return s
        return None

    def prompt_for_slot(self, slot: str) -> str:
        templates = {
            'commodity': "Which commodity are you interested in?",
            'area': "Which UP city are you asking about?",
            'time': "Which date/time are you interested in? (e.g. today, tomorrow, 25/08/2025)",
        }
        return templates.get(slot, f"Please provide {slot}.")

    def _is_affirmative(self, text: str) -> bool:
        return bool(re.search(r'\b(yes|yep|yeah|correct|right|y)\b', text.lower()))

    def _is_negative(self, text: str) -> bool:
        return bool(re.search(r'\b(no|nah|nope|n)\b', text.lower()))

    def handle_message(self, text: str, session_state: Dict[str, Any]) -> Dict[str, Any]:
        session_state.setdefault('slots', {'commodity': None, 'area': None, 'time': None})
        session_state.setdefault('raw_inputs', [])
        session_state.setdefault('expecting', None)
        session_state.setdefault('status', 'new')
        session_state['raw_inputs'].append(text)
        text = text.strip()
        if session_state.get('expecting'):
            slot = session_state['expecting']
            filled = False
            attempted_value = None
            if slot == 'commodity':
                found = self._match_from_list(text, self.commodity_list)
                if found:
                    session_state['slots']['commodity'] = found
                    filled = True
                else:
                    single = text.lower().split()[0]
                    if single in self.commodity_list:
                        session_state['slots']['commodity'] = single
                        filled = True
                    else:
                        attempted_value = text
            elif slot == 'area':
                found = self._match_from_list(text, self.up_cities)
                if found:
                    session_state['slots']['area'] = found
                    filled = True
                else:
                    single = text.lower().strip()
                    if single in self.up_cities:
                        session_state['slots']['area'] = single
                        filled = True
                    else:
                        attempted_value = text
            elif slot == 'time':
                norm = self.normalize_time(text)
                if norm:
                    session_state['slots']['time'] = norm
                    filled = True
                else:
                    attempted_value = text
            session_state['expecting'] = None
            if not filled:
                if self._is_negative(text):
                    prompt = self.prompt_for_slot(slot)
                    session_state['expecting'] = slot
                    session_state['status'] = 'incomplete'
                    return {'session_state': session_state, 'ask': prompt}
                elif attempted_value:
                    error_msg = self._get_invalid_slot_message(slot, attempted_value)
                    prompt = self.prompt_for_slot(slot)
                    session_state['expecting'] = slot
                    session_state['status'] = 'incomplete'
                    return {'session_state': session_state, 'ask': f"{error_msg} {prompt}"}
                else:
                    session_state['slots'] = self.extract_slots(text, session_state['slots'])
        else:
            session_state['slots'] = self.extract_slots(text, session_state['slots'])
        for slot_name, slot_value in session_state['slots'].items():
            if slot_value and not self._validate_slot(slot_name, slot_value):
                session_state['slots'][slot_name] = None
                session_state['expecting'] = slot_name
                session_state['status'] = 'incomplete'
                error_msg = self._get_invalid_slot_message(slot_name, slot_value)
                prompt = self.prompt_for_slot(slot_name)
                return {'session_state': session_state, 'ask': f"{error_msg} {prompt}"}
        missing = self.next_missing_slot(session_state['slots'])
        if missing:
            session_state['expecting'] = missing
            session_state['status'] = 'incomplete'
            prompt = self.prompt_for_slot(missing)
            return {'session_state': session_state, 'ask': prompt}
        session_state['status'] = 'complete'
        session_state['expecting'] = None
        return {'session_state': session_state, 'ask': None, 'slots': session_state['slots']}

# ------------ Scraper Helpers ------------
def extract_market_prices_enhanced(soup, market_name, commodity_name, date):
    """Parse one market table into rows."""
    try:
        table_ids = ['cphBody_GridPriceData', 'DataGrid1', 'gvPriceData']
        table = None
        for table_id in table_ids:
            table = soup.find('table', {'id': table_id})
            if table:
                break
        if not table:
            return None
        rows = table.find_all('tr')
        market_prices = []
        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 6:
                try:
                    row_data = [cell.get_text().strip() for cell in cells]
                    if len(row_data) >= 8 and row_data[1] and row_data[1] != 'Market':
                        market_prices.append({
                            'Market': market_name,
                            'Commodity': commodity_name,
                            'Min Price': row_data[6] if len(row_data) > 6 else 'N/A',
                            'Max Price': row_data[7] if len(row_data) > 7 else 'N/A',
                            'Modal Price': row_data[8] if len(row_data) > 8 else 'N/A',
                            'Date': date
                        })
                except (IndexError, ValueError):
                    continue
        return market_prices if market_prices else None
    except Exception as e:
        print(f"❌ Error extracting prices for {market_name}: {e}")
        return None

def create_city_specific_mock_data(commodity_name, city_name):
    """Mock rows when live data is unavailable."""
    base_prices = {
        'Wheat': 2450, 'Rice': 2800, 'Maize': 1950, 'Potato': 1200,
        'Onion': 1800, 'Tomato': 2500, 'Gram': 5500, 'Arhar': 6200
    }
    base_price = base_prices.get(commodity_name, 2000)
    current_date = datetime.now().strftime('%d-%b-%Y')
    if city_name.lower() == 'lucknow':
        markets_data = [
            {'Market': 'Lucknow', 'Commodity': commodity_name, 'Min Price': base_price-40, 'Max Price': base_price+60, 'Modal Price': base_price+10, 'Date': current_date},
            {'Market': 'Banthara', 'Commodity': commodity_name, 'Min Price': base_price-30, 'Max Price': base_price+70, 'Modal Price': base_price+20, 'Date': current_date},
        ]
    else:
        markets_data = [
            {'Market': f'{city_name} - Main Market', 'Commodity': commodity_name, 'Min Price': base_price-35, 'Max Price': base_price+65, 'Modal Price': base_price+15, 'Date': current_date},
            {'Market': f'{city_name} - Wholesale Market', 'Commodity': commodity_name, 'Min Price': base_price-25, 'Max Price': base_price+75, 'Modal Price': base_price+25, 'Date': current_date},
        ]
    return pd.DataFrame(markets_data)

# ------------ BULLETPROOF SELENIUM HANDLING ------------
def wait_for_page_load_complete(driver, timeout=WAIT_TIMEOUT):
    """Wait for JavaScript page load to complete"""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(2)  # Additional buffer for dynamic content
        return True
    except TimeoutException:
        print("⏳ Page load timeout")
        return False

def robust_element_interaction(driver, locator, action_type="click", value=None, timeout=WAIT_TIMEOUT):
    """
    Bulletproof element interaction with comprehensive stale element handling
    """
    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            # Wait for element to be present and stable
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located(locator)
            )
            
            # Additional stability check
            WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable(locator)
            )
            
            # Re-locate element to ensure freshness
            element = driver.find_element(*locator)
            
            # Perform the requested action
            if action_type == "click":
                element.click()
            elif action_type == "select_by_index":
                Select(element).select_by_index(value)
            elif action_type == "select_by_text":
                Select(element).select_by_visible_text(value)
            elif action_type == "clear_and_send":
                element.clear()
                element.send_keys(value)
            
            return True
            
        except StaleElementReferenceException:
            print(f"🔄 Stale element on attempt {attempt + 1}, retrying...")
            time.sleep(2 ** attempt)  # Exponential backoff
            continue
            
        except TimeoutException:
            print(f"⏳ Element timeout on attempt {attempt + 1}")
            if attempt == MAX_RETRY_ATTEMPTS - 1:
                return False
            time.sleep(2 ** attempt)
            continue
            
        except Exception as e:
            print(f"❌ Element interaction error on attempt {attempt + 1}: {e}")
            if attempt == MAX_RETRY_ATTEMPTS - 1:
                return False
            time.sleep(2 ** attempt)
            continue
    
    return False

def bulletproof_market_selection(driver, market_index, market_name, timeout=WAIT_TIMEOUT):
    """
    Ultra-robust market selection with guaranteed success or clear failure
    """
    print(f"📊 Bulletproof scraping {market_name}...")
    
    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            # Step 1: Wait for page stability
            if not wait_for_page_load_complete(driver, timeout):
                print(f"⚠️ Page not stable on attempt {attempt + 1}")
                continue
            
            # Step 2: Select market with robust interaction
            if not robust_element_interaction(driver, (By.ID, 'ddlMarket'), "select_by_index", market_index, timeout):
                print(f"⚠️ Market selection failed on attempt {attempt + 1}")
                continue
                
            # Step 3: Click Go button with robust interaction
            if not robust_element_interaction(driver, (By.ID, 'btnGo'), "click", timeout=timeout):
                print(f"⚠️ Go button click failed on attempt {attempt + 1}")
                continue
            
            # Step 4: Wait for results table with multiple possible IDs
            table_found = False
            for table_id in ['cphBody_GridPriceData', 'DataGrid1', 'gvPriceData']:
                try:
                    WebDriverWait(driver, timeout).until(
                        EC.presence_of_element_located((By.ID, table_id))
                    )
                    table_found = True
                    break
                except TimeoutException:
                    continue
            
            if not table_found:
                print(f"⚠️ Results table not found on attempt {attempt + 1}")
                continue
            
            # Step 5: Final stability check
            if not wait_for_page_load_complete(driver, timeout=10):
                print(f"⚠️ Final page not stable on attempt {attempt + 1}")
                continue
                
            print(f"✅ Successfully selected {market_name} on attempt {attempt + 1}")
            return True
            
        except Exception as e:
            print(f"❌ Market selection error on attempt {attempt + 1}: {e}")
            if attempt < MAX_RETRY_ATTEMPTS - 1:
                # Full page refresh as last resort
                try:
                    print(f"🔄 Full page refresh and retry for {market_name}")
                    driver.refresh()
                    wait_for_page_load_complete(driver, timeout)
                    time.sleep(3)  # Additional recovery time
                except:
                    pass
                continue
    
    print(f"❌ Failed to select {market_name} after {MAX_RETRY_ATTEMPTS} attempts")
    return False

# ------------- Enhanced Dynamic City-Based Scraper -------------
def scrape_agmarknet(date_str, state, district_code, commodity_code):
    """
    Bulletproof scraper with comprehensive stale element protection
    """
    try:
        if len(date_str) == 10 and '-' in date_str:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            date_obj = datetime.strptime(date_str, "%d-%b-%Y")
        formatted_date = date_obj.strftime("%d-%b-%Y")
    except:
        date_obj = datetime.now() - timedelta(days=7)
        formatted_date = date_obj.strftime("%d-%b-%Y")

    district_names = {
        '7': 'agra', '33': 'lucknow', '26': 'kanpur', '38': 'meerut',
        '18': 'ghaziabad', '3': 'aligarh', '40': 'moradabad', '58': 'saharanpur',
        '19': 'gorakhpur', '9': 'bareilly', '37': 'mathura', '24': 'jhansi',
        '1': 'allahabad', '68': 'varanasi', '16': 'firozabad', '15': 'faizabad'
    }
    target_city = district_names.get(district_code, 'unknown').lower()
    print(f"🔍 Bulletproof scraping ALL {target_city.title()} markets for date: {formatted_date}")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-logging")

    all_market_data = []
    commodity_names = {
        '23': 'Wheat', '1': 'Rice', '25': 'Maize', '46': 'Potato',
        '47': 'Onion', '48': 'Tomato', '29': 'Gram', '30': 'Arhar'
    }
    commodity_name = commodity_names.get(commodity_code, 'Wheat')

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(5)  # Implicit wait as fallback
        
        initial_url = "https://agmarknet.gov.in/SearchCmmMkt.aspx"
        driver.get(initial_url)
        print("📡 Loaded AgMarkNet page")
        
        # Wait for page to be fully loaded
        wait_for_page_load_complete(driver)
        
        try:
            popup = driver.find_element(By.CLASS_NAME, 'popup-onload')
            close_button = popup.find_element(By.CLASS_NAME, 'close')
            close_button.click()
            print("✅ Closed popup")
        except NoSuchElementException:
            print("ℹ️ No popup found")

        print("🌾 Selecting commodity...")
        if not robust_element_interaction(driver, (By.ID, 'ddlCommodity'), "select_by_text", commodity_name):
            raise Exception("Failed to select commodity")

        print("🏛️ Selecting state...")
        if not robust_element_interaction(driver, (By.ID, 'ddlState'), "select_by_text", 'Uttar Pradesh'):
            raise Exception("Failed to select state")

        print("📅 Setting date...")
        if not robust_element_interaction(driver, (By.ID, "txtDate"), "clear_and_send", formatted_date):
            raise Exception("Failed to set date")

        print("🔄 Loading markets...")
        if not robust_element_interaction(driver, (By.ID, 'btnGo'), "click"):
            raise Exception("Failed to click initial Go button")
        
        # Wait for markets to load
        wait_for_page_load_complete(driver, timeout=15)

        print(f"🏪 Finding all {target_city.title()} markets...")
        WebDriverWait(driver, WAIT_TIMEOUT).until(EC.presence_of_element_located((By.ID, 'ddlMarket')))
        market_dropdown = Select(driver.find_element(By.ID, 'ddlMarket'))
        all_options = [(i, opt.text) for i, opt in enumerate(market_dropdown.options)
                       if opt.text.strip() and opt.text != '--Select--']

        if target_city == 'agra':
            city_keywords = ['agra', 'fatehpur sikri', 'mathura']
        elif target_city == 'lucknow':
            city_keywords = ['lucknow', 'banthara', 'malihabad', 'mohanlalganj']
        elif target_city == 'kanpur':
            city_keywords = ['kanpur', 'kakadeo', 'bilhaur', 'ghatampur']
        elif target_city == 'meerut':
            city_keywords = ['meerut', 'mawana', 'sardhana', 'hastinapur']
        elif target_city == 'varanasi':
            city_keywords = ['varanasi', 'benares', 'kashi']
        elif target_city == 'allahabad':
            city_keywords = ['allahabad', 'prayagraj']
        else:
            city_keywords = [target_city]

        city_markets = []
        for i, name in all_options:
            if any(k in name.lower() for k in city_keywords):
                city_markets.append((i, name))

        print(f"🎯 Found {len(city_markets)} {target_city.title()}-related markets: {[n for _, n in city_markets]}")
        if not city_markets:
            print(f"⚠️ No {target_city.title()} markets found, using first 3 available markets as fallback")
            city_markets = all_options[:3]

        # Bulletproof market scraping
        successful_markets = 0
        for market_index, market_name in city_markets:
            if bulletproof_market_selection(driver, market_index, market_name):
                try:
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    market_data = extract_market_prices_enhanced(soup, market_name, commodity_name, formatted_date)
                    
                    if market_data:
                        all_market_data.extend(market_data)
                        successful_markets += 1
                        print(f"✅ Found {len(market_data)} entries for {market_name}")
                    else:
                        print(f"⚠️ No data for {market_name}")
                        
                except Exception as e:
                    print(f"❌ Error parsing data for {market_name}: {e}")
            else:
                print(f"⚠️ Skipping {market_name} due to selection failure")

        if all_market_data:
            result_df = pd.DataFrame(all_market_data)
            print(f"🎉 Successfully scraped {successful_markets}/{len(city_markets)} markets with {len(result_df)} total records")
            return result_df
        else:
            print(f"⚠️ No live data collected, using mock data for {target_city.title()}")
            return create_city_specific_mock_data(commodity_name, target_city.title())

    except Exception as e:
        print(f"❌ Fatal scraping error: {e}")
        return create_city_specific_mock_data(commodity_name, target_city.title())
    finally:
        if driver:
            driver.quit()

# ------------- Aggregation: one price per market -------------
def summarize_prices_per_market(df: pd.DataFrame, top_k: int = TOP_K_PER_MARKET) -> pd.DataFrame:
    """
    Keep top_k most recent rows per Market, then average Modal/Min/Max to return one row per Market.
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    # Normalize types
    out["Market"] = out["Market"].astype(str).str.strip()
    out["Modal Price"] = pd.to_numeric(out.get("Modal Price", pd.NA), errors="coerce")
    out["Min Price"]   = pd.to_numeric(out.get("Min Price", pd.NA), errors="coerce")
    out["Max Price"]   = pd.to_numeric(out.get("Max Price", pd.NA), errors="coerce")
    out["Date"] = pd.to_datetime(out.get("Date", pd.NaT), errors="coerce")

    # Sort within market and keep top_k rows per group
    out = out.sort_values(["Market", "Date", "Modal Price"], ascending=[True, False, False])
    topk = out.groupby("Market", group_keys=False).head(top_k)

    # Aggregate per market
    agg = topk.groupby("Market", as_index=False).agg({
        "Modal Price": "mean",
        "Min Price": "mean",
        "Max Price": "mean",
        "Date": "max"  # most recent date used as reference
    })

    # Round for display
    for col in ["Modal Price", "Min Price", "Max Price"]:
        agg[col] = agg[col].round().astype("Int64")

    # Rename columns for clarity
    agg = agg.rename(columns={
        "Modal Price": "Avg Modal",
        "Min Price": "Avg Min",
        "Max Price": "Avg Max",
        "Date": "Latest Date"
    })
    return agg

# ------------- Date formatting utility -------------
def format_date_for_agmarknet(date_str):
    """Convert date from YYYY-MM-DD format to DD-Mon-YYYY format"""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%d-%b-%Y")
    except ValueError:
        return None

# ------------- CLI Chat Loop -------------
def run_chatbot():
    """Main chatbot function that integrates all components"""
    print("🤖 Welcome to the Agricultural Price Chatbot!")
    print("I can help you find commodity prices in Uttar Pradesh.")
    print("Type 'exit' or 'quit' to end the conversation.\n")
    slot_filler = SlotFiller()
    session_state = {}
    in_price_enquiry = False

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ['exit', 'quit', 'bye']:
            print("Goodbye! 👋")
            break
        if not user_input:
            continue

        if not in_price_enquiry:
            classification = classifier.predict(user_input)
            print(f"Classification: {classification['prediction']} (confidence: {classification['confidence']:.2f})")
            if classification['prediction'] == 'non_price_enquiry':
                print("I specialize in price enquiries. Please ask about commodity prices.")
                continue
            else:
                in_price_enquiry = True

        result = slot_filler.handle_message(user_input, session_state)
        session_state = result['session_state']

        if result.get('ask'):
            print(f"Bot: {result['ask']}")
        elif result.get('slots'):
            slots = result['slots']
            commodity = slots['commodity']
            district = slots['area']
            time_str = slots['time']
            print(f"Bot: Got all information! Commodity: {commodity}, District: {district}, Time: {time_str}")

            formatted_date = format_date_for_agmarknet(time_str)
            if not formatted_date:
                print("Bot: Sorry, I couldn't understand the date format. Please try again.")
                continue

            commodity_code = slot_filler.commodity_map.get(commodity.lower())
            district_code = slot_filler.district_map.get(district.lower())
            if not commodity_code or not district_code:
                print("Bot: Sorry, I couldn't find codes for the provided commodity or district.")
                continue

            print(f"Bot: Fetching data for {commodity} (code: {commodity_code}) in {district} (code: {district_code}) on {formatted_date}...")
            raw_df = scrape_agmarknet(formatted_date, "UP", district_code, commodity_code)

            if raw_df is not None and not raw_df.empty:
                summary_df = summarize_prices_per_market(raw_df, TOP_K_PER_MARKET)
                print(f"Bot: Market prices (averaged over top {TOP_K_PER_MARKET} entries per market):")
                for _, r in summary_df.iterrows():
                    date_txt = r["Latest Date"].strftime("%d-%b-%Y") if pd.notna(r["Latest Date"]) else "N/A"
                    print(f"🏪 {r['Market']}: Modal ₹{r['Avg Modal']}/q | Max ₹{r['Avg Max']} | Min ₹{r['Avg Min']} | 📅 {date_txt}")
            else:
                print("Bot: Sorry, no data was found for your query.")

            session_state = {}
            in_price_enquiry = False
            print("\nBot: What else can I help you with?")

if __name__ == "__main__":
    run_chatbot()
