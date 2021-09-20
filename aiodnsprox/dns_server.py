#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import abc


class DNSServer(abc.ABC):
    # pylint: disable=too-few-public-methods
    @abc.abstractmethod
    async def close(self):
        raise NotImplementedError
