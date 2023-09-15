#!/usr/bin/env python3
"""\
@file   sign.py
@author Nat Goodspeed
@date   2023-09-14
@brief  Sign the designated executable using Windows signtool.

$LicenseInfo:firstyear=2023&license=viewerlgpl$
Copyright (c) 2023, Linden Research, Inc.
$/LicenseInfo$
"""

from collections.abc import Iterable
from datetime import datetime, timedelta
import os
from pathlib import Path
from pyng.commands import Commands
import re
import subprocess
import sys
import time

class Error(Exception):
    pass

ExpiresLine = re.compile(
    r"\bExpires:\s+\S{3}\s+(\S{3}) (\d+) \d\d:\d\d:\d\d (\d{4})"
)  # looking for a date like 'Sep 16 23:59:59 2017'

# Make a function decorator that will generate an ArgumentParser
command = Commands()

# Interactively, don't print our int return value
@command.format(lambda ret: None)
def sign(executable, *, service: Iterable, certificate,
         delay=5, retries=6, backoff=1.5, certwarning=14,
         description='Second Life Setup'):
    """
    Sign the designated executable using Windows signtool.

    Pass:

    executable:  path to executable to sign
    certificate: path to certificate file with authentication
    service:     iterable of URLs to timestamp services
    delay:       initial delay before signing attempt
    retries:     number of times to attempt the signing operation
    backoff:     scale factor by which to multiply delay for each retry
    certwarning: warn if certificate will expire in fewer than this many days
    description: pass to signtool
    """
    VerBinPath = os.getenv('WindowsSdkVerBinPath')
    assert VerBinPath, '$WindowsSdkVerBinPath must be set'
    signtool = Path(VerBinPath) / 'X64' / 'signtool.exe'
    assert signtool.is_file()

    # If we bang on the timestamp server too hard by signing executables
    # back-to-back, we may get throttled.
    # "Error: SignerSign() failed. (-1073700864/0xc000a000)"
    # may be throttle-related, and it somehow fails the build despite the
    # backoff loop meant to deal with it. (???)
    # At any rate, a small fixed delay may keep us out of throttle trouble.
    done = None
    for retry in range(retries):
        if retry:
            print(f'signing {retry} failed, ', end='', file=sys.stderr)
        print(f'waiting {delay} seconds', file=sys.stderr)
        time.sleep(delay)
        delay *= backoff
        # round-robin between listed services
        service = services[retry % len(services)]
        done = subprocess.run(
            [signtool, 'sign',
             '/f', certificate,
             '/t', service,
             '/d', description,
             '/fd', 'sha256',
             '/v',
             executable],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True)
        if done.returncode == 0:
            break
    else:
        print(f'Sign tool failed after {retries} attempts', file=sys.stderr)
        print(done.stdout, file=sys.stderr)
        sys.exit('Giving up...')

    # Here the last of the retries succeeded, setting 'done'
    rc = done.returncode
    print('Signing succeeded')
    # Check the certificate expiration date in the output to warn of imminent expiration
    expiration = None
    for line in done.stdout.splitlines():
        print(line)
        found = ExpiresLine.search(line)
        if found:
            # month is an abbreviated name, translate
            try:
                expiration = datetime.strptime(' '.join(found.groups()), '%b %d %Y')
            except ValueError:
                print('failed to parse expiration from:', line, file=sys.stderr)
                rc = 1
    if not expiration:
        sys.exit('Failed to find certificate expiration date')
    if expiration < datetime.now() + timedelta(certwarning):
        print(f'::warning::Certificate expires soon: {expiration}')
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
