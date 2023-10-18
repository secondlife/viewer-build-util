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

import os
import re
import shlex
import subprocess
import sys
import time
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path

from pyng.commands import Commands


class Error(Exception):
    pass


ExpiresLine = re.compile(
    r"\bExpires:\s+\S{3}\s+(\S{3}) (\d+) \d\d:\d\d:\d\d (\d{4})"
)  # looking for a date like 'Sep 16 23:59:59 2017'

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
               '-tr',  'http://timestamp.digicert.com',
               '-v',   executable]
    print(name, 'signing:', shlex.join(command))
    done = subprocess.run(command,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          text=True)
    print(done.stdout, end='')
    rc = done.returncode
    if rc != 0:
        raise Error(name + ' signing failed')

    print(name, 'signing succeeded')
    # Check the certificate expiration date in the output to warn of imminent expiration
    for line in done.stdout.splitlines():
        found = ExpiresLine.search(line)
        if found:
            # month is an abbreviated name, translate
            try:
                expiration = datetime.strptime(' '.join(found.groups()), '%b %d %Y')
            except ValueError:
                raise Error('failed to parse expiration from: ' + line)
            else:
                expires = expiration - datetime.now()
                print(f'Certificate expires in {expires.days} days')
                if expires < timedelta(certwarning):
                    print(f'::warning::Certificate expires in {expires.days} days: {expiration}')
                break
    else:
##        raise Error('Failed to find certificate expiration date')
        print('::warning::Failed to find certificate expiration date')
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
