import json
import os
import re

class GDTLoader:
    def __init__(self, json_path):
        self.json_path = json_path
        self.knowledge_base = [] # List of dicts
        self.loaded = False

    def load(self):
        """Loads the JSON file and parses relevant nodes."""
        if not os.path.exists(self.json_path):
            print(f"[WARN] GD&T Data file not found: {self.json_path}")
            return

        try:
            # Use utf-8-sig to handle BOM (Byte Order Mark) in UTF-8 files
            with open(self.json_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            
            # Parse nodes
            count = 0
            for item in data:
                n = item.get('n', {})
                props = n.get('properties', {})
                labels = n.get('labels', [])

                # We look for nodes that have a definition OR represent a Tolerance type
                # Distinctive feature: Labels containing '公差' or properties having 'definition'
                
                definition = props.get('definition', '')
                symbol = props.get('symbol', '')
                prop_name = props.get('name', '')
                
                # Extract potential human readable names from Labels
                # e.g. ["Resource", "owl__NamedIndividual", "公差", "垂直度公差", "方向類公差"]
                # We want "垂直度公差", "方向類公差"
                
                readable_names = []
                for label in labels:
                    if '公差' in label or '面' in label or '特徵' in label:
                        readable_names.append(label)
                
                # Also check property name if it looks readable (Chinese)
                if re.search(r'[\u4e00-\u9fff]', prop_name):
                    readable_names.append(prop_name)

                # Filter: Must be meaningful
                if not definition and not symbol:
                    # If no definition/symbol, only keep if it's a high level Class concept (e.g. "形狀類公差")
                    if 'owl__Class' not in labels:
                        continue
                        
                if not readable_names and not prop_name:
                    continue

                entry = {
                    'primary_id': prop_name,
                    'keywords': readable_names + [prop_name, props.get('rdfs__label', '')],
                    'symbol': symbol,
                    'definition': definition,
                    'source': props.get('source', ''),
                    'labels': labels
                }
                
                # Clean keywords (remove empty, duplicates)
                entry['keywords'] = list(set([k for k in entry['keywords'] if k]))
                
                self.knowledge_base.append(entry)
                count += 1
            
            self.loaded = True
            print(f"[SUCCESS] GD&T Knowledge Graph loaded: {count} entries found.")

        except Exception as e:
            print(f"[ERROR] Error loading GD&T data: {e}")

    def search(self, query):
        """
        Search for terms in the query.
        Returns a list of formatted strings found.
        """
        if not self.loaded:
            return []

        results = set() # Use set to avoid duplicates
        q = query.strip()
        
        # Extract meaningful terms from query (remove common words)
        common_words = {'什麼', '是', '的', '有', '關於', '請問', '告訴我', '解釋', '說明', '怎麼', '如何'}
        query_terms: list[str] = []
        
        # First try to extract technical terms by removing common question words
        cleaned_query = q
        for word in common_words:
            cleaned_query = cleaned_query.replace(word, ' ')
        
        # Split by common delimiters and filter
        for term in re.split(r'[，。？！\s]+', cleaned_query):
            term = term.strip()
            if len(term) >= 2:
                query_terms.append(term)
        
        # Also add original query terms split by delimiters
        for term in re.split(r'[，。？！\s]+', q):
            term = term.strip()
            if len(term) >= 2 and term not in common_words:
                query_terms.append(term)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_terms: list[str] = []
        for term in query_terms:
            if term not in seen:
                seen.add(term)
                unique_terms.append(term)
        query_terms = unique_terms
        
        # If no meaningful terms found, use original query
        if not query_terms:
            query_terms = [q]
        
        for item in self.knowledge_base:
            match = False
            match_score: int = 0
            
            # 1. Symbol Match (highest priority)
            if item['symbol'] and item['symbol'] in q:
                match = True
                match_score += 10
                
            # 2. Keyword Match
            for kw in item['keywords']:
                if len(kw) >= 2:
                    # Check if keyword contains any query term or vice versa
                    for term in query_terms:
                        if term in kw or kw in term:
                            match = True
                            # Exact match gets higher score
                            if term == kw:
                                match_score += 5
                            else:
                                match_score += 1
                            break
            
            if match:
                # Format the Output
                # Use the most descriptive name (longest keyword usually)
                display_name = max(item['keywords'], key=len) if item['keywords'] else item['primary_id']
                
                desc = f"【{display_name}】"
                if item['symbol']:
                    desc += f" (符號: {item['symbol']})"
                
                if item['definition']:
                    desc += f"\n  定義: {item['definition']}"
                
                if item['source']:
                    desc += f"\n  來源: {item['source']}"
                    
                # Store with score for potential sorting
                results.add((match_score, desc))

        # Sort by score (descending) and return descriptions only
        sorted_results = sorted(results, key=lambda x: x[0], reverse=True)
        return [desc for score, desc in sorted_results]

# Global Instance
gdt_loader = GDTLoader(os.path.join(os.path.dirname(__file__), 'data', 'records (3).json'))
