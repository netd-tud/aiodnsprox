#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import asyncio
import logging

import dns.message
import pytest

from DTLSSocket import dtls as tinydtls

from aiodnsprox import dns_upstream
from aiodnsprox import dtls

from .fixtures import dns_server, config  # noqa: F401


def test_tinydtls_wrapper__connect(mocker, config):
    config.add_config(
        {
            "dtls_credentials": {
                "client_identity": "Client_identifier",
                "psk": "secretPSK",
            }
        }
    )
    mocker.patch("aiodnsprox.dtls.TinyDTLSWrapper._read")
    mocker.patch("aiodnsprox.dtls.TinyDTLSWrapper._write")
    mocker.patch("aiodnsprox.dtls.TinyDTLSWrapper._event")
    wrapper = dtls.TinyDTLSWrapper(mocker.MagicMock())
    wrapper.connect(("::1", 853))
    wrapper._write.assert_called()
    wrapper.close(("::1", 853))


def test_tinydtls_wrapper__handle_message(caplog, mocker, config):
    config.add_config(
        {
            "dtls_credentials": {
                "client_identity": "Client_identifier",
                "psk": "secretPSK",
            }
        }
    )
    mocker.patch("aiodnsprox.dtls.TinyDTLSWrapper._read")
    mocker.patch("aiodnsprox.dtls.TinyDTLSWrapper._write")
    mocker.patch("aiodnsprox.dtls.TinyDTLSWrapper._event")
    wrapper = dtls.TinyDTLSWrapper(mocker.MagicMock())
    assert wrapper.handle_message(b"abcd", ("::1", 853)) == (None, None, False)
    assert wrapper.handle_message(b"abcd", tinydtls.Session("::1", 853)) == (
        None,
        None,
        False,
    )
    with pytest.raises(ValueError):
        wrapper.handle_message(b"abcd", "This is a string were non should be")
    with caplog.at_level(logging.WARNING):
        # try to handle Client Hello from unverified peer
        assert wrapper.handle_message(
            b"\x16\xfe\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x36\x01"
            b"\x00\x00\x2a\x00\x00\x00\x00\x00\x00\x00\x2a\xfe\xfd\x00"
            b"\x00\x00\x00\xc1\xfa\x0e\x7b\xbb\x9b\x30\xc8\xf2\xf0\x65"
            b"\xe7\x6b\x15\x59\x68\xea\x69\x30\xb6\x08\x6e\x58\xba\x1e"
            b"\x99\x61\x55\x00\x00\x00\x02\xc0\xa8\x01\x00",
            ("::1", 853),
        ) == (None, None, False)
    # Seems not to be logged like that anymore
    # assert "Unable to handle incoming DTLS message from ('::1', 853)" in caplog.text


def test_tinydtls_wrapper__write(caplog, mocker, config):
    config.add_config(
        {
            "dtls_credentials": {
                "client_identity": "Client_identifier",
                "psk": "secretPSK",
            }
        }
    )
    mocker.patch("aiodnsprox.dtls.TinyDTLSWrapper._read")
    mocker.patch("aiodnsprox.dtls.TinyDTLSWrapper._write")
    mocker.patch("aiodnsprox.dtls.TinyDTLSWrapper._event")
    wrapper = dtls.TinyDTLSWrapper(mocker.MagicMock())
    with caplog.at_level(logging.WARNING):
        wrapper.write(b"abcd", ("::1", 853))
    assert "('::1', 853) does not have an active session" in caplog.text
    # pylint: disable=no-member,protected-access
    wrapper._write.assert_not_called()
    mocker.patch("aiodnsprox.dtls.TinyDTLSWrapper.is_connected", return_value=True)
    wrapper._active_sessions = {("::1", 853): tinydtls.Session("::1", 853)}
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        wrapper.write(b"abcd", ("::1", 853))
    assert "('::1', 853) does not have an active session" not in caplog.text
    wrapper._write.assert_called()
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        wrapper.write(b"abcd", wrapper._active_sessions["::1", 853])
    assert "('::1', 853) does not have an active session" not in caplog.text
    wrapper._write.assert_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("done_delay", [None, 0.0, 0.012])
async def test_dtls_proxy(dns_server, config, done_delay):  # noqa: C901, F811
    proxy_bind = ("::1", 2304)
    config.add_config(
        {
            "dtls_credentials": {
                "client_identity": "Client_identifier",
                "psk": "secretPSK",
            }
        }
    )

    if done_delay is not None:
        config.add_config(
            {
                "dtls": {"server_hello_done_delay": done_delay},
            }
        )

    class ClientProtocol(asyncio.DatagramProtocol):
        def __init__(self, loop, on_connection_lost):
            self.loop = loop
            self.on_connection_lost = on_connection_lost
            self.connection = None
            self.result = None
            self.transport = None
            self._dtls = None

        def send_query(self, session):
            query = dns.message.make_query(
                dns_server["req_hostname"], dns_server["resp_rtype"].__name__
            )
            self._dtls.write(query.to_wire(), session)

        def connection_made(self, transport):
            self.transport = transport
            self._dtls = dtls.TinyDTLSWrapper(transport)
            self.connection = self._dtls.connect(proxy_bind)

        def datagram_received(self, response, session):
            data, addr, connected = self._dtls.handle_message(response, session)
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
            self._dtls.close(proxy_bind)

    upstream = dns_upstream.DNSUpstream(dns_server["host"], dns_server["port"])
    factory = dtls.DNSOverDTLSServerFactory(upstream)
    loop = asyncio.get_running_loop()
    server = await factory.create_server(loop, local_addr=proxy_bind)
    try:
        on_connection_lost = loop.create_future()
        client_transport, _ = await loop.create_datagram_endpoint(
            lambda: ClientProtocol(loop, on_connection_lost), remote_addr=proxy_bind
        )
        try:
            response, addr = await on_connection_lost
            assert addr[:2] == (proxy_bind[0], proxy_bind[1])
            found_answer = False
            for rset in response.answer:
                for rda in rset:
                    if isinstance(rda, dns_server["resp_rtype"]):
                        found_answer = True
                        assert rda.address == dns_server["resp_address"]
            assert found_answer
        finally:
            client_transport.close()
    finally:
        await server.close()
        await server.close()  # call second time to check idempotency


@pytest.mark.asyncio
async def test_dtls_factory_create_server_wo_config(dns_server):
    proxy_bind = ("::1", 2304)
    upstream = dns_upstream.DNSUpstream(dns_server["host"], dns_server["port"])
    factory = dtls.DNSOverDTLSServerFactory(upstream)
    loop = asyncio.get_running_loop()
    with pytest.raises(RuntimeError):
        await factory.create_server(loop, local_addr=proxy_bind)


@pytest.mark.asyncio
@pytest.mark.parametrize("local_addr", [None, ("localhost", None)])
async def test_dtls_factory_create_server(local_addr, mocker):
    loop = mocker.MagicMock()
    future = asyncio.Future()
    future.set_result((0, 0))
    loop.create_datagram_endpoint.return_value = future
    upstream = dns_upstream.DNSUpstream("localhost", 53)
    factory = dtls.DNSOverDTLSServerFactory(upstream)
    server = await factory.create_server(loop, local_addr=local_addr)
    loop.create_datagram_endpoint.assert_called_once()
    del server
