#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021-23 Freie Universität Berlin
# Copyright (C) 2023-25 TU Dresden
#
# Distributed under terms of the MIT license.

import dns.message
import dns.rcode
import pytest

from aiodnsprox import dns_upstream

from .fixtures import dns_server  # noqa: F401


def test_upstream_init__unknown_transport():
    with pytest.raises(ValueError):
        dns_upstream.DNSUpstream(host="::1", transport=57)


@pytest.mark.parametrize(
    "port, transport, exp_port",
    [
        (None, dns_upstream.DNSTransport.UDP, 53),
        (None, dns_upstream.DNSTransport.UDP_TCP_FALLBACK, 53),
        (None, dns_upstream.DNSTransport.TCP, 53),
        (52387, dns_upstream.DNSTransport.UDP, 52387),
        (52387, dns_upstream.DNSTransport.UDP_TCP_FALLBACK, 52387),
        (52387, dns_upstream.DNSTransport.TCP, 52387),
    ],
)
def test_upstream_init(port, transport, exp_port):
    upstream = dns_upstream.DNSUpstream(host="::1", port=port, transport=transport)
    assert upstream.port == exp_port


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "id, transport, timeout",
    [
        (0, dns_upstream.DNSTransport.UDP, None),
        (41905, dns_upstream.DNSTransport.UDP, None),
        (0, dns_upstream.DNSTransport.UDP_TCP_FALLBACK, None),
        (41905, dns_upstream.DNSTransport.UDP_TCP_FALLBACK, None),
        (0, dns_upstream.DNSTransport.TCP, None),
        (41905, dns_upstream.DNSTransport.TCP, None),
        (0, dns_upstream.DNSTransport.UDP, 6.0),
        (41905, dns_upstream.DNSTransport.UDP, 6.0),
        (0, dns_upstream.DNSTransport.UDP_TCP_FALLBACK, 6.0),
        (41905, dns_upstream.DNSTransport.UDP_TCP_FALLBACK, 6.0),
        (0, dns_upstream.DNSTransport.TCP, 6.0),
        (41905, dns_upstream.DNSTransport.TCP, 6.0),
    ],
)
async def test_upstream_query(dns_server, id, transport, timeout):  # noqa: F811, E501
    upstream = dns_upstream.DNSUpstream(
        host=dns_server["host"], port=dns_server["port"], transport=transport
    )
    query = dns.message.make_query(
        dns_server["req_hostname"], dns_server["resp_rtype"].__name__
    )
    query.id = id
    response_bytes = await upstream.query(query.to_wire(), timeout=timeout)
    response = dns.message.from_wire(response_bytes)
    found_answer = False
    for rset in response.answer:
        for rda in rset:
            if isinstance(rda, dns_server["resp_rtype"]):
                found_answer = True
                assert rda.address == dns_server["resp_address"]
    assert found_answer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "transport",
    [
        (dns_upstream.DNSTransport.UDP),
        (dns_upstream.DNSTransport.UDP_TCP_FALLBACK),
        (dns_upstream.DNSTransport.TCP),
    ],
)
async def test_upstream_query_timeout(transport):
    upstream = dns_upstream.DNSUpstream(host="::1", port=13417, transport=transport)
    query = dns.message.make_query("example.org", "AAAA")
    response_bytes = await upstream.query(query.to_wire(), timeout=0.1)
    response = dns.message.from_wire(response_bytes)
    assert response.rcode() == dns.rcode.SERVFAIL


def test_mock_upstream_init__unknown_address_type():
    with pytest.raises(TypeError):
        dns_upstream.MockDNSUpstream(IN={"A": dns.message.Message()})
    with pytest.raises(TypeError):
        dns_upstream.MockDNSUpstream(IN={"AAAA": dns.message.Message()})


@pytest.mark.parametrize(
    "A, AAAA",
    [
        ("10.0.0", None),
        ("10.0.0.1.2", None),
        (None, "2001:db8::1::1"),
        ("2001:db8::1", "10.0.0.1"),
        (b"\x0a\0\0\1\3", None),
        (b"\x0a\0\0", None),
        (None, b"\x20\x01\x0d\xb8" + (b"\0" * 11) + b"\1\3"),
        (None, b"\x20\x01\x0d\xb8"),
    ],  # pylint: disable=invalid-name
)
def test_mock_upstream_init__invalid_addresses(A, AAAA):
    IN = {}  # pylint: disable=invalid-name
    if A is not None:
        IN["A"] = A
    if AAAA is not None:
        IN["AAAA"] = AAAA
    with pytest.raises(ValueError):
        dns_upstream.MockDNSUpstream(IN=IN)


@pytest.mark.parametrize(
    "A, AAAA",
    [
        (None, None),
        ("10.0.0.1", None),
        (None, "2001:db8::1"),
        ("10.0.0.1", "2001:db8::1"),
        (b"\x0a\0\0\1", None),
        (None, b"\x20\x01\x0d\xb8" + (b"\0" * 11) + b"\1"),
    ],  # pylint: disable=invalid-name
)
def test_mock_upstream_init__success(A, AAAA):
    IN = {}  # pylint: disable=invalid-name
    if A is not None:
        IN["A"] = A
    if AAAA is not None:
        IN["AAAA"] = AAAA
    upstream = dns_upstream.MockDNSUpstream(IN=IN)
    if A is not None:
        assert "A" in upstream._IN  # pylint: disable=protected-access
    if AAAA is not None:
        assert "AAAA" in upstream._IN  # pylint: disable=protected-access


@pytest.mark.asyncio
async def test_mock_upstream_query_a():
    IN = {"A": "10.0.0.1"}  # pylint: disable=invalid-name
    upstream = dns_upstream.MockDNSUpstream(IN=IN)
    found_answer = False
    query = dns.message.make_query("example.org", "A").to_wire()
    response = dns.message.from_wire(await upstream.query(query))
    for rset in response.answer:
        for rda in rset:
            if isinstance(rda, dns.rdtypes.IN.A.A):
                found_answer = True
                assert rda.address == IN["A"]
    assert found_answer


@pytest.mark.asyncio
async def test_mock_upstream_query_aaaa():
    IN = {"AAAA": "2001:db8::1"}  # pylint: disable=invalid-name
    upstream = dns_upstream.MockDNSUpstream(IN=IN)
    found_answer = False
    query = dns.message.make_query("example.org", "AAAA").to_wire()
    response = dns.message.from_wire(await upstream.query(query))
    for rset in response.answer:
        for rda in rset:
            if isinstance(rda, dns.rdtypes.IN.AAAA.AAAA):
                found_answer = True
                assert rda.address == IN["AAAA"]
    assert found_answer


@pytest.mark.asyncio
async def test_mock_upstream_query_a_and_aaa():
    IN = {  # pylint: disable=invalid-name
        "A": "10.0.0.1",
        "AAAA": "::1",
    }
    upstream = dns_upstream.MockDNSUpstream(IN=IN)
    found_answer = 0
    query = dns.message.make_query("example.org", "A")
    query.find_rrset(
        query.question,
        dns.name.from_text("v6.example.org"),
        dns.rdataclass.IN,
        dns.rdatatype.AAAA,
        create=True,
        force_unique=True,
    )
    response = dns.message.from_wire(await upstream.query(query.to_wire()))
    for rset in response.answer:
        for rda in rset:
            if isinstance(rda, dns.rdtypes.IN.A.A):
                found_answer += 1
                assert rda.address == IN["A"]
            if isinstance(rda, dns.rdtypes.IN.AAAA.AAAA):
                found_answer += 1
                assert rda.address == IN["AAAA"]
    assert found_answer == 2


@pytest.mark.asyncio
async def test_mock_upstream_query_cname():
    IN = {  # pylint: disable=invalid-name
        "A": "10.0.0.1",
        "AAAA": "::1",
    }
    upstream = dns_upstream.MockDNSUpstream(IN=IN)
    found_answer = 0
    query = dns.message.make_query("example.org", "CNAME")
    response = dns.message.from_wire(await upstream.query(query.to_wire()))
    for rset in response.answer:
        for rda in rset:
            if isinstance(rda, dns.rdtypes.IN.A.A):
                found_answer += 1
            if isinstance(rda, dns.rdtypes.IN.AAAA.AAAA):
                found_answer += 1
    assert found_answer == 0


@pytest.mark.asyncio
async def test_mock_upstream_query_non_in():
    IN = {  # pylint: disable=invalid-name
        "A": "10.0.0.1",
        "AAAA": "::1",
    }
    upstream = dns_upstream.MockDNSUpstream(IN=IN)
    found_answer = 0
    query = dns.message.make_query("example.org", "CNAME", rdclass="CHAOS")
    response = dns.message.from_wire(await upstream.query(query.to_wire()))
    for rset in response.answer:
        for rda in rset:
            if isinstance(rda, dns.rdtypes.IN.A.A):
                found_answer += 1
            if isinstance(rda, dns.rdtypes.IN.AAAA.AAAA):
                found_answer += 1
    assert found_answer == 0
