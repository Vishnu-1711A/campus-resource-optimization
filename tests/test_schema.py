"""
Unit tests for schema integrity, relational joins, and analytics calculations.
"""

from app import crud, database


def test_kpi_metrics():
    kpis = crud.get_dashboard_kpis()
    assert kpis["total_resources"] >= 10
    assert kpis["available_resources"] > 0
    assert kpis["open_maintenance"] > 0
    assert len(kpis["category_counts"]) > 0


def test_resource_filtering():
    # Filter by building 'Golden Jubilee Block'
    gjbc_resources = crud.get_all_resources(building="Golden Jubilee Block")
    assert len(gjbc_resources) > 0
    for r in gjbc_resources:
        assert r["building"] == "Golden Jubilee Block"


def test_analytics_queries_execution():
    queries = crud.get_analytics_queries_results()
    assert len(queries) == 10
    for q in queries:
        assert "id" in q
        assert "title" in q
        assert "sql" in q
        assert isinstance(q["data"], list)
