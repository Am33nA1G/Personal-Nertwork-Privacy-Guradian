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


# ---------------------------------------------------------------------------
# open_readers / close_readers
# ---------------------------------------------------------------------------


def test_open_readers_both_success(tmp_path):
    """open_readers sets both _country_reader and _asn_reader when files exist."""
    import geoip2.database
    from pnpg.pipeline.geo_enricher import open_readers, close_readers
    import pnpg.pipeline.geo_enricher as geo_mod
    from unittest.mock import MagicMock, patch

    mock_reader = MagicMock(spec=geoip2.database.Reader)

    with patch("geoip2.database.Reader", return_value=mock_reader):
        open_readers("fake_country.mmdb", "fake_asn.mmdb")

    assert geo_mod._country_reader is mock_reader
    assert geo_mod._asn_reader is mock_reader

    # Cleanup
    geo_mod._country_reader = None
    geo_mod._asn_reader = None


def test_open_readers_country_missing(tmp_path, caplog):
    """open_readers logs a warning and sets _country_reader=None when country file is absent."""
    import geoip2.database
    from pnpg.pipeline.geo_enricher import open_readers
    import pnpg.pipeline.geo_enricher as geo_mod
    from unittest.mock import MagicMock, patch

    mock_asn_reader = MagicMock(spec=geoip2.database.Reader)

    def reader_factory(path, mode=None):
        if "country" in path.lower():
            raise FileNotFoundError(path)
        return mock_asn_reader

    with patch("geoip2.database.Reader", side_effect=reader_factory):
        with caplog.at_level("WARNING"):
            open_readers("missing_country.mmdb", "fake_asn.mmdb")

    assert geo_mod._country_reader is None
    assert geo_mod._asn_reader is mock_asn_reader
    assert "Country" in caplog.text or "country" in caplog.text

    # Cleanup
    geo_mod._country_reader = None
    geo_mod._asn_reader = None


def test_open_readers_asn_missing(tmp_path, caplog):
    """open_readers logs a warning and sets _asn_reader=None when ASN file is absent."""
    import geoip2.database
    from pnpg.pipeline.geo_enricher import open_readers
    import pnpg.pipeline.geo_enricher as geo_mod
    from unittest.mock import MagicMock, patch

    mock_country_reader = MagicMock(spec=geoip2.database.Reader)

    def reader_factory(path, mode=None):
        if "asn" in path.lower():
            raise FileNotFoundError(path)
        return mock_country_reader

    with patch("geoip2.database.Reader", side_effect=reader_factory):
        with caplog.at_level("WARNING"):
            open_readers("fake_country.mmdb", "missing_asn.mmdb")

    assert geo_mod._country_reader is mock_country_reader
    assert geo_mod._asn_reader is None
    assert "ASN" in caplog.text or "asn" in caplog.text

    # Cleanup
    geo_mod._country_reader = None
    geo_mod._asn_reader = None


def test_close_readers_resets_globals():
    """close_readers calls close() on open readers and sets both to None."""
    import geoip2.database
    from pnpg.pipeline.geo_enricher import close_readers
    import pnpg.pipeline.geo_enricher as geo_mod
    from unittest.mock import MagicMock

    mock_country = MagicMock(spec=geoip2.database.Reader)
    mock_asn = MagicMock(spec=geoip2.database.Reader)

    geo_mod._country_reader = mock_country
    geo_mod._asn_reader = mock_asn

    close_readers()

    mock_country.close.assert_called_once()
    mock_asn.close.assert_called_once()
    assert geo_mod._country_reader is None
    assert geo_mod._asn_reader is None


def test_close_readers_when_already_none():
    """close_readers is safe to call when readers are already None."""
    from pnpg.pipeline.geo_enricher import close_readers
    import pnpg.pipeline.geo_enricher as geo_mod

    geo_mod._country_reader = None
    geo_mod._asn_reader = None

    close_readers()  # Must not raise

    assert geo_mod._country_reader is None
    assert geo_mod._asn_reader is None
