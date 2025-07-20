# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

"""Proxy configuration"""

import argparse
import pprint
import typing
import yaml


class _Singleton(type):
    """Singleton meta class.

    see https://stackoverflow.com/q/6760685
    """

    _instances: dict[typing.Type["_Singleton"], "_Singleton"] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(_Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Config(metaclass=_Singleton):
    """Singleton Config mapping class to represent both config file and CLI
    argument congfiguration.
    """

    def __init__(self):
        self._sections = {}

    def __str__(self):
        return pprint.pformat(self._sections)

    def __repr__(self):
        return f"<{type(self).__name__}: {self._sections}>"

    def __len__(self):
        return len(self._sections)

    def __contains__(self, key: str) -> bool:
        return key in self._sections

    def __getitem__(self, key: str) -> typing.Mapping:
        return self._sections[key]

    def get(self, section: str, default=None) -> typing.Mapping:
        """Get configuration section.

        :param key: Name of the configuration section.
        :type key: str
        :param default: (Optional) default if section does not exist.
        """
        return self._sections.get(section, default)

    def add_config(self, config: typing.Mapping):
        """Adds configuration from a mapping

        :param config: A mapping that contains the new configuration sections.
        :type config: :py:class:`typing.Mapping`.
        """
        self._sections.update(config)

    def add_yaml_config(self, yaml_file):
        """Adds configuration from a YAML file

        :param yaml: A file-like object to a YAML file.
        :type yaml: A file-like object.
        """
        self.add_config(yaml.load(yaml_file, yaml.loader.FullLoader))

    def add_args_config(self, args):
        """Adds configuration from CLI arguments

        :param args: parsed CLI arguments.
        :type args: :py:class:`argparse.Namespace`
        """
        self.add_config(
            {
                k: vars(v) if isinstance(v, argparse.Namespace) else v
                for k, v in vars(args).items()
                if v is not None
            }
        )
