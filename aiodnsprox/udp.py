# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

"""DNS over UDP serving side of the proxy."""

import socket
import struct
import sys

from .config import Config
from .dns_server import BaseServerFactory, BaseDNSServer
from .dns_upstream import DNSUpstreamServerMixin


class DNSOverUDPServerFactory(BaseServerFactory):
    """Factory to create DNS over UDP servers"""

    # pylint: disable=too-few-public-methods
    DNS_PORT = 53

    class DNSOverUDPServer(BaseDNSServer, DNSUpstreamServerMixin):
        """DNS over UDP server implementation

        :param factory: The factory that created the DNS over DTLS server.
        :type factory: :py:class:`DNSOverUDPServerFactory`
        """

        def __init__(self, factory):
            super().__init__(dns_upstream=factory.dns_upstream)
            self.transport = None

        def send_response_to_requester(self, response, requester):
            self.transport.sendto(response, requester)

        def connection_made(self, transport):
            # pylint: disable=line-too-long
            """See `connection_made()`_

            .. _`connection_made()`: https://docs.python.org/3/library/asyncio-protocol.html#asyncio.BaseProtocol.connection_made
            """  # noqa: E501
            self.transport = transport

        def datagram_received(self, data, addr):
            # pylint: disable=line-too-long
            """See `datagram_received()`_

            .. _`datagram_received()`: https://docs.python.org/3/library/asyncio-protocol.html#asyncio.DatagramProtocol.datagram_received
            """  # noqa: E501
            self.dns_query_received(data, addr)

        def error_received(self, exc):
            # pylint: disable=line-too-long
            """See `error_received()`_

            .. _`error_received()`: https://docs.python.org/3/library/asyncio-protocol.html#asyncio.DatagramProtocol.error_received
            """  # noqa: E501
            raise exc  # pragma: no cover

        def connection_lost(self, exc):
            # pylint: disable=line-too-long,unnecessary-pass
            """See `connection_lost()`_

            .. _`connection_lost()`: https://docs.python.org/3/library/asyncio-protocol.html#asyncio.BaseProtocol.connection_lost
            """  # noqa: E501
            pass  # pragma: no cover

        async def close(self):
            if self.transport is not None:
                self.transport.close()
                self.transport = None

    def _create_server_protocol(self, *args, **kwargs):
        return self.DNSOverUDPServer(self, *args, **kwargs)

    async def create_server(self, loop, *args, local_addr=None, **kwargs):
        """Creates an :py:class:`DNSOverUDPServer` object.

        :param loop: the asyncio event loop the server should run in
        :type loop: :py:class:`asyncio.AbstractEventLoop`
        :param local_addr: A tuple for the created server to bind to. The first
                           element is the host part, the second element the
                           port.
        :type local_addr: :py:class:`typing.Tuple[str, int]`

        :returns: An :py:class:`DNSOverUDPServer` object representing an
                  DNS over DTLS server.
        :rtype: :py:class:`DNSOverUDPServer`
        """
        if local_addr is None:
            local_addr = ("localhost", self.DNS_PORT)
        if local_addr[1] is None:
            local_addr = (local_addr[0], self.DNS_PORT)

        transport, protocol = await loop.create_datagram_endpoint(
            self._create_server_protocol,
            *args,
            local_addr=local_addr,
            **kwargs,
        )
        if Config().get("do_not_auto_flow_label", False):
            if not sys.platform.startswith("linux"):
                raise RuntimeError(
                    f"{sys.platform} not supported for do_not_auto_flow_label"
                )
            sock = transport.get_extra_info("socket")
            if sock is not None:
                disable = struct.pack("i", 0)
                sock.setsockopt(socket.IPPROTO_IPV6, 70, disable)

        return protocol
