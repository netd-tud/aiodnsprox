# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import random
import subprocess

from dns.rdtypes.IN.AAAA import AAAA
import pytest

from aiodnsprox.config import Config

TEST_HOSTNAME = "example.org"
TEST_ADDRESS = "2001:db8::1"


@pytest.fixture
def config():
    conf = Config()
    conf._sections.clear()  # pylint: disable=protected-access
    yield conf
    conf._sections.clear()  # pylint: disable=protected-access


@pytest.fixture
def dns_server(tmp_path):
    config = tmp_path / "dnsmasq.conf"
    config.write_text("")
    port = random.randint(1 << 2, 0xFF) << 8 | 53
    proc = subprocess.Popen(
        [
            "dnsmasq",
            "-C",
            str(config),
            "-k",
            "-p",
            str(port),
            f"--host-record={TEST_HOSTNAME},{TEST_ADDRESS}",
        ]
    )
    while True:
        try:
            subprocess.check_call(f"ss -ulpn | grep -q {port}", shell=True)
        except subprocess.CalledProcessError:
            continue
        else:
            break
    yield {
        "host": "::1",
        "port": port,
        "req_hostname": TEST_HOSTNAME,
        "resp_rtype": AAAA,
        "resp_address": TEST_ADDRESS,
    }
    proc.kill()
    proc.wait()
