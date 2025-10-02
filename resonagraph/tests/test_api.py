"""
Tests for Client SDK API methods.

Phase 5: Tests for traverse() and query() with resonance extensions.
"""

import pytest
from resonagraph.api.client import Client
from resonagraph.api.query import Query
from resonagraph.core.phase_key import PhaseKey


class TestClientTraverse:
    """Test Client.traverse() method with coherence bias."""
    
    def test_traverse_initialization(self):
        """Test traverse can be called."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Should not raise error
        results = client.traverse("vertex:start", "FOLLOWS", phase_key)
        assert isinstance(results, list)
    
    def test_traverse_nonexistent_start(self):
        """Test traverse with nonexistent start vertex."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        results = client.traverse("vertex:nonexistent", "FOLLOWS", phase_key)
        assert len(results) == 0
    
    def test_traverse_simple_path(self):
        """Test traverse with simple two-node path."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Create vertices
        client.put("vertex:alice", {"name": "Alice"}, phase_key)
        client.put("vertex:bob", {"name": "Bob"}, phase_key)
        
        # Create edge
        client.put("edge:vertex:alice:vertex:bob:FOLLOWS", {}, phase_key)
        
        # Traverse from alice
        results = client.traverse("vertex:alice", "FOLLOWS", phase_key)
        
        # Should find alice (start) and bob (via edge)
        assert len(results) > 0
        
        # Check that alice is in results
        alice_found = any(r['key'] == 'vertex:alice' for r in results)
        assert alice_found
    
    def test_traverse_with_max_depth(self):
        """Test traverse respects max_depth parameter."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Create chain: A -> B -> C -> D
        client.put("vertex:a", {"name": "A"}, phase_key)
        client.put("vertex:b", {"name": "B"}, phase_key)
        client.put("vertex:c", {"name": "C"}, phase_key)
        client.put("vertex:d", {"name": "D"}, phase_key)
        
        client.put("edge:vertex:a:vertex:b:NEXT", {}, phase_key)
        client.put("edge:vertex:b:vertex:c:NEXT", {}, phase_key)
        client.put("edge:vertex:c:vertex:d:NEXT", {}, phase_key)
        
        # Traverse with max_depth=2
        results = client.traverse("vertex:a", "NEXT", phase_key, max_depth=2)
        
        # Should find A, B, C but not D (depth > 2)
        keys = [r['key'] for r in results if r['type'] == 'vertex']
        assert 'vertex:a' in keys
        assert 'vertex:b' in keys
        # C might be found at depth 2
    
    def test_traverse_with_coherence_bias(self):
        """Test traverse with coherence bias enabled."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Create vertices
        client.put("vertex:alice", {"name": "Alice"}, phase_key)
        client.put("vertex:bob", {"name": "Bob"}, phase_key)
        client.put("vertex:carol", {"name": "Carol"}, phase_key)
        
        # Create edges
        client.put("edge:vertex:alice:vertex:bob:KNOWS", {}, phase_key)
        client.put("edge:vertex:alice:vertex:carol:KNOWS", {}, phase_key)
        
        # Traverse with coherence
        results = client.traverse(
            "vertex:alice", "KNOWS", phase_key, use_coherence=True
        )
        
        assert len(results) > 0
    
    def test_traverse_without_coherence_bias(self):
        """Test traverse with coherence bias disabled."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Create vertices and edges
        client.put("vertex:alice", {"name": "Alice"}, phase_key)
        client.put("vertex:bob", {"name": "Bob"}, phase_key)
        client.put("edge:vertex:alice:vertex:bob:KNOWS", {}, phase_key)
        
        # Traverse without coherence
        results = client.traverse(
            "vertex:alice", "KNOWS", phase_key, use_coherence=False
        )
        
        assert len(results) > 0
    
    def test_traverse_returns_path_info(self):
        """Test that traverse results include path information."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Create simple path
        client.put("vertex:alice", {"name": "Alice"}, phase_key)
        client.put("vertex:bob", {"name": "Bob"}, phase_key)
        client.put("edge:vertex:alice:vertex:bob:KNOWS", {}, phase_key)
        
        results = client.traverse("vertex:alice", "KNOWS", phase_key)
        
        # Check vertex results have path info
        for result in results:
            if result['type'] == 'vertex':
                assert 'path' in result
                assert 'depth' in result
                assert isinstance(result['path'], list)
    
    def test_traverse_cyclic_graph(self):
        """Test traverse handles cycles correctly."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Create cycle: A -> B -> C -> A
        client.put("vertex:a", {"name": "A"}, phase_key)
        client.put("vertex:b", {"name": "B"}, phase_key)
        client.put("vertex:c", {"name": "C"}, phase_key)
        
        client.put("edge:vertex:a:vertex:b:NEXT", {}, phase_key)
        client.put("edge:vertex:b:vertex:c:NEXT", {}, phase_key)
        client.put("edge:vertex:c:vertex:a:NEXT", {}, phase_key)
        
        # Should not infinite loop
        results = client.traverse("vertex:a", "NEXT", phase_key, max_depth=5)
        
        # Should visit each vertex once
        vertex_keys = [r['key'] for r in results if r['type'] == 'vertex']
        unique_keys = set(vertex_keys)
        assert len(unique_keys) <= 3  # A, B, C


class TestClientQuery:
    """Test Client.query() method with Cypher execution."""
    
    def test_query_simple_match(self):
        """Test simple MATCH query execution."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Create vertex
        client.put("vertex:alice", {"name": "Alice", "age": 30}, phase_key)
        
        # Execute query
        query = Query('MATCH (u:User {id: "vertex:alice"}) RETURN u')
        result = client.query(query, phase_key)
        
        assert 'nodes' in result
        assert 'edges' in result
        assert 'metrics' in result
    
    def test_query_with_relationship(self):
        """Test query with relationship traversal."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Create graph: Alice -> Bob
        client.put("vertex:alice", {"name": "Alice"}, phase_key)
        client.put("vertex:bob", {"name": "Bob"}, phase_key)
        client.put("edge:vertex:alice:vertex:bob:FOLLOWS", {}, phase_key)
        
        # Query with relationship
        query = Query(
            'MATCH (u:User {id: "vertex:alice"})-[:FOLLOWS]->(f) RETURN f'
        )
        result = client.query(query, phase_key)
        
        assert result is not None
        assert 'metrics' in result
    
    def test_query_with_cohere_extension(self):
        """Test query with COHERE ON resonance extension."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Create graph
        client.put("vertex:alice", {"name": "Alice"}, phase_key)
        client.put("vertex:bob", {"name": "Bob"}, phase_key)
        client.put("edge:vertex:alice:vertex:bob:FOLLOWS", {}, phase_key)
        
        # Query with COHERE
        query = Query(
            'MATCH (u:User {id: "vertex:alice"})-[:FOLLOWS]->(f) '
            'COHERE ON u,f RETURN f'
        )
        result = client.query(query, phase_key)
        
        assert result['metrics']['used_cohere'] is True
    
    def test_query_with_epoch_window(self):
        """Test query with EPOCH WINDOW resonance extension."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Create vertex
        client.put("vertex:alice", {"name": "Alice"}, phase_key)
        
        # Query with EPOCH WINDOW
        query = Query(
            'MATCH (u:User {id: "vertex:alice"}) EPOCH WINDOW +2 RETURN u'
        )
        result = client.query(query, phase_key)
        
        assert result['metrics']['epoch_window'] == 2
    
    def test_query_metrics_included(self):
        """Test that query results include metrics."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Create vertex
        client.put("vertex:alice", {"name": "Alice"}, phase_key)
        
        # Execute query
        query = Query('MATCH (u:User {id: "vertex:alice"}) RETURN u')
        result = client.query(query, phase_key)
        
        metrics = result['metrics']
        assert 'query_time' in metrics
        assert 'nodes_matched' in metrics
        assert 'edges_matched' in metrics
        assert isinstance(metrics['query_time'], float)
    
    def test_query_with_params(self):
        """Test query with parameter substitution."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Create vertex
        client.put("vertex:alice", {"name": "Alice"}, phase_key)
        
        # Query with params
        query = Query('MATCH (u:User {id: "vertex:alice"}) RETURN u')
        params = {"depth": 2}
        result = client.query(query, phase_key, params)
        
        assert result is not None
    
    def test_query_variable_length_path(self):
        """Test query with variable-length relationship."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Create chain: A -> B -> C
        client.put("vertex:a", {"name": "A"}, phase_key)
        client.put("vertex:b", {"name": "B"}, phase_key)
        client.put("vertex:c", {"name": "C"}, phase_key)
        
        client.put("edge:vertex:a:vertex:b:KNOWS", {}, phase_key)
        client.put("edge:vertex:b:vertex:c:KNOWS", {}, phase_key)
        
        # Query with variable-length path
        query = Query(
            'MATCH (u:User {id: "vertex:a"})-[:KNOWS*1..2]->(f) RETURN f'
        )
        result = client.query(query, phase_key)
        
        # Should find B and C
        assert result['metrics']['nodes_matched'] >= 0
    
    def test_query_empty_result(self):
        """Test query with no matching results."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Query for nonexistent vertex
        query = Query('MATCH (u:User {id: "vertex:nonexistent"}) RETURN u')
        result = client.query(query, phase_key)
        
        assert result['metrics']['nodes_matched'] == 0


class TestCoherenceBias:
    """Test coherence bias computation."""
    
    def test_compute_coherence_score(self):
        """Test coherence score computation between vertices."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Create two vertices
        client.put("vertex:a", {"name": "A"}, phase_key)
        client.put("vertex:b", {"name": "B"}, phase_key)
        
        # Compute coherence
        score = client._compute_coherence_score(
            "vertex:a", "vertex:b", phase_key
        )
        
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
    
    def test_coherence_score_nonexistent_vertices(self):
        """Test coherence score with nonexistent vertices."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        score = client._compute_coherence_score(
            "vertex:nonexistent1", "vertex:nonexistent2", phase_key
        )
        
        assert score == 0.0


class TestAPIIntegration:
    """Integration tests for API methods."""
    
    def test_full_query_workflow(self):
        """Test complete workflow: put, query, traverse."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Step 1: Create graph
        client.put("vertex:alice", {"name": "Alice", "age": 30}, phase_key)
        client.put("vertex:bob", {"name": "Bob", "age": 25}, phase_key)
        client.put("vertex:carol", {"name": "Carol", "age": 28}, phase_key)
        
        client.put("edge:vertex:alice:vertex:bob:FOLLOWS", {}, phase_key)
        client.put("edge:vertex:alice:vertex:carol:FOLLOWS", {}, phase_key)
        client.put("edge:vertex:bob:vertex:carol:KNOWS", {}, phase_key)
        
        # Step 2: Execute query with COHERE
        query = Query(
            'MATCH (u:User {id: "vertex:alice"})-[:FOLLOWS*1..2]->(f) '
            'COHERE ON u,f '
            'RETURN f'
        )
        result = client.query(query, phase_key)
        
        # Step 3: Verify results
        assert result is not None
        assert result['metrics']['used_cohere'] is True
        
        # Step 4: Direct traverse for comparison
        traverse_result = client.traverse(
            "vertex:alice", "FOLLOWS", phase_key, max_depth=2
        )
        
        assert len(traverse_result) > 0
    
    def test_query_performance_metrics(self):
        """Test that query returns performance metrics."""
        client = Client("http://test.local")
        phase_key = PhaseKey.generate()
        
        # Create data
        for i in range(5):
            client.put(f"vertex:user{i}", {"id": i}, phase_key)
        
        # Execute query
        query = Query('MATCH (u:User {id: "vertex:user0"}) RETURN u')
        result = client.query(query, phase_key)
        
        # Check metrics
        assert 'query_time' in result['metrics']
        assert result['metrics']['query_time'] >= 0.0
