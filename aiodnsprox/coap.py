# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import asyncio
import base64

import aiocoap
import aiocoap.resource
import aiocoap.transports.tinydtls_server

from .config import Config
from .dns_server import DNSServer
from .dns_upstream import DNSUpstreamServerMixin
from .server_factory import BaseServerFactory


CONTENT_FORMAT_DNS_MESSAGE = 65053


class NotAcceptable(aiocoap.error.ConstructionRenderableError):
    code = aiocoap.numbers.codes.Code.NOT_ACCEPTABLE


class DNSOverCoAPServerFactory(BaseServerFactory):
    # pylint: disable=too-few-public-methods
    class DNSQueryResource(aiocoap.resource.Resource, DNSUpstreamServerMixin):
        def __init__(self, factory):
            super().__init__(host=factory.upstream_host,
                             port=factory.upstream_port,
                             transport=factory.upstream_transport,
                             timeout=factory.upstream_timeout)
            self._pending_responses = {}

        async def _dns_response(self, query):
            self._pending_responses[query] = asyncio.Future()
            self.dns_query_received(query, query)
            return await self._pending_responses[query]

        def send_response_to_requester(self, response, query):
            # pylint: disable=arguments-renamed
            assert query in self._pending_responses
            self._pending_responses[query].set_result(response)

        @staticmethod
        def _coap_response(dns_response):
            return aiocoap.Message(
                content_format=CONTENT_FORMAT_DNS_MESSAGE,  # noqa: E501
                payload=dns_response
            )

        async def _render_acceptable(self, request, query):
            formatted_response = await self._dns_response(query)
            if request.opt.accept is None or \
               request.opt.accept == CONTENT_FORMAT_DNS_MESSAGE:
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
            return await self._render_with_payload(request)

        async def render_get(self, request):
            queries = dict(q.split("=") for q in request.opt.uri_query)
            if 'dns' in queries:
                query_code = queries['dns']
                # python's base64 only understands encoding with padding, so
                # add '=' padding if needed
                query = base64.urlsafe_b64decode(
                    query_code + '=' * (4 - len(query_code) % 4)
                )
                return await self._render_acceptable(request, query)
            raise aiocoap.error.BadRequest()

        async def render_post(self, request):
            return await self._render_with_payload(request)

    class ClosableContext(aiocoap.Context, DNSServer):
        async def close(self):
            ri_type = type(self.request_interfaces)
            if self.request_interfaces:
                try:
                    await self.shutdown()
                except AttributeError:  # pragma: no cover
                    # apparently one should not call shutdown twice ;-)
                    pass
                self.request_interfaces = ri_type()

    class CredentialStore:
        # hacking our own SecretStore, so that config is observed
        def __init__(self):
            try:
                credentials = Config()['dtls_credentials']
                client_identity = credentials['client_identity'].encode()
                self._dict = {client_identity: credentials['psk'].encode()}
            except KeyError as exc:
                raise RuntimeError(f"DTLS credential option {exc} not found") \
                    from exc

        def __contains__(self, key):
            return key in self._dict    # pragma: no cover

        def __getitem__(self, key):
            return self._dict[key]

        def keys(self):
            return self._dict.keys()

    async def create_server(self, loop, *args, local_addr=None, **kwargs):
        if local_addr is None:
            local_addr = ('localhost', None)
        site = aiocoap.resource.Site()
        site.add_resource(
            ['.well-known', 'core'],
            aiocoap.resource.WKCResource(site.get_resources_as_linkheader)
        )
        site.add_resource(['dns-query'], self.DNSQueryResource(self))

        aiocoap.transports.tinydtls_server.securitystore = \
            self.CredentialStore()
        return await self.ClosableContext.create_server_context(site,
                                                                local_addr)
