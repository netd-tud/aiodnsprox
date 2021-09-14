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

from aiodnsprox import dtls

from .fixtures import dns_server        # noqa: F401


@pytest.mark.asyncio
async def test_dtls_proxy(dns_server):   # noqa: C901, F811
    proxy_bind = ('::1', 2304)
    psk_id = b"Client_identifier"
    psk_store = {psk_id: b"secretPSK"}

    class ClientProtocol(asyncio.DatagramProtocol):
        def __init__(self, loop, on_connection_lost):
            self.loop = loop
            self.on_connection_lost = on_connection_lost
            self.result = None
            self.transport = None
            self._dtls = None

        def send_query(self, session):
            query = dns.message.make_query(dns_server['req_hostname'],
                                           dns_server['resp_rtype'].__name__)
            self._dtls.write(query.to_wire(), session)

        def connection_made(self, transport):
            self.transport = transport
            self._dtls = dtls.TinyDTLSWrapper(transport, psk_id, psk_store)
            self._dtls.connect(proxy_bind)

        def datagram_received(self, response, session):
            data, addr, connected = self._dtls.handle_message(response,
                                                              session)
            # during handle message the client connected
            if connected:
                self.send_query(session)
                return
            if data is not None:
                self.result = (dns.message.from_wire(data), addr)
                self.transport.close()

        def error_received(self, exc):
            raise exc

        def connection_lost(self, exc):
            self.on_connection_lost.set_result(self.result)

    factory = dtls.DNSOverDTLSServerFactory(dns_server['host'],
                                            dns_server['port'])
    loop = asyncio.get_running_loop()
    server = await factory.create_server(
        loop,
        psk_id,
        psk_store,
        local_addr=proxy_bind
    )
    try:
        on_connection_lost = loop.create_future()
        client_transport, _ = await loop.create_datagram_endpoint(
            lambda: ClientProtocol(loop, on_connection_lost),
            remote_addr=proxy_bind
        )
        try:
            response, addr = await on_connection_lost
            assert addr[:2] == (proxy_bind[0], proxy_bind[1])
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
        server.close()
        server.close()  # call second time to check idempotency


# @pytest.mark.asyncio
# @pytest.mark.parametrize(
    # 'local_addr', [None, ('localhost', None)]
# )
# async def test_udp_factory_create_datagram_endpoint(local_addr, mocker):
    # loop = mocker.MagicMock()
    # loop.create_datagram_endpoint = mocker.AsyncMock(return_value=(0, 0))
    # factory = udp.DNSOverUDPServerProtocolFactory("localhost", 53)
    # await factory.create_server(loop, local_addr=local_addr)
    # loop.create_datagram_endpoint.assert_called_once()
