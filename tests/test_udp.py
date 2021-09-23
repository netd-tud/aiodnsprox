#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import asyncio
import socket

import dns.message
import pytest

from aiodnsprox import dns_upstream
from aiodnsprox import udp

from .fixtures import dns_server        # noqa: F401


@pytest.mark.asyncio
async def test_udp_proxy(dns_server):   # noqa: C901, F811
    proxy_bind = ('::1', 59462)

    class ClientProtocol(asyncio.DatagramProtocol):
        def __init__(self, on_connection_lost):
            self.on_connection_lost = on_connection_lost
            self.result = None
            self.transport = None

        def connection_made(self, transport):
            query = dns.message.make_query(dns_server['req_hostname'],
                                           dns_server['resp_rtype'].__name__)
            self.transport = transport
            self.transport.sendto(query.to_wire())

        def datagram_received(self, response, addr):
            self.result = (dns.message.from_wire(response), addr)
            self.transport.close()

        def error_received(self, exc):
            raise exc

        def connection_lost(self, exc):
            self.on_connection_lost.set_result(self.result)

    upstream = dns_upstream.DNSUpstream(dns_server['host'], dns_server['port'])
    factory = udp.DNSOverUDPServerFactory(upstream)
    loop = asyncio.get_running_loop()
    server = await factory.create_server(
        loop,
        local_addr=proxy_bind
    )
    try:
        on_connection_lost = loop.create_future()
        client_transport, _ = await loop.create_datagram_endpoint(
            lambda: ClientProtocol(on_connection_lost),
            remote_addr=proxy_bind
        )
        try:
            response, addr = await on_connection_lost
            assert addr == (proxy_bind[0], proxy_bind[1], 0, 0)
            found_answer = False
            for rset in response.answer:
                for rda in rset:
                    if isinstance(rda, dns_server['resp_rtype']):
                        found_answer = True
                        assert rda.address == dns_server['resp_address']
            assert found_answer
        finally:
            client_transport.close()
    finally:
        await server.close()
        await server.close()    # call second time to check idempotency


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'local_addr', [None, ('localhost', None)]
)
async def test_udp_factory_create_server(local_addr, mocker):
    loop = mocker.MagicMock()
    future = asyncio.Future()
    future.set_result((0, 0))
    loop.create_datagram_endpoint.return_value = future
    upstream = dns_upstream.DNSUpstream("localhost", 53)
    factory = udp.DNSOverUDPServerFactory(upstream)
    server = await factory.create_server(loop, local_addr=local_addr)
    loop.create_datagram_endpoint.assert_called_once()
    del server
