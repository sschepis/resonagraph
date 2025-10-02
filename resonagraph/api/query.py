"""
Query language support for ResonaGraph.

Extends Cypher with resonance primitives:
- COHERE ON path: Apply H_G bias for coherent subgraph traversal
- EPOCH WINDOW ±n: Filter beacons by epoch drift tolerance
"""

from typing import Optional, Dict, Any, List
import re


class QueryParser:
    """
    Parser for Cypher-like queries with resonance extensions.
    
    According to design.md Section 4.2:
    - Cypher subset + resonance extensions
    - COHERE ON path: Apply H_G bias
    - EPOCH WINDOW ±n: Filter beacons by drift
    """
    
    def __init__(self):
        """Initialize query parser."""
        # Basic Cypher patterns
        self.match_pattern = re.compile(
            r'MATCH\s+(.+?)(?:\s+WHERE|\s+COHERE|\s+EPOCH|\s+RETURN|$)',
            re.IGNORECASE
        )
        self.where_pattern = re.compile(
            r'WHERE\s+(.+?)(?:\s+COHERE|\s+EPOCH|\s+RETURN|$)',
            re.IGNORECASE
        )
        self.return_pattern = re.compile(
            r'RETURN\s+(.+?)(?:\s+LIMIT|\s+ORDER|$)',
            re.IGNORECASE
        )
        
        # Resonance extensions
        self.cohere_pattern = re.compile(
            r'COHERE\s+ON\s+(.+?)(?:\s+EPOCH|\s+WHERE|\s+RETURN|$)',
            re.IGNORECASE
        )
        self.epoch_window_pattern = re.compile(
            r'EPOCH\s+WINDOW\s+([+-]?\d+)',
            re.IGNORECASE
        )
        
        # Relationship patterns
        self.rel_pattern = re.compile(
            r'\[([^\]]*)\]'
        )
    
    def parse(self, cypher: str) -> Dict[str, Any]:
        """
        Parse Cypher query into structured representation.
        
        Args:
            cypher: Cypher query string
            
        Returns:
            Parsed query structure with:
            - match_clause: Pattern to match
            - where_clause: Filter conditions
            - return_clause: Return values
            - cohere_on: Variables to apply coherence bias
            - epoch_window: Epoch drift tolerance
            - lazy_eval: Whether to use lazy evaluation
        """
        parsed = {
            'type': 'query',
            'cypher': cypher,
            'match_clause': None,
            'where_clause': None,
            'return_clause': None,
            'cohere_on': None,
            'epoch_window': None,
            'lazy_eval': True  # Default for resonance queries
        }
        
        # Parse MATCH clause
        match_result = self.match_pattern.search(cypher)
        if match_result:
            parsed['match_clause'] = self._parse_match_clause(match_result.group(1))
        
        # Parse WHERE clause
        where_result = self.where_pattern.search(cypher)
        if where_result:
            parsed['where_clause'] = where_result.group(1).strip()
        
        # Parse RETURN clause
        return_result = self.return_pattern.search(cypher)
        if return_result:
            parsed['return_clause'] = [
                item.strip() for item in return_result.group(1).split(',')
            ]
        
        # Parse COHERE ON extension
        cohere_result = self.cohere_pattern.search(cypher)
        if cohere_result:
            parsed['cohere_on'] = [
                var.strip() for var in cohere_result.group(1).split(',')
            ]
        
        # Parse EPOCH WINDOW extension
        epoch_result = self.epoch_window_pattern.search(cypher)
        if epoch_result:
            parsed['epoch_window'] = int(epoch_result.group(1))
        
        return parsed
    
    def _parse_match_clause(self, match_str: str) -> Dict[str, Any]:
        """
        Parse MATCH clause pattern.
        
        Args:
            match_str: MATCH clause content
            
        Returns:
            Parsed pattern structure
        """
        # Parse node patterns: (var:Label {prop: value})
        node_pattern = re.compile(r'\(([^)]+)\)')
        nodes = []
        for node_match in node_pattern.finditer(match_str):
            node_content = node_match.group(1)
            node_info = self._parse_node_pattern(node_content)
            nodes.append(node_info)
        
        # Parse relationship patterns: -[:TYPE*min..max]->
        relationships = []
        rel_matches = self.rel_pattern.finditer(match_str)
        for rel_match in rel_matches:
            rel_content = rel_match.group(1)
            rel_info = self._parse_relationship_pattern(rel_content)
            relationships.append(rel_info)
        
        return {
            'nodes': nodes,
            'relationships': relationships,
            'pattern': match_str.strip()
        }
    
    def _parse_node_pattern(self, node_str: str) -> Dict[str, Any]:
        """Parse node pattern like 'u:User {id: "user_123"}'."""
        # First extract properties (everything in {...})
        props = {}
        label = None
        var = node_str.strip()
        
        # Check for properties
        if '{' in node_str:
            var_label_part, props_str = node_str.split('{', 1)
            props_str = props_str.rstrip('}').strip()
            
            # Parse properties
            if props_str:
                # Split by comma, but be careful with nested structures
                for prop in props_str.split(','):
                    if ':' in prop:
                        key, value = prop.split(':', 1)
                        props[key.strip()] = value.strip().strip('"\'')
            
            node_str = var_label_part
        
        # Now parse variable and label
        parts = node_str.split(':')
        var = parts[0].strip()
        
        if len(parts) > 1:
            label = parts[1].strip()
        
        return {
            'variable': var,
            'label': label,
            'properties': props
        }
    
    def _parse_relationship_pattern(self, rel_str: str) -> Dict[str, Any]:
        """Parse relationship pattern like ':FOLLOWS*1..2'."""
        # Match pattern: [:TYPE*min..max]
        if not rel_str:
            return {'type': None, 'min_hops': 1, 'max_hops': 1}
        
        parts = rel_str.split('*')
        rel_type = parts[0].lstrip(':').strip() if parts[0] else None
        
        min_hops, max_hops = 1, 1
        if len(parts) > 1:
            hop_range = parts[1]
            if '..' in hop_range:
                min_str, max_str = hop_range.split('..')
                min_hops = int(min_str) if min_str else 1
                max_hops = int(max_str) if max_str else float('inf')
            else:
                min_hops = max_hops = int(hop_range)
        
        return {
            'type': rel_type,
            'min_hops': min_hops,
            'max_hops': max_hops
        }


class Query:
    """
    Cypher-like query with resonance extensions.
    
    According to design.md Section 4.2:
    - Cypher subset + resonance extensions
    - Lazy evaluation for partial locks
    """
    
    def __init__(self, cypher: str):
        """
        Create a query from Cypher string.
        
        Args:
            cypher: Cypher query string with optional resonance extensions
        """
        self.cypher = cypher
        self._parsed = None
        self._parser = QueryParser()
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse the Cypher query.
        
        Returns:
            Parsed query structure
        """
        if self._parsed is None:
            self._parsed = self._parser.parse(self.cypher)
        
        return self._parsed
    
    def __repr__(self) -> str:
        """String representation."""
        return f"Query({self.cypher!r})"
