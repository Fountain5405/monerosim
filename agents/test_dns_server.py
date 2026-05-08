"""Smoke tests for agents.dns_server.MoneroResolver.

We test the resolver in isolation (no socket binding, no MoneroDNSServer).
The resolver is the entire request-handling surface: given a DNSRecord
question and a handler, .resolve() returns a reply with answer RRs or
NXDOMAIN. The DNSServer wrapper itself just plumbs UDP/TCP sockets, which
isn't worth unit-testing.
"""
import json
import logging

import pytest
from dnslib import DNSRecord, QTYPE, RCODE

from agents.dns_server import MoneroResolver


def _question(qname, qtype="A"):
    """Build a DNSRecord query for *qname* / *qtype* (e.g. 'A', 'TXT')."""
    return DNSRecord.question(qname, qtype)


@pytest.fixture
def resolver(shared_dir):
    """A MoneroResolver pinned to the per-test shared dir."""
    logger = logging.getLogger("test-dns-resolver")
    return MoneroResolver(shared_dir=shared_dir, logger=logger)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

def test_constructor_does_not_raise(shared_dir):
    """Resolver constructs cleanly with empty shared dir; caches are empty."""
    logger = logging.getLogger("test-dns")
    r = MoneroResolver(shared_dir=shared_dir, logger=logger)
    assert r.shared_dir == shared_dir
    assert r.seed_ips == []
    assert r.checkpoints == {}


# ---------------------------------------------------------------------------
# Seed-domain A queries
# ---------------------------------------------------------------------------

def test_resolve_seed_domain_returns_a_records_from_miners(resolver, shared_dir):
    """A seed-domain A-query returns one A record per miner IP in the registry.

    With no monero-seed hosts configured (legacy fallback path), the resolver
    falls back to using miner IPs as seed answers.
    """
    (shared_dir / "agent_registry.json").write_text(json.dumps({
        "agents": [
            {"id": "m1", "ip_addr": "10.0.0.1", "attributes": {"is_miner": "true"}},
            {"id": "m2", "ip_addr": "10.0.0.2", "attributes": {"is_miner": "true"}},
            {"id": "u1", "ip_addr": "10.0.0.99", "attributes": {"is_miner": "false"}},
        ]
    }))
    reply = resolver.resolve(_question("seeds.moneroseeds.se."), handler=None)
    answers = list(reply.rr)
    assert len(answers) == 2
    # rdata stringifies to the IP address.
    ips = {str(rr.rdata) for rr in answers}
    assert ips == {"10.0.0.1", "10.0.0.2"}
    # Reply is NOERROR (0), not NXDOMAIN.
    assert reply.header.rcode == RCODE.NOERROR


def test_resolve_seed_domain_prefers_seed_node_hosts(resolver, shared_dir):
    """When monero-seed hosts exist, miners are NOT used as fallbacks."""
    (shared_dir / "agent_registry.json").write_text(json.dumps({
        "agents": [
            {"id": "s1", "ip_addr": "10.1.0.1",
             "attributes": {"is_seed_node": "true"}},
            {"id": "m1", "ip_addr": "10.0.0.1",
             "attributes": {"is_miner": "true"}},
        ]
    }))
    reply = resolver.resolve(_question("seeds.moneroseeds.ch."), handler=None)
    ips = {str(rr.rdata) for rr in reply.rr}
    # Only the seed-node IP is returned; miner is excluded.
    assert ips == {"10.1.0.1"}


def test_resolve_seed_domain_with_no_registry_returns_empty_answer(resolver):
    """Seed-domain query with no registry file: NOERROR, zero answers."""
    reply = resolver.resolve(_question("seeds.moneroseeds.li."), handler=None)
    assert len(list(reply.rr)) == 0
    # Note: implementation returns NOERROR with 0 RRs (not NXDOMAIN) for
    # seed domains - this is intentional for empty seed lists.
    assert reply.header.rcode == RCODE.NOERROR


# ---------------------------------------------------------------------------
# NXDOMAIN for unknown names
# ---------------------------------------------------------------------------

def test_resolve_unknown_domain_returns_nxdomain(resolver):
    """A name that's not in the seed/checkpoint domain sets returns NXDOMAIN."""
    reply = resolver.resolve(_question("example.com."), handler=None)
    assert reply.header.rcode == RCODE.NXDOMAIN
    assert len(list(reply.rr)) == 0


def test_resolve_seed_domain_with_wrong_qtype_returns_nxdomain(resolver):
    """An MX query for a known seed domain falls through to NXDOMAIN."""
    reply = resolver.resolve(_question("seeds.moneroseeds.se.", qtype="MX"),
                             handler=None)
    assert reply.header.rcode == RCODE.NXDOMAIN


# ---------------------------------------------------------------------------
# Registry cache TTL
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# MoneroDNSServer wrapper: logger idempotency
# ---------------------------------------------------------------------------

def test_dns_server_setup_logging_is_idempotent(shared_dir):
    """Re-instantiating MoneroDNSServer with the same agent_id must not
    double-add stream handlers to the shared named logger."""
    from agents.dns_server import MoneroDNSServer

    s1 = MoneroDNSServer(
        agent_id="dns-test",
        shared_dir=shared_dir,
        bind_ip="127.0.0.1",
        port=0,
        log_level="INFO",
    )
    handlers_after_first = len(s1.logger.handlers)

    s2 = MoneroDNSServer(
        agent_id="dns-test",
        shared_dir=shared_dir,
        bind_ip="127.0.0.1",
        port=0,
        log_level="INFO",
    )
    assert len(s2.logger.handlers) == handlers_after_first


def test_seed_ip_cache_refreshes_after_ttl(resolver, shared_dir, mocker):
    """The seed-IP cache rereads the registry once TTL has elapsed."""
    (shared_dir / "agent_registry.json").write_text(json.dumps({
        "agents": [{"id": "s1", "ip_addr": "10.1.0.1",
                    "attributes": {"is_seed_node": "true"}}]
    }))
    # First call at t=100 populates the cache.
    mock_time = mocker.patch("agents.dns_server.time.time", return_value=100.0)
    reply1 = resolver.resolve(_question("seeds.moneroseeds.se."), handler=None)
    assert {str(rr.rdata) for rr in reply1.rr} == {"10.1.0.1"}

    # Mutate registry, advance past 5s TTL.
    (shared_dir / "agent_registry.json").write_text(json.dumps({
        "agents": [
            {"id": "s1", "ip_addr": "10.1.0.1",
             "attributes": {"is_seed_node": "true"}},
            {"id": "s2", "ip_addr": "10.1.0.2",
             "attributes": {"is_seed_node": "true"}},
        ]
    }))
    mock_time.return_value = 200.0
    reply2 = resolver.resolve(_question("seeds.moneroseeds.se."), handler=None)
    assert {str(rr.rdata) for rr in reply2.rr} == {"10.1.0.1", "10.1.0.2"}
