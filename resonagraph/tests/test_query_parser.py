"""
Tests for Query Language Parser.

Phase 5: Tests for Cypher-like query parsing with resonance extensions.
"""

import pytest
from resonagraph.api.query import Query, QueryParser


class TestQueryParser:
    """Test QueryParser for Cypher parsing."""
    
    def test_parser_initialization(self):
        """Test parser can be created."""
        parser = QueryParser()
        assert parser is not None
    
    def test_parse_simple_match(self):
        """Test parsing simple MATCH clause."""
        parser = QueryParser()
        result = parser.parse("MATCH (u:User) RETURN u")
        
        assert result['type'] == 'query'
        assert result['match_clause'] is not None
        assert len(result['match_clause']['nodes']) == 1
        assert result['match_clause']['nodes'][0]['variable'] == 'u'
        assert result['match_clause']['nodes'][0]['label'] == 'User'
    
    def test_parse_match_with_properties(self):
        """Test parsing MATCH with node properties."""
        parser = QueryParser()
        result = parser.parse('MATCH (u:User {id: "user_123"}) RETURN u')
        
        assert result['match_clause'] is not None
        node = result['match_clause']['nodes'][0]
        assert node['variable'] == 'u'
        assert node['label'] == 'User'
        assert node['properties']['id'] == 'user_123'
    
    def test_parse_relationship_pattern(self):
        """Test parsing relationship patterns."""
        parser = QueryParser()
        result = parser.parse("MATCH (u)-[:FOLLOWS]->(f) RETURN f")
        
        assert result['match_clause'] is not None
        rels = result['match_clause']['relationships']
        assert len(rels) > 0
        assert rels[0]['type'] == 'FOLLOWS'
        assert rels[0]['min_hops'] == 1
        assert rels[0]['max_hops'] == 1
    
    def test_parse_variable_length_relationship(self):
        """Test parsing variable-length relationships."""
        parser = QueryParser()
        result = parser.parse("MATCH (u)-[:FOLLOWS*1..2]->(f) RETURN f")
        
        rels = result['match_clause']['relationships']
        assert len(rels) > 0
        assert rels[0]['type'] == 'FOLLOWS'
        assert rels[0]['min_hops'] == 1
        assert rels[0]['max_hops'] == 2
    
    def test_parse_where_clause(self):
        """Test parsing WHERE clause."""
        parser = QueryParser()
        result = parser.parse("MATCH (u:User) WHERE u.age > 18 RETURN u")
        
        assert result['where_clause'] is not None
        assert 'u.age > 18' in result['where_clause']
    
    def test_parse_return_clause(self):
        """Test parsing RETURN clause."""
        parser = QueryParser()
        result = parser.parse("MATCH (u:User) RETURN u.name, u.age")
        
        assert result['return_clause'] is not None
        assert 'u.name' in result['return_clause']
        assert 'u.age' in result['return_clause']
    
    def test_parse_cohere_extension(self):
        """Test parsing COHERE ON resonance extension."""
        parser = QueryParser()
        result = parser.parse(
            "MATCH (u:User)-[:FOLLOWS]->(f) COHERE ON u,f RETURN f"
        )
        
        assert result['cohere_on'] is not None
        assert 'u' in result['cohere_on']
        assert 'f' in result['cohere_on']
    
    def test_parse_epoch_window_extension(self):
        """Test parsing EPOCH WINDOW resonance extension."""
        parser = QueryParser()
        result = parser.parse("MATCH (u:User) EPOCH WINDOW +5 RETURN u")
        
        assert result['epoch_window'] is not None
        assert result['epoch_window'] == 5
    
    def test_parse_epoch_window_negative(self):
        """Test parsing EPOCH WINDOW with negative value."""
        parser = QueryParser()
        result = parser.parse("MATCH (u:User) EPOCH WINDOW -3 RETURN u")
        
        assert result['epoch_window'] == -3
    
    def test_parse_complex_query(self):
        """Test parsing complex query with all features."""
        parser = QueryParser()
        cypher = (
            'MATCH (u:User {id: "user_123"})-[:FOLLOWS*1..2]->(f) '
            'WHERE f.active = true '
            'COHERE ON u,f '
            'EPOCH WINDOW +2 '
            'RETURN f.name, f.age'
        )
        result = parser.parse(cypher)
        
        # Check all components parsed
        assert result['match_clause'] is not None
        assert result['where_clause'] is not None
        assert result['return_clause'] is not None
        assert result['cohere_on'] is not None
        assert result['epoch_window'] == 2
        
        # Check specifics
        assert len(result['match_clause']['nodes']) > 0
        assert 'u' in result['cohere_on']
        assert 'f' in result['cohere_on']
    
    def test_parse_lazy_eval_default(self):
        """Test that lazy evaluation is enabled by default."""
        parser = QueryParser()
        result = parser.parse("MATCH (u:User) RETURN u")
        
        assert result['lazy_eval'] is True


class TestQueryClass:
    """Test Query class wrapper."""
    
    def test_query_initialization(self):
        """Test Query object can be created."""
        query = Query("MATCH (u:User) RETURN u")
        assert query is not None
        assert query.cypher == "MATCH (u:User) RETURN u"
    
    def test_query_parse(self):
        """Test Query.parse() uses parser."""
        query = Query("MATCH (u:User) RETURN u")
        result = query.parse()
        
        assert result['type'] == 'query'
        assert result['cypher'] == query.cypher
    
    def test_query_parse_caching(self):
        """Test that parsed result is cached."""
        query = Query("MATCH (u:User) RETURN u")
        result1 = query.parse()
        result2 = query.parse()
        
        assert result1 is result2  # Same object reference
    
    def test_query_repr(self):
        """Test Query string representation."""
        query = Query("MATCH (u:User) RETURN u")
        repr_str = repr(query)
        
        assert "Query" in repr_str
        assert "MATCH" in repr_str
    
    def test_query_with_cohere(self):
        """Test Query with COHERE extension."""
        query = Query(
            "MATCH (u:User)-[:FOLLOWS]->(f) COHERE ON u,f RETURN f.name"
        )
        result = query.parse()
        
        assert result['cohere_on'] is not None
        assert 'u' in result['cohere_on']
    
    def test_query_with_epoch_window(self):
        """Test Query with EPOCH WINDOW extension."""
        query = Query("MATCH (u:User) EPOCH WINDOW +3 RETURN u")
        result = query.parse()
        
        assert result['epoch_window'] == 3


class TestQueryParserEdgeCases:
    """Test edge cases in query parsing."""
    
    def test_parse_empty_query(self):
        """Test parsing empty query."""
        parser = QueryParser()
        result = parser.parse("")
        
        assert result['type'] == 'query'
        assert result['match_clause'] is None
    
    def test_parse_case_insensitive(self):
        """Test that parsing is case-insensitive."""
        parser = QueryParser()
        result1 = parser.parse("MATCH (u:User) RETURN u")
        result2 = parser.parse("match (u:User) return u")
        
        # Both should parse successfully
        assert result1['match_clause'] is not None
        assert result2['match_clause'] is not None
    
    def test_parse_node_without_label(self):
        """Test parsing node pattern without label."""
        parser = QueryParser()
        result = parser.parse("MATCH (u) RETURN u")
        
        node = result['match_clause']['nodes'][0]
        assert node['variable'] == 'u'
        assert node['label'] is None
    
    def test_parse_relationship_without_type(self):
        """Test parsing relationship without type."""
        parser = QueryParser()
        result = parser.parse("MATCH (u)-[]->(f) RETURN f")
        
        rels = result['match_clause']['relationships']
        assert len(rels) > 0
        # Type should be None for untyped relationship
    
    def test_parse_multiple_return_fields(self):
        """Test parsing multiple RETURN fields."""
        parser = QueryParser()
        result = parser.parse("MATCH (u:User) RETURN u.name, u.age, u.email")
        
        assert len(result['return_clause']) == 3
        assert 'u.name' in result['return_clause']
        assert 'u.age' in result['return_clause']
        assert 'u.email' in result['return_clause']
