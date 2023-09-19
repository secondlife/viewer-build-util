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

from autobuild.autobuild_tool_source_environment import (
    load_vsvars, _available_vsvers, SourceEnvError)
from collections.abc import Iterable
from datetime import datetime, timedelta
import os
from pathlib import Path
from pyng.commands import Commands
import re
import shlex
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
    # First, locate signtool.
    # Don't even pretend to support 32-bit any more.
    os.environ['AUTOBUILD_ADDRSIZE'] = '64'
    try:
        vsver = _available_vsvers()[-1]
    except SourceEnvError as err:
        raise Error(str(err)) from err
    except IndexError:
        raise Error("Can't determine latest Visual Studio version, is it installed?")

    try:
        vsvars = load_vsvars(vsver)
    except SourceEnvError as err:
        raise Error(str(err)) from err

    try:
        # load_vsvars() returns an ordinary Python dict, that is,
        # case-sensitive. Empirically the keys are all uppercase. We could go
        # through the exercise of loading this data into a case-insensitive
        # dict, but it's simpler to use an uppercase key.
        VerBinPath = vsvars['WINDOWSSDKVERBINPATH']
    except KeyError:
        from pprint import pprint
        pprint({ key: value for key, value in vsvars.items() if 'Kits' in value },
               sys.stderr)
        raise Error(f"WindowsSdkVerBinPath not set by VS version {vsver}")

    signtool = Path(VerBinPath) / 'X64' / 'signtool.exe'
    assert signtool.is_file()

    name = Path(executable).name

    # If we bang on the timestamp server too hard by signing executables
    # back-to-back, we may get throttled.
    # "Error: SignerSign() failed. (-1073700864/0xc000a000)"
    # may be throttle-related, and it somehow fails the build despite the
    # backoff loop meant to deal with it. (???)
    # At any rate, a small fixed delay may keep us out of throttle trouble.
    done = None
    for retry in range(retries):
        if retry:
            print(f'{name} signing {retry} failed, ', end='', file=sys.stderr)
        print(f'waiting {delay:.1f} seconds', file=sys.stderr)
        time.sleep(delay)
        delay *= backoff
        # round-robin between listed services
        svc = service[retry % len(service)]
        command = [signtool, 'sign',
                   '/f', certificate,
                   '/t', svc,
                   '/d', description,
                   '/fd', 'sha256',
                   '/v',
                   executable]
        print(f'{name} attempt {retry+1}:', shlex.join(command))
        done = subprocess.run(command,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              text=True)
        print(done.stdout, end='')
        if done.returncode == 0:
            break
    else:
        raise Error(f'{name} signing failed after {retries} attempts, giving up')

    # Here the last of the retries succeeded, setting 'done'
    rc = done.returncode
    print('Signing succeeded')
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
                break
    else:
        raise Error('Failed to find certificate expiration date')
    expires = expiration - datetime.now()
    print(f'Certificate expires in {expires.days}')
    if expires < timedelta(certwarning):
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
