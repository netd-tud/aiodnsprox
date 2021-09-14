#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import pytest

from aiodnsprox import config


def test_config__empty():
    conf = config.Config()
    assert 'test' not in conf
    with pytest.raises(KeyError):
        assert conf['test']
    assert conf.get('test') is None
    assert conf.get('test', 'foobar') == 'foobar'


def test_config__add_config():
    conf1 = config.Config()
    conf2 = config.Config()
    assert 'test' not in conf1
    assert 'test' not in conf2
    conf1.add_config({'test': 'foobar'})
    assert 'test' in conf1
    assert 'test' in conf2
    assert conf1['test'] == 'foobar'
    assert conf2['test'] == 'foobar'
    assert conf1.get('test') == 'foobar'
    assert conf2.get('test') == 'foobar'
