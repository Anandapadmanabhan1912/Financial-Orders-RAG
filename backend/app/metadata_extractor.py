import re
from datetime import datetime
from typing import Dict, Any, List

GO_PATTERN = re.compile(
    r'(?:G\.?\s*O\.?\s*(?:\([A-Za-z0-9\.]+\))?\s*No\.?\s*[\d\/A-Za-z\-]+)',
    re.IGNORECASE
)

DATE_PATTERNS = [
    re.compile(r'Dated\s*,\s*(?:[A-Za-z\s]+,)?\s*(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4})', re.IGNORECASE),
    re.compile(r'Dated\s*(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4})', re.IGNORECASE),
    re.compile(r'dated\s*(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4})', re.IGNORECASE),
    re.compile(r'(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4})')
]

MONEY_PATTERN = re.compile(r'(?:Rs\.?|INR)\s*[\d\.,]+\s*(?:Crore|Lakh|Lakhs|Thousand)?', re.IGNORECASE)
PERCENT_PATTERN = re.compile(r'(\d+(?:\.\d+)?\s*%)')

RELATION_KEYWORDS = {
    "SUPERSEDES": ["superseded", "supersession", "in supersession of", "cancels", "cancelled"],
    "AMENDS": ["modified", "modification", "amended", "amendment", "revised"],
    "EXTENDS": ["extended", "extension", "validity extended"],
    "CONTINUATION": ["in continuation to", "in continuation of", "further to"],
    "REFERENCES": ["read", "vide", "referred", "accordance with"]
}

def normalize_date(date_str: str) -> str:
    """Converts DD/MM/YYYY or DD-MM-YYYY to YYYY-MM-DD."""
    if not date_str:
        return ""
    clean = date_str.strip().replace('.', '/').replace('-', '/')
    parts = clean.split('/')
    if len(parts) == 3:
        try:
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            return f"{year:04d}-{month:02d}-{day:02d}"
        except ValueError:
            pass
    return date_str

def extract_go_number(text: str) -> str:
    matches = GO_PATTERN.findall(text)
    if matches:
        # Pick the longest match if multiple matches found
        best = max(matches, key=len).strip()
        return best.rstrip('/.-')
    return ""

def extract_department(text: str) -> str:
    match = re.search(r'(FINANCE\s*\([A-Z0-9\&\-\s]+\)\s*DEPARTMENT)', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    match2 = re.search(r'([A-Z\s\(\)\&\-]+\s*DEPARTMENT)', text)
    if match2:
        dept = match2.group(1).strip()
        if len(dept) < 60 and "GOVERNMENT" not in dept:
            return dept
    return "FINANCE DEPARTMENT"

def extract_date(text: str) -> tuple:
    for pat in DATE_PATTERNS:
        match = pat.search(text)
        if match:
            raw_d = match.group(1)
            norm_d = normalize_date(raw_d)
            return raw_d, norm_d
    return "", ""

def extract_abstract(text: str) -> str:
    match = re.search(r'Abstract\s*\n+(.*?)(?=\n\s*[A-Z\s\(\)]+DEPARTMENT|G\.O\.|\n\s*ORDER)', text, re.DOTALL | re.IGNORECASE)
    if match:
        clean = " ".join(match.group(1).split())
        return clean[:300]
    return ""

def extract_financial_parameters(text: str) -> Dict[str, Any]:
    params = {}
    money_matches = MONEY_PATTERN.findall(text)
    if money_matches:
        params["monetary_amounts"] = list(set(money_matches))
        
    percent_matches = PERCENT_PATTERN.findall(text)
    if percent_matches:
        params["percentages_rates"] = list(set(percent_matches))
        
    # Check for schedule dates table references
    schedule_dates = re.findall(r'([A-Za-z0-9\s\(\)&]+)\s*[:\-]\s*(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4})', text)
    if schedule_dates:
        params["schedule_dates"] = {k.strip(): v for k, v in schedule_dates if len(k.strip()) < 40}
        
    return params

def extract_references_and_relations(text: str, current_go: str = "") -> List[Dict[str, Any]]:
    refs = []
    
    # Locate "Read" section
    read_section = ""
    read_match = re.search(r'Read\s*:\s*(.*?)(?=\n\s*ORDER|\n\s*G\.O\.)', text, re.DOTALL | re.IGNORECASE)
    if read_match:
        read_section = read_match.group(1)
    else:
        read_match_2 = re.search(r'Read\s*1\s*(.*?)(?=\n\s*ORDER)', text, re.DOTALL | re.IGNORECASE)
        if read_match_2:
            read_section = read_match_2.group(1)
            
    # Find all referenced GO numbers
    search_space = read_section if read_section else text
    raw_refs = GO_PATTERN.findall(search_space)
    
    for r_go in set(raw_refs):
        r_go_clean = r_go.strip()
        if current_go and r_go_clean.lower() == current_go.lower():
            continue
            
        # Classify relationship based on surrounding context
        context_match = re.search(r'([^.\n]{0,100}' + re.escape(r_go_clean) + r'[^.\n]{0,100})', text, re.IGNORECASE)
        snippet = context_match.group(1) if context_match else ""
        
        rel_type = "REFERENCES"
        snippet_lower = snippet.lower()
        
        for rel_name, kw_list in RELATION_KEYWORDS.items():
            if any(kw in snippet_lower for kw in kw_list):
                rel_type = rel_name
                break
                
        refs.append({
            "target_go_number": r_go_clean,
            "relation_type": rel_type,
            "raw_text": snippet.strip()
        })
        
    return refs
