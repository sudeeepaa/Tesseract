"""
Tests for Tesseract Security Layer: Cypher and Vector Injection Protection.
Verifies that malicious or oversized inputs are properly sanitized.
"""
from __future__ import annotations

import pytest
from threadline.security import sanitize_name, validate_extraction_result
from threadline.models import ExtractionResult, Entity, EntityType


def test_sanitize_name_cypher_keywords():
    # Test keywords disarming
    assert sanitize_name("DROP") == "DROP_entity"
    assert sanitize_name("create") == "create_entity"
    assert sanitize_name("Merge") == "Merge_entity"
    
    # Non-exact keyword matches should remain untouched
    assert sanitize_name("CREATE_TABLE") == "CREATE_TABLE"
    assert sanitize_name("Drop off files") == "Drop off files"


def test_sanitize_name_malicious_characters():
    # Quotes, backticks, semi-colons, curly/square braces, and backslashes should be removed
    malicious = "Dev Rao; MATCH (n) DETACH DELETE n"
    sanitized = sanitize_name(malicious)
    assert ";" not in sanitized
    assert "MATCH" in sanitized # Substring MATCH is OK as long as it's not the exact name
    assert "DETACH" in sanitized
    
    inject_sql = "Priya Nair' OR '1'='1"
    sanitized_sql = sanitize_name(inject_sql)
    assert "'" not in sanitized_sql
    
    chars = r"name`\"'{}[\]\\;"
    sanitized_chars = sanitize_name(chars)
    assert sanitized_chars == "name"


def test_sanitize_name_oversized():
    # Long strings should be truncated to 200 characters
    long_name = "A" * 300
    sanitized = sanitize_name(long_name)
    assert len(sanitized) == 200


def test_validate_extraction_result_cascade():
    # Create extraction result with adversarial fields
    entity = Entity(
        id="ent_malicious",
        name="Dev Rao; DROP DATABASE",
        entity_type=EntityType.person,
        source_meeting_ids=["meeting_01"]
    )
    result = ExtractionResult(
        meeting_id="meeting_01",
        entities=[entity]
    )
    
    validated = validate_extraction_result(result)
    
    # The name should be sanitized
    assert ";" not in validated.entities[0].name
    assert "DROP DATABASE" in validated.entities[0].name
    assert validated.entities[0].name == "Dev Rao DROP DATABASE"
