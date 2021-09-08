# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

from .dns_upstream import DNSUpstreamProtocolMixin
from .server_protocol_factory import BaseServerProtocolFactory


class DNSOverUDPServerProtocolFactory(BaseServerProtocolFactory):
    # pylint: disable=too-few-public-methods
    class DNSOverUDPServerProtocol(DNSUpstreamProtocolMixin):
        def __init__(self, factory):
            super().__init__(
                host=factory.upstream_host,
                port=factory.upstream_port,
                transport=factory.upstream_transport,
                timeout=factory.upstream_timeout
            )
            self.transport = None

        def connection_made(self, transport):
            self.transport = transport

        def datagram_received(self, data, addr):
            self.query_received(data, addr)

        def error_received(self, exc):  # pylint: disable=no-self-use
            raise exc   # pragma: no cover

        def send_response_to_requester(self, response, requester):
            self.transport.sendto(response, requester)

    def create_server_protocol(self, *args, **kwargs):
        return self.DNSOverUDPServerProtocol(self, *args, **kwargs)
