# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import asyncio

import aiocoap
import base64
import dns.message
import pytest

from aiodnsprox import coap
from aiodnsprox import dns_upstream

from .fixtures import dns_server, config


async def _client(proxy_bind, config):
    client = await aiocoap.Context.create_client_context()
    client.client_credentials.load_from_dict(
        {
            f"coaps://[{proxy_bind[0]}]/*": {
                "dtls": {
                    "client-identity": {
                        "ascii": config["dtls_credentials"]["client_identity"],
                    },
                    "psk": {
                        "ascii": config["dtls_credentials"]["psk"],
                    },
                },
            },
        }
    )
    return client


async def _send_query(
    client,
    uri,
    method,
    query,
    accept=coap.CONTENT_FORMAT_DNS_MESSAGE,
    content_format=coap.CONTENT_FORMAT_DNS_MESSAGE,
):
    request = aiocoap.Message(
        code=method,
        uri=uri,
        accept=accept,
        content_format=content_format,
        payload=query,
    )
    return await client.request(request).response


async def _send_query_safe(
    client,
    uri,
    method,
    query,
    accept=coap.CONTENT_FORMAT_DNS_MESSAGE,
    content_format=coap.CONTENT_FORMAT_DNS_MESSAGE,
    dns_var="dns",
):
    if method == aiocoap.GET:
        query_code = base64.urlsafe_b64encode(query).decode().strip("=")
        uri = f"{uri}?{dns_var}={query_code}"
    return await _send_query(
        client, uri, method, query, accept=accept, content_format=content_format
    )


async def _test_dns_query(client, dns_server, uri, method, query):
    coap_response = await _send_query_safe(client, uri, method, query)
    if method == aiocoap.POST:
        assert coap_response.code == aiocoap.numbers.codes.Code.CHANGED
    else:
        assert coap_response.code == aiocoap.numbers.codes.Code.CONTENT
    dns_response = dns.message.from_wire(coap_response.payload)
    found_answer = False
    for rset in dns_response.answer:
        for rda in rset:
            if isinstance(rda, dns_server["resp_rtype"]):
                found_answer = True
                assert rda.address == dns_server["resp_address"]
    assert found_answer


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [None, "/foobar"])
async def test_coap_proxy(dns_server, config, path):
    proxy_bind = ("::1", None)
    config.add_config(
        {
            "dtls_credentials": {
                "client_identity": "Client_identifier",
                "psk": "secretPSK",
            }
        }
    )
    if path is None:
        path = "/dns-query"
    else:
        config.add_config({"transports": {"coap": {"path": path}}})

    upstream = dns_upstream.DNSUpstream(dns_server["host"], dns_server["port"])
    factory = coap.DNSOverCoAPServerFactory(upstream)
    loop = asyncio.get_running_loop()
    server = await factory.create_server(loop, local_addr=proxy_bind)
    try:
        client = await _client(proxy_bind, config)
        query = dns.message.make_query(
            dns_server["req_hostname"], dns_server["resp_rtype"].__name__
        )
        query = query.to_wire()
        await _test_dns_query(
            client,
            dns_server,
            f"coap://[{proxy_bind[0]}]{path}",
            aiocoap.FETCH,
            query,
        )
        await _test_dns_query(
            client,
            dns_server,
            f"coaps://[{proxy_bind[0]}]{path}",
            aiocoap.FETCH,
            query,
        )
        await _test_dns_query(
            client,
            dns_server,
            f"coap://[{proxy_bind[0]}]{path}",
            aiocoap.GET,
            query,
        )
        await _test_dns_query(
            client,
            dns_server,
            f"coaps://[{proxy_bind[0]}]{path}",
            aiocoap.GET,
            query,
        )
        await _test_dns_query(
            client,
            dns_server,
            f"coap://[{proxy_bind[0]}]{path}",
            aiocoap.POST,
            query,
        )
        await _test_dns_query(
            client,
            dns_server,
            f"coaps://[{proxy_bind[0]}]{path}",
            aiocoap.POST,
            query,
        )
        coap_response = await _send_query_safe(
            client,
            f"coaps://[{proxy_bind[0]}]{path}",
            aiocoap.FETCH,
            query,
            content_format=0,
        )
        assert (
            coap_response.code == aiocoap.numbers.codes.Code.UNSUPPORTED_CONTENT_FORMAT
        )
        coap_response = await _send_query_safe(
            client,
            f"coaps://[{proxy_bind[0]}]{path}",
            aiocoap.FETCH,
            query,
            accept=0,
        )
        assert coap_response.code == aiocoap.numbers.codes.Code.NOT_ACCEPTABLE
        coap_response = await _send_query_safe(
            client,
            f"coaps://[{proxy_bind[0]}]{path}",
            aiocoap.GET,
            query,
            dns_var="foobar",
        )
        assert coap_response.code == aiocoap.numbers.codes.Code.BAD_REQUEST
    finally:
        await server.close()
        await server.close()  # call second time to check idempotency


@pytest.mark.asyncio
async def test_coap_factory_create_server_wo_config(dns_server):
    proxy_bind = ("::1", 2304)
    upstream = dns_upstream.DNSUpstream(dns_server["host"], dns_server["port"])
    factory = coap.DNSOverCoAPServerFactory(upstream)
    loop = asyncio.get_running_loop()
    with pytest.raises(RuntimeError):
        await factory.create_server(loop, local_addr=proxy_bind)


@pytest.mark.asyncio
@pytest.mark.parametrize("local_addr", [None, ("localhost", None)])
async def test_coap_factory_create_server(local_addr, mocker, config):
    config.add_config(
        {
            "dtls_credentials": {
                "client_identity": "Client_identifier",
                "psk": "secretPSK",
            }
        }
    )
    loop = mocker.MagicMock()
    mocker.patch("aiodnsprox.coap.DNSOverCoAPServerFactory.ClosableContext")
    fut = asyncio.Future()
    fut.set_result(mocker.MagicMock())
    coap.DNSOverCoAPServerFactory.ClosableContext.create_server_context.return_value = (
        fut
    )
    upstream = dns_upstream.DNSUpstream("localhost", 53)
    factory = coap.DNSOverCoAPServerFactory(upstream)
    server = await factory.create_server(loop, local_addr=local_addr)
    coap.DNSOverCoAPServerFactory.ClosableContext.create_server_context.assert_called_once()
    del server
