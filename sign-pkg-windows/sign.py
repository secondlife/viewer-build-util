#!/usr/bin/env python3
"""\
@file   sign.py
@author Nat Goodspeed
@date   2023-09-14
@brief  Sign the designated executable using Microsoft AzureSignTool.

$LicenseInfo:firstyear=2023&license=viewerlgpl$
Copyright (c) 2023, Linden Research, Inc.
$/LicenseInfo$
"""

import shlex
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from pyng.commands import Commands


class Error(Exception):
    pass


# Make a function decorator that will generate an ArgumentParser
command = Commands()


# Interactively, don't print our int return value
@command.format(lambda ret: None)
def sign(executable, *, vault_uri, cert_name, client_id, client_secret, tenant_id,
         certwarning=14):
    """
    Sign the designated executable using Microsoft AzureSignTool.

    Pass:

    executable:    path to executable to sign
    vault_uri:     Azure key vault URI
    cert_name:     Name of certificate on Azure
    client_id:     Azure signer app clientId
    client_secret: Azure signer app clientSecret
    tenant_id:     Azure signer app tenantId
    certwarning:   warn if certificate will expire in fewer than this many days
    """
    name = Path(executable).name

    command = ['AzureSignTool', 'sign',
               '-kvu', vault_uri,
               '-kvi', client_id,
               '-kvt', tenant_id,
               '-kvs', client_secret,
               '-kvc', cert_name,
               '-tr', 'http://timestamp.digicert.com',
               '-v', executable]
    print(name, 'signing:', shlex.join(command))
    done = subprocess.run(command)
    rc = done.returncode
    if rc != 0:
        raise Error(name + ' signing failed')

    print(name, 'signing succeeded')
    return rc


def main(*raw_args):
    parser = command.get_parser()
    args = parser.parse_args(raw_args)
    args.run()


if __name__ == "__main__":
    try:
        sys.exit(main(*sys.argv[1:]))
    except Error as err:
        sys.exit(str(err))
