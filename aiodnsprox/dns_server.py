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

from .dns_upstream import DNSUpstream


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

    :param dns_upstream: The proxied DNS server for
                         :py:class:`.dns_upstream.DNSUpstreamServerMixin`.
    :type upstream_host: :py:class:`.dns_upstream.DNSUpstream`
    """     # noqa: E501
    # pylint: disable=too-few-public-methods
    def __init__(self, dns_upstream: DNSUpstream):
        self.dns_upstream = dns_upstream

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
