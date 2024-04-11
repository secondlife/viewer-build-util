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

import argparse
import re
import shlex
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


class Error(Exception):
    pass


ExpiresLine = re.compile(
    r"\bExpires:\s+\S{3}\s+(\S{3}) (\d+) \d\d:\d\d:\d\d (\d{4})"
)  # looking for a date like 'Sep 16 23:59:59 2017'

def sign(executable, vault_uri, cert_name, client_id, client_secret, tenant_id,
         cert_warning=14):
    """
    Sign the designated executable using Microsoft AzureSignTool.
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
                if expires < timedelta(cert_warning):
                    print(f'::warning::Certificate expires in {expires.days} days: {expiration}')
                break
    else:
        # raise Error('Failed to find certificate expiration date')
        print('::warning::Failed to find certificate expiration date')
    return rc


def main(argv=None):
    parser = argparse.ArgumentParser(description='Sign the designated executable using Microsoft AzureSignTool.')
    parser.add_argument('executable', help='path to executable to sign')
    parser.add_argument('-v', '--vault-uri', required=True, help='Azure key vault URI')
    parser.add_argument('-c', '--cert-name', required=True, help='Name of certificate on Azure')
    parser.add_argument('-C', '--client-id', required=True, help='Azure signer app clientId')
    parser.add_argument('--client-secret', required=True, help='Azure signer app clientSecret')
    parser.add_argument('-t', '--tenant-id', required=True, help='Azure signer app tenantId')
    parser.add_argument('--cert-warning', type=int, default=14, help='warn if certificate will expire in fewer than this many days')
    args = parser.parse_args(argv)
    sign(**vars(args))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Error as err:
        sys.exit(str(err))
