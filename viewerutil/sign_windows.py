"""
Sign the designated executable using Microsoft AzureSignTool.
"""

import glob
import re
import shlex
import subprocess
import sys
from argparse import ArgumentParser
from datetime import datetime, timedelta
from pathlib import Path


class SignError(Exception):
    pass


ExpiresLine = re.compile(
    r"\bExpires:\s+\S{3}\s+(\S{3}) (\d+) \d\d:\d\d:\d\d (\d{4})"
)  # looking for a date like 'Sep 16 23:59:59 2017'


def sign(file, *, vault_uri, cert_name, client_id, client_secret, tenant_id,
         certwarning=14):
    """
    Sign the designated files using Microsoft AzureSignTool.

    Pass:

    files:         path to executable to sign
    vault_uri:     Azure key vault URI
    cert_name:     Name of certificate on Azure
    client_id:     Azure signer app clientId
    client_secret: Azure signer app clientSecret
    tenant_id:     Azure signer app tenantId
    certwarning:   warn if certificate will expire in fewer than this many days
    """
    name = Path(file).name

    command = ['AzureSignTool', 'sign',
               '-kvu', vault_uri,
               '-kvi', client_id,
               '-kvt', tenant_id,
               '-kvs', client_secret,
               '-kvc', cert_name,
               '-tr', 'http://timestamp.digicert.com',
               '-v', file]
    print(name, 'signing:', shlex.join(command))
    done = subprocess.run(command,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          text=True)
    print(done.stdout, end='')
    rc = done.returncode
    if rc != 0:
        raise SignError(name + ' signing failed')

    print(name, 'signing succeeded')
    # Check the certificate expiration date in the output to warn of imminent expiration
    for line in done.stdout.splitlines():
        found = ExpiresLine.search(line)
        if found:
            # month is an abbreviated name, translate
            try:
                expiration = datetime.strptime(' '.join(found.groups()), '%b %d %Y')
            except ValueError:
                raise SignError('failed to parse expiration from: ' + line)
            else:
                expires = expiration - datetime.now()
                print(f'Certificate expires in {expires.days} days')
                if expires < timedelta(certwarning):
                    print(f'::warning::Certificate expires in {expires.days} days: {expiration}')
                break
    else:
        # raise Error('Failed to find certificate expiration date')
        print('::warning::Failed to find certificate expiration date')
    return rc


def cli(argv=None):
    parser = ArgumentParser()
    parser.add_argument('files', help='CSV or newline separated list of files to sign')
    parser.add_argument('-v', '--vault-uri', required=True)
    parser.add_argument('-c', '--cert-name', required=True)
    parser.add_argument('-i', '--client-id', required=True)
    parser.add_argument('-s', '--client-secret', required=True)
    parser.add_argument('-t', '--tenant-id', required=True)
    parser.add_argument('-w', '--certwarning', type=int, default=14)
    args = parser.parse_args(argv)
    files = args.files
    kwargs = vars(args)
    kwargs.pop('files')
    for ln in re.split(r',|\n', files):
        ln = ln.strip()
        for f in glob.glob(ln):
            sign(f, **kwargs)


def main():
    try:
        cli()
    except SignError as err:
        sys.exit(str(err))
