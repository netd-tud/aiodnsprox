================================================
aiodnsprox—A DNS proxy based on Python's asyncio
================================================

.. image:: https://github.com/anr-bmbf-pivot/aiodnsprox/actions/workflows/test.yml/badge.svg?event=schedule
   :alt: Test aiodnsprox
   :target: https://github.com/anr-bmbf-pivot/aiodnsprox/actions/workflows/test.yml

aiodnsprox is a DNS proxy based on Python's `asyncio`_. It supports a variety
of different DNS transports on both the serving side and the proxied side. On
the proxied side, classic DNS protocols are supported, such as

- DNS over UDP (`RFC 1035, section 4.2.1 <https://datatracker.ietf.org/doc/html/rfc1035#section-4.2.1>`_) and
- DNS over TCP (`RFC 1035, section 4.2.2 <https://datatracker.ietf.org/doc/html/rfc1035#section-4.2.2>`_).

On the serving side, DNS over UDP is supported as well but in addition the
following are supported:

- DNS over DTLS (`RFC 8094`_)
- DNS over CoAP (DoC, `draft-ietf-core-dns-over-coap`_), supporting both
  unencrypted transfer and CoAP over DTLS.

Since aiodnsprox currently is using an experimental feature branch of `aiocoap`_
that provides CoAP over DTLS server support, aiodnsprox is to be considered in
an early **beta state**.

Installation
============

Releases can be installed from PyPI

.. code:: bash

  pip install aiodnsprox

You can install the latest development version directly from GitHub

.. code:: bash

  pip install git+https://github.com/anr-bmbf-pivot/aiodnsprox/

Dependencies
------------
aiodnsprox works on `Python`_ 3.7 or newer.

The following packages are required (see `requirements.txt`_):
To parse configuration files `PyYAML`_ 5.4 or newer is used.
For proxying upstream DNS services and message parsing, `dnspython`_ 2.1 or
newer is used.
For serving DTLS messages, the `tinydtls`_-based `DTLSSocket`_ 0.1 or newer is
used.
For serving CoAP, an `experimental branch <https://gitlab.com/aiocoap/aiocoap/-/tree/dtls-server>`_
of `aiocoap`_ with ``linkheader``, ``tinydtls``, and ``oscore`` support is used.
The branch is based on `aiocoap`_ 0.4.1.

Usage
=====

To start e.g. a DNS over UDP proxy towards a public DNS over UDP server of
`OpenNIC`_, use

.. code:: bash

  aiodns-proxy -u -U 185.120.22.15

For more information on the provided arguments, see

.. code:: bash

  aiodns-proxy -h

Development
===========

Code contributions to aiodnsprox can be made in our `Github repository`_.
Development there follows the `PEP8`_ recommendations and general best practices
as best as possible.

Bugs and feature requests can be made in the `issue tracker`_ over at Github.

Our `documentation`_ is built with `sphinx`_.

For testing we try to achieve as much coverage as possible with our tests found
in the `tests`_ directory and utilize `pytest`_. The easiest way to run the
whole test suite is via the `tox`_ tool. Just run

.. code:: bash

  tox

.. _`asyncio`: https://docs.python.org/3/library/asyncio.html
.. _`RFC 8094`: https://datatracker.ietf.org/doc/html/rfc8094
.. _`draft-ietf-core-dns-over-coap`: https://datatracker.ietf.org/doc/html/draft-ietf-core-dns-over-coap
.. _`Python`: https://docs.python.org
.. _`requirements.txt`: https://github.com/anr-bmbf-pivot/aiodnsprox/blob/main/requirements.txt
.. _`PyYAML`: https://pyyaml.org
.. _`dnspython`: https://www.dnspython.org
.. _`tinydtls`: https://projects.eclipse.org/projects/iot.tinydtls
.. _`DTLSSocket`: https://git.fslab.de/jkonra2m/tinydtls-cython
.. _`aiocoap`: https://aiocoap.readthedocs.io
.. _`OpenNIC`: https://www.opennic.org
.. _`Github repository`: https://github.com/anr-bmbf-pivot/aiodnsprox
.. _`PEP8`: https://www.python.org/dev/peps/pep-0008/
.. _`issue tracker`: https://github.com/anr-bmbf-pivot/aiodnsprox/issues
.. _`documentation`: https://anr-bmbf-pivot.github.io/aiodnsprox
.. _`sphinx`: https://www.sphinx-doc.org
.. _`tests`: https://github.com/anr-bmbf-pivot/aiodnsprox/tree/main/tests
.. _`pytest`: https://pytest.org
.. _`tox`: https://tox.readthedocs.io
