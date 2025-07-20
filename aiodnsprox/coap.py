# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021-23 Freie Universität Berlin
# Copyright (C) 2023-25 TU Dresden
#
# Distributed under terms of the MIT license.

"""DNS over CoAP serving side of the proxy."""

import os
import asyncio
import base64

import aiocoap                              # type: ignore
import aiocoap.resource                     # type: ignore
import aiocoap.transports.tinydtls_server   # type: ignore
from aiocoap.numbers import NOT_ACCEPTABLE  # type: ignore

from .config import Config
from .dns_server import BaseServerFactory, BaseDNSServer
from .dns_upstream import DNSUpstreamServerMixin


CONTENT_FORMAT_DNS_MESSAGE = 553


class NotAcceptable(aiocoap.error.ConstructionRenderableError):
    """Exception to represent a 4.06 Not Acceptable CoAP error response"""

    code = NOT_ACCEPTABLE


class DNSOverCoAPServerFactory(BaseServerFactory):
    """Factory to create DNS over CoAP servers"""

    # pylint: disable=too-few-public-methods

    class _InnerDNSUpstream(DNSUpstreamServerMixin):
        def __init__(self, dns_upstream):
            super().__init__(dns_upstream=dns_upstream)
            self.dns_upstream = dns_upstream
            self._pending_responses = {}

        def send_response_to_requester(self, response, requester):
            assert requester in self._pending_responses
            self._pending_responses[requester].set_result(response)

        # pylint: disable=missing-function-docstring
        async def dns_response(self, query):
            self._pending_responses[query] = asyncio.Future()
            self.dns_query_received(query, query)
            return await self._pending_responses[query]

    class DNSQueryResource(aiocoap.resource.Resource):
        """The DNS over CoAP resource of the DNS over CoAP server.

        :param factory: The factory that created the DNS over CoAP server.
        :type factory: :py:class:`DNSOverCoAPServerFactory`
        """

        def __init__(self, factory):
            super().__init__()
            self._dns_upstream = factory._InnerDNSUpstream(factory.dns_upstream)

        @staticmethod
        def _coap_response(dns_response):
            return aiocoap.Message(
                content_format=CONTENT_FORMAT_DNS_MESSAGE,  # noqa: E501
                payload=dns_response,
            )

        async def _render_acceptable(self, request, query):
            formatted_response = await self._dns_upstream.dns_response(query)
            if (
                request.opt.accept is None
                or request.opt.accept == CONTENT_FORMAT_DNS_MESSAGE
            ):
                dns_response = formatted_response
            else:
                raise NotAcceptable()
            return self._coap_response(dns_response)

        async def _render_with_payload(self, request):
            if request.opt.content_format == CONTENT_FORMAT_DNS_MESSAGE:
                query = request.payload
            else:
                raise aiocoap.error.UnsupportedContentFormat()
            return await self._render_acceptable(request, query)

        async def render_fetch(self, request):
            """:py:class:`aiocoap.resource.Resource` method to serve a FETCH
            request

            :param request: The FETCH request
            :returns: The response for the FETCH request.
            """
            return await self._render_with_payload(request)

        async def render_get(self, request):
            """:py:class:`aiocoap.resource.Resource` method to serve a GET
            request

            :param request: The GET request
            :returns: The response for the GET request.
            """
            queries = dict(q.split("=") for q in request.opt.uri_query)
            if "dns" in queries:
                query_code = queries["dns"]
                # python's base64 only understands encoding with padding, so
                # add '=' padding if needed
                query = base64.urlsafe_b64decode(
                    query_code + "=" * (4 - len(query_code) % 4)
                )
                return await self._render_acceptable(request, query)
            raise aiocoap.error.BadRequest()

        async def render_post(self, request):
            """:py:class:`aiocoap.resource.Resource` method to serve a POST
            request

            :param request: The POST request
            :returns: The response for the POST request.
            """
            return await self._render_with_payload(request)

    class ClosableContext(aiocoap.Context, BaseDNSServer):
        """:py:class:`aiocoap.Context` that also serves as an extension of
        :py:class:`.dns_server.BaseDNSServer` so it can be returned by
        :py:meth:`DNSOverCoAPServerFactory.create_server`"""

        async def close(self):
            ri_type = type(self.request_interfaces)
            if self.request_interfaces:
                try:
                    await self.shutdown()
                except AttributeError:  # pragma: no cover
                    # apparently one should not call shutdown twice ;-)
                    pass
                self.request_interfaces = ri_type()

    async def create_server(self, loop, *args, local_addr=None, **kwargs):
        """Creates an ``aiocoap`` server context.

        :param loop: the asyncio event loop the server should run in
        :type loop: :py:class:`asyncio.AbstractEventLoop`
        :param local_addr: A tuple for the created server to bind to. The first
                           element is the host part, the second element the
                           port.
        :type local_addr: :py:class:`typing.Tuple[str, int]`

        :returns: An :py:class:`ClosableContext` object representing an
                  ``aiocoap`` server context.
        :rtype: :py:class:`ClosableContext`
        """
        config = Config()
        if local_addr is None:
            local_addr = ("localhost", None)
        site = aiocoap.resource.Site()
        site.add_resource(
            [".well-known", "core"],
            aiocoap.resource.WKCResource(site.get_resources_as_linkheader),
        )
        path = (
            config.get("transports", {})
            .get("coap", {})
            .get("path", "dns")
            .strip("/")
            .split("/")
        )
        site.add_resource(path, self.DNSQueryResource(self))

        try:
            client_identity = config["dtls_credentials"]["client_identity"]
            psk = config["dtls_credentials"]["psk"]
        except KeyError as exc:
            raise RuntimeError(f"DTLS credential option {exc} not found") from exc

        os.environ["AIOCOAP_DTLSSERVER_ENABLED"] = "1"

        # pylint: disable=protected-access
        aiocoap.transports.tinydtls_server._SEND_SLEEP_WORKAROUND = config.get(
            "dtls", {}
        ).get("server_hello_done_delay", 0.0)
        ctx = await self.ClosableContext.create_server_context(site, local_addr)
        ctx.server_credentials.load_from_dict(
            {
                ":client": {
                    "dtls": {
                        "client-identity": {"ascii": client_identity},
                        "psk": {"ascii": psk},
                    }
                }
            }
        )
        return ctx
