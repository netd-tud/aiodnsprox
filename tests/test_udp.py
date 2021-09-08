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

        def send_response_to_requester(self, response, requester):
            self.transport.sendto(resp, requester)

        def error_received(self, exc):
            raise exc

        def connection_lost(self, exc):
            self.on_connection_lost.set_result(self.result)

    factory = udp.DNSOverUDPServerProtocolFactory(dns_server['host'],
                                                  dns_server['port'])
    loop = asyncio.get_running_loop()
    server_transport, _ = await loop.create_datagram_endpoint(
        factory.create_server_protocol,
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
        server_transport.close()
