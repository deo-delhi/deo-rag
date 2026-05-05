import re
from typing import List, Dict

# Simple synonym dictionary for DEO context
DEO_SYNONYMS = {
    "ration": ["food security", "bpl", "pds", "provision"],
    "eligibility": ["criteria", "requirement", "qualification", "conditions"],
    "income": ["salary", "earnings", "revenue", "means"],
    "certificate": ["document", "attestation", "proof", "record"],
    "land": ["property", "plot", "estate", "holding"],
    "defence": ["military", "cantonment", "army", "armed forces"],
    "estate": ["land", "property", "holding"],
}

# Hindi-English common variants for DEO context
HINDI_VARIANTS = {
    "ration": ["rashan", "खाद्य"],
    "land": ["zamin", "bhumi", "ज़मीन"],
    "certificate": ["praman patra", "प्रमाण पत्र"],
    "income": ["aay", "आय"],
}

def expand_query(query: str) -> List[str]:
    """Expands query with synonyms and Hindi variants."""
    expanded = [query]
    words = re.findall(r'\w+', query.lower())
    
    syns = []
    for word in words:
        if word in DEO_SYNONYMS:
            syns.extend(DEO_SYNONYMS[word])
        if word in HINDI_VARIANTS:
            syns.extend(HINDI_VARIANTS[word])
    
    if syns:
        # Create a combined expanded query
        expanded.append(query + " " + " ".join(list(set(syns))[:5]))
        
    return expanded

def classify_query(query: str) -> str:
    """Classifies query as 'keyword-heavy' or 'semantic'."""
    # Check for numbers or IDs
    if re.search(r'\d{3,}', query):
        return "keyword-heavy"
    
    # Check for specific short terms or codes
    if len(query.split()) <= 2 and any(len(w) < 4 for w in query.split()):
        return "keyword-heavy"
        
    return "semantic"
