import pytest
from app.normalizers.x_network_normalizer import XNetworkNormalizer
from app.schemas.unified_edge import RelationshipType
from app.exceptions import NormalizationError

def test_normalize_valid_edge():
    normalizer = XNetworkNormalizer()
    raw_data = {
        "source": "userA",
        "target": "userB",
        "relationship_type": "QUOTE",
        "timestamp": "2026-09-03T12:00:00Z",
        "weight": "2.5"
    }
    
    edge = normalizer.normalize(raw_data, {"platform": "x", "raw_file": ""})
    
    assert edge.source_user_id == "userA"
    assert edge.target_user_id == "userB"
    assert edge.relationship_type == RelationshipType.QUOTE
    assert edge.weight == 2.5
    assert edge.timestamp is not None
    assert edge.edge_id is not None

def test_missing_source_target():
    normalizer = XNetworkNormalizer()
    raw_data = {
        "source": "userA"
    }
    
    with pytest.raises(NormalizationError, match="Missing source or target"):
        normalizer.normalize(raw_data, {"platform": "x", "raw_file": ""})

def test_invalid_relationship_type_fallback():
    normalizer = XNetworkNormalizer()
    raw_data = {
        "source": "userA",
        "target": "userB",
        "relationship_type": "MAGIC"
    }
    
    edge = normalizer.normalize(raw_data, {"platform": "x", "raw_file": ""})
    assert edge.relationship_type == RelationshipType.UNKNOWN
