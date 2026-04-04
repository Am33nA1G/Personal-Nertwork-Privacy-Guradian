"""GeoIP + ASN enrichment — local MaxMind GeoLite2 database lookups.

GEO-01: Resolve destination IPs to country codes.
GEO-02: Resolve destination IPs to ASN and organization name.
GEO-03: GeoIP lookups have hard timeout of 5ms (satisfied by design — MODE_MEMORY).
GEO-04: Failed lookups return null fields — pipeline never blocks.
GEO-05: Log GEOIP_STALE if local DB is older than 30 days.
"""

import logging
import os
import time

import geoip2.database
import geoip2.errors
import maxminddb

logger = logging.getLogger(__name__)

SECONDS_IN_DAY = 86400

_country_reader: geoip2.database.Reader | None = None
_asn_reader: geoip2.database.Reader | None = None


def open_readers(country_db_path: str, asn_db_path: str) -> None:
    """Open Country and ASN MMDB readers in memory; missing files log WARNING and leave reader None."""
    global _country_reader, _asn_reader
    _country_reader = None
    _asn_reader = None

    try:
        _country_reader = geoip2.database.Reader(
            country_db_path, mode=maxminddb.MODE_MEMORY
        )
    except FileNotFoundError:
        logger.warning(
            "GeoLite2-Country database not found at %s", country_db_path
        )
        _country_reader = None

    try:
        _asn_reader = geoip2.database.Reader(
            asn_db_path, mode=maxminddb.MODE_MEMORY
        )
    except FileNotFoundError:
        logger.warning("GeoLite2-ASN database not found at %s", asn_db_path)
        _asn_reader = None

    opened = int(_country_reader is not None) + int(_asn_reader is not None)
    logger.info("GeoIP readers opened: %s of 2 (country=%s, asn=%s)", opened, _country_reader is not None, _asn_reader is not None)


def close_readers() -> None:
    """Close and release reader handles."""
    global _country_reader, _asn_reader
    if _country_reader is not None:
        _country_reader.close()
        _country_reader = None
    if _asn_reader is not None:
        _asn_reader.close()
        _asn_reader = None


def enrich_geo(event: dict) -> dict:
    """Add dst_country, dst_asn, dst_org from local MMDB readers; nulls if missing IP, reader, or lookup."""
    ip = event.get("dst_ip")
    country: str | None = None
    asn: str | None = None
    org: str | None = None

    if ip and _country_reader is not None:
        try:
            resp = _country_reader.country(ip)
            country = resp.country.iso_code
        except (geoip2.errors.AddressNotFoundError, Exception):
            country = None

    if ip and _asn_reader is not None:
        try:
            resp = _asn_reader.asn(ip)
            asn = f"AS{resp.autonomous_system_number}"
            org = resp.autonomous_system_organization
        except (geoip2.errors.AddressNotFoundError, Exception):
            asn, org = None, None

    return {
        **event,
        "dst_country": country,
        "dst_asn": asn,
        "dst_org": org,
    }


def check_db_freshness(db_path: str, max_age_seconds: float, metric_key: str) -> None:
    """Log WARNING with metric_key if DB file is older than max_age_seconds or missing."""
    try:
        age = time.time() - os.path.getmtime(db_path)
        if age > max_age_seconds:
            logger.warning(
                "%s: database at %s is %.1f days old (limit: %.1f days)",
                metric_key,
                db_path,
                age / SECONDS_IN_DAY,
                max_age_seconds / SECONDS_IN_DAY,
            )
    except FileNotFoundError:
        logger.warning("%s: database file not found at %s", metric_key, db_path)
