#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

"""Base definitions for the serving side of the DNS proxy"""

import abc
import asyncio
import typing

from .dns_upstream import DNSTransport


class BaseDNSServer(abc.ABC):
    """An abstract DNS server."""
    # pylint: disable=too-few-public-methods
    @abc.abstractmethod
    async def close(self) -> typing.NoReturn:
        """Closes the server.
        """
        raise NotImplementedError


class BaseServerFactory(abc.ABC):
    """Abstract :py:class:`BaseDNSServer` factory.

    :param upstream_host: Host of the proxied DNS server for
                          :py:class:`.dns_upstream.DNSUpstreamServerMixin`.
    :type upstream_host: str
    :param upstream_port: Port of the proxied DNS server for
                          :py:class:`.dns_upstream.DNSUpstreamServerMixin`.
    :type upstream_port: int
    :param upstream_transport: Transport used to communicate with proxied DNS server
                               for :py:class:`.dns_upstream.DNSUpstreamServerMixin`.
    :type upstream_transport: :py:class:`.dns_upstream.DNSTransport`
    :param upstream_timeout: Timeout for queries towards the proxied DNS server
                             for :py:class:`.dns_upstream.DNSUpstreamServerMixin`.
    :type upstream_timeout: float
    """     # noqa: E501
    # pylint: disable=too-few-public-methods
    def __init__(self, upstream_host: str,
                 upstream_port: typing.Optional[int] = None,
                 upstream_transport: typing.Optional[DNSTransport] =
                 DNSTransport.UDP,
                 upstream_timeout: typing.Optional[float] = None):
        self.upstream_host = upstream_host
        self.upstream_port = upstream_port
        self.upstream_transport = upstream_transport
        self.upstream_timeout = upstream_timeout

    @abc.abstractmethod
    async def create_server(
        self, loop: asyncio.AbstractEventLoop, *args,
        local_addr: typing.Tuple[str, int] = None, **kwargs
    ) -> BaseDNSServer:
        """Creates a :py:class:`BaseDNSServer` object.

        :param loop: the asyncio event loop the server should run in
        :type loop: :py:class:`asyncio.AbstractEventLoop`
        :param local_addr: A tuple for the created server to bind to. The first
                           element is the host part, the second element the
                           port. If ``local_addr`` is ``None`` or any of its
                           elements are ``local_addr`` are ``None``, a sensible
                           default is selected by the implementation.
        :type local_addr: :py:class:`typing.Tuple[str, int]`

        :returns: An object based on the :py:class:`BaseDNSServer` class.
        :rtype: :py:class:`BaseDNSServer`
        """
        raise NotImplementedError
