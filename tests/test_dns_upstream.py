#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import random
import subprocess

import dns.message
import pytest

from dns.rdtypes.IN.AAAA import AAAA

from aiodnsprox import dns_upstream


TEST_HOSTNAME = 'example.org'
TEST_ADDRESS = '2001:db8::1'


@pytest.fixture
def dns_server():
    port = random.randint(1 << 2, 0xff) << 8 | 53
    proc = subprocess.Popen(
        ['dnsmasq', '-k', '-p', str(port),
         f'--host-record={TEST_HOSTNAME},{TEST_ADDRESS}']
    )
    yield {'host': '::1', 'port': port}
    proc.kill()
    proc.wait()


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
    'id, transport', [
        (0, dns_upstream.DNSTransport.UDP),
        (41905, dns_upstream.DNSTransport.UDP),
        (0, dns_upstream.DNSTransport.UDP_TCP_FALLBACK),
        (41905, dns_upstream.DNSTransport.UDP_TCP_FALLBACK),
        (0, dns_upstream.DNSTransport.TCP),
        (41905, dns_upstream.DNSTransport.TCP),
    ]
)
async def test_upstream_query(dns_server, id, transport):
    upstream = dns_upstream.DNSUpstream(
        host=dns_server['host'],
        port=dns_server['port'],
        transport=transport
    )
    query = dns.message.make_query(TEST_HOSTNAME, 'AAAA')
    query.id = id
    response_bytes = await upstream.query(query.to_wire())
    response = dns.message.from_wire(response_bytes)
    found_answer = False
    for rset in response.answer:
        for rd in rset:
            if isinstance(rd, AAAA):
                found_answer = True
                assert rd.address == TEST_ADDRESS
    assert found_answer
