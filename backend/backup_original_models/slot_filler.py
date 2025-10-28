import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

class SlotFiller:
    """Slot filler with pattern-matching for commodity price queries."""
    
    def __init__(self,
                 commodity_list: Optional[List[str]] = None,
                 up_cities: Optional[List[str]] = None):
        # Three main commodities
        self.commodity_list = [c.lower() for c in (commodity_list or ["rice", "wheat", "maize"])]
        
        # UP cities (abbreviated list for demo - add more as needed)
        up = (up_cities or [
            "Agra", "Aligarh", "Amethi", "Amroha", "Azamgarh", "Bareilly", "Basti", 
            "Bijnor", "Budaun", "Bulandshahr", "Chandauli", "Chitrakoot", "Deoria",
            "Etah", "Etawah", "Faizabad", "Farrukhabad", "Fatehpur", "Firozabad",
            "Ghaziabad", "Ghazipur", "Gonda", "Gorakhpur", "Hamirpur", "Hapur",
            "Hardoi", "Hathras", "Jhansi", "Kannauj", "Kanpur", "Kasganj", "Kushinagar",
            "Lakhimpur", "Lalitpur", "Lucknow", "Maharajganj", "Mainpuri", "Mathura",
            "Mau", "Meerut", "Mirzapur", "Moradabad", "Muzaffarnagar", "Pilibhit",
            "Pratapgarh", "Prayagraj", "Raebareli", "Rampur", "Saharanpur", "Sambhal",
            "Shahjahanpur", "Shamli", "Sitapur", "Sultanpur", "Unnao", "Varanasi"
        ])
        
        # Normalize to lowercase
        self.up_cities = sorted({c.lower().strip() for c in up})
        
        print(f"✅ SlotFiller initialized with {len(self.commodity_list)} commodities and {len(self.up_cities)} cities")

    def _match_from_list(self, text: str, lst: List[str]) -> Optional[str]:
        if not text:
            return None
        text_low = text.lower().strip()
        matches = []
        for w in lst:
            if w in text_low or text_low in w:
                matches.append(w)
        if not matches:
            return None
        # Return longest match
        matches.sort(key=lambda x: -len(x))
        return matches[0]

    def normalize_time(self, text: str) -> Optional[str]:
        if not text:
            return None
        
        today = datetime.now().date()
        t = text.lower().strip()
        
        if t in ('today', 'tod', 'now'):
            return str(today.isoformat())
        if t in ('yesterday', 'yest'):
            return str((today - timedelta(days=1)).isoformat())
        if t in ('tomorrow', 'tmw'):
            return str((today + timedelta(days=1)).isoformat())
        
        # Add pattern matching for dates
        if re.search(r'\d{4}-\d{2}-\d{2}', t):
            return t
        
        return None

    def extract_slots(self, text: str, current_slots: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
        """Extract commodity, area, and time from text"""
        text = text.strip().lower()
        
        print(f"[DEBUG] Extracting from: '{text}'")
        print(f"[DEBUG] Current slots: {current_slots}")
        
        # Extract commodity
        if not current_slots.get('commodity'):
            commodity = self._match_from_list(text, self.commodity_list)
            if commodity:
                current_slots['commodity'] = commodity
                print(f"[DEBUG] Found commodity: {commodity}")
        
        # Extract area
        if not current_slots.get('area'):
            area = self._match_from_list(text, self.up_cities)
            if area:
                current_slots['area'] = area
                print(f"[DEBUG] Found area: {area}")
        
        # Extract time
        if not current_slots.get('time'):
            time_val = self.normalize_time(text)
            if time_val:
                current_slots['time'] = time_val
                print(f"[DEBUG] Found time: {time_val}")
        
        print(f"[DEBUG] Updated slots: {current_slots}")
        return current_slots

    def next_missing_slot(self, slots: Dict[str, Optional[str]]) -> Optional[str]:
        """Return the next missing slot"""
        for s in ['commodity', 'area', 'time']:
            if not slots.get(s):
                return s
        return None

    def prompt_for_slot(self, slot: str) -> str:
        """Generate prompt for missing slot"""
        templates = {
            'commodity': "Which commodity are you asking about? (rice, wheat, or maize)",
            'area': "Which UP city? (e.g., Agra, Lucknow, Kanpur, Varanasi)",
            'time': "For which date? (today, tomorrow, or specific date)"
        }
        return templates.get(slot, f"Please provide {slot}")

    def handle_message(self, text: str, session_state: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a message and update session state"""
        # Initialize session state
        session_state.setdefault('slots', {'commodity': None, 'area': None, 'time': None})
        session_state.setdefault('expecting', None)
        
        print(f"[DEBUG] Processing message: '{text}'")
        print(f"[DEBUG] Session state: {session_state}")
        
        # Extract slots from the current message
        session_state['slots'] = self.extract_slots(text, session_state['slots'])
        
        # Check what's still missing
        missing_slot = self.next_missing_slot(session_state['slots'])
        
        if missing_slot:
            # Still need more information
            session_state['expecting'] = missing_slot
            prompt = self.prompt_for_slot(missing_slot)
            return {
                'session_state': session_state,
                'ask': prompt
            }
        else:
            # All slots filled!
            return {
                'session_state': session_state,
                'slots': session_state['slots']
            }
