#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import dns.message
import dns.rcode
import pytest

from aiodnsprox import dns_upstream

from .fixtures import dns_server        # noqa: F401


def test_upstream_init__unknown_transport():
    with pytest.raises(ValueError):
        dns_upstream.DNSUpstream(
            host='::1',
            transport=57
        )


@pytest.mark.parametrize(
    'port, transport, exp_port',
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
    upstream = dns_upstream.DNSUpstream(
        host='::1',
        port=port,
        transport=transport
    )
    assert upstream.port == exp_port


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'id, transport, timeout', [
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
    ]
)
async def test_upstream_query(dns_server, id, transport, timeout):  # noqa: F811, E501
    upstream = dns_upstream.DNSUpstream(
        host=dns_server['host'],
        port=dns_server['port'],
        transport=transport
    )
    query = dns.message.make_query(dns_server['req_hostname'],
                                   dns_server['resp_rtype'].__name__)
    query.id = id
    response_bytes = await upstream.query(query.to_wire(), timeout=timeout)
    response = dns.message.from_wire(response_bytes)
    found_answer = False
    for rset in response.answer:
        for rda in rset:
            if isinstance(rda, dns_server['resp_rtype']):
                found_answer = True
                assert rda.address == dns_server['resp_address']
    assert found_answer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'transport', [
        (dns_upstream.DNSTransport.UDP),
        (dns_upstream.DNSTransport.UDP_TCP_FALLBACK),
        (dns_upstream.DNSTransport.TCP),
    ]
)
async def test_upstream_query_timeout(transport):
    upstream = dns_upstream.DNSUpstream(
        host='::1',
        port=13417,
        transport=transport
    )
    query = dns.message.make_query('example.org', 'AAAA')
    response_bytes = await upstream.query(query.to_wire(), timeout=0.1)
    response = dns.message.from_wire(response_bytes)
    assert response.rcode() == dns.rcode.SERVFAIL
