"""RED-phase tests for GeoIP + ASN enrichment (GEO-01 … GEO-05)."""
import os
import time
from unittest.mock import MagicMock, patch

from geoip2.errors import AddressNotFoundError

from pnpg.pipeline.geo_enricher import check_db_freshness, enrich_geo


def test_country_lookup():
    """GEO-01: dst_country from Country database."""
    mock_reader = MagicMock()
    resp = MagicMock()
    resp.country.iso_code = "US"
    mock_reader.country.return_value = resp
    with (
        patch("pnpg.pipeline.geo_enricher._country_reader", mock_reader),
        patch("pnpg.pipeline.geo_enricher._asn_reader", None),
    ):
        result = enrich_geo({"dst_ip": "8.8.8.8"})
    assert result["dst_country"] == "US"


def test_asn_lookup():
    """GEO-02: dst_asn and dst_org from ASN database."""
    mock_asn_reader = MagicMock()
    asn_resp = MagicMock()
    asn_resp.autonomous_system_number = 15169
    asn_resp.autonomous_system_organization = "Google LLC"
    mock_asn_reader.asn.return_value = asn_resp
    with (
        patch("pnpg.pipeline.geo_enricher._country_reader", None),
        patch("pnpg.pipeline.geo_enricher._asn_reader", mock_asn_reader),
    ):
        result = enrich_geo({"dst_ip": "8.8.8.8"})
    assert result["dst_asn"] == "AS15169"
    assert result["dst_org"] == "Google LLC"


def test_geo_latency():
    """GEO-03: enrich_geo averages under 5ms per call (100 calls < 500ms total)."""
    mock_country_reader = MagicMock()
    country_resp = MagicMock()
    country_resp.country.iso_code = "US"
    mock_country_reader.country.return_value = country_resp
    mock_asn_reader = MagicMock()
    asn_resp = MagicMock()
    asn_resp.autonomous_system_number = 15169
    asn_resp.autonomous_system_organization = "Google LLC"
    mock_asn_reader.asn.return_value = asn_resp
    with (
        patch("pnpg.pipeline.geo_enricher._country_reader", mock_country_reader),
        patch("pnpg.pipeline.geo_enricher._asn_reader", mock_asn_reader),
    ):
        t0 = time.monotonic()
        for _ in range(100):
            enrich_geo({"dst_ip": "8.8.8.8"})
        elapsed = time.monotonic() - t0
    assert elapsed < 0.5


def test_address_not_found():
    """GEO-04: AddressNotFoundError yields null geo fields."""
    mock_country = MagicMock()
    mock_country.country.side_effect = AddressNotFoundError("192.168.1.1")
    mock_asn = MagicMock()
    mock_asn.asn.side_effect = AddressNotFoundError("192.168.1.1")
    with (
        patch("pnpg.pipeline.geo_enricher._country_reader", mock_country),
        patch("pnpg.pipeline.geo_enricher._asn_reader", mock_asn),
    ):
        result = enrich_geo({"dst_ip": "192.168.1.1"})
    assert result["dst_country"] is None
    assert result["dst_asn"] is None
    assert result["dst_org"] is None


def test_readers_none_graceful():
    """GEO-04: Missing readers — null fields, no crash."""
    with (
        patch("pnpg.pipeline.geo_enricher._country_reader", None),
        patch("pnpg.pipeline.geo_enricher._asn_reader", None),
    ):
        result = enrich_geo({"dst_ip": "1.2.3.4"})
    assert result["dst_country"] is None
    assert result["dst_asn"] is None
    assert result["dst_org"] is None


def test_stale_warning(caplog, tmp_path):
    """GEO-05: Old DB file triggers GEOIP_STALE in logs."""
    f = tmp_path / "old.mmdb"
    f.write_bytes(b"x")
    old = time.time() - (31 * 86400)
    os.utime(f, (old, old))
    with caplog.at_level("WARNING"):
        check_db_freshness(str(f), 30 * 86400, "GEOIP_STALE")
    assert "GEOIP_STALE" in caplog.text


def test_missing_db_warning(caplog):
    """GEO-05: Missing DB path triggers GEOIP_STALE in logs."""
    with caplog.at_level("WARNING"):
        check_db_freshness("/nonexistent/path.mmdb", 30 * 86400, "GEOIP_STALE")
    assert "GEOIP_STALE" in caplog.text


def test_enrich_geo_immutable():
    """Original event is not mutated."""
    event = {"dst_ip": "8.8.8.8", "seq": 1}
    mock_reader = MagicMock()
    resp = MagicMock()
    resp.country.iso_code = "US"
    mock_reader.country.return_value = resp
    with (
        patch("pnpg.pipeline.geo_enricher._country_reader", mock_reader),
        patch("pnpg.pipeline.geo_enricher._asn_reader", None),
    ):
        result = enrich_geo(event)
    assert "dst_country" not in event
    assert result["dst_country"] == "US"
