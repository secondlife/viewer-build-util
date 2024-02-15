#!/usr/bin/env python3
"""\
@file   which_branch.py
@author Nat Goodspeed
@date   2023-11-14
@brief  Discover which git branch(es) correspond to a given commit hash.

$LicenseInfo:firstyear=2023&license=viewerlgpl$
Copyright (c) 2023, Linden Research, Inc.
$/LicenseInfo$
"""

import contextlib
import os
import re
import subprocess
import sys

import github


class Error(Exception):
    pass


def branches_for(repo, commit):
    """
    Use the GitHub REST API to discover which branch(es) correspond to the
    passed commit hash. The commit string can actually be any of the ways git
    permits to identify a commit:

    https://git-scm.com/docs/gitrevisions#_specifying_revisions

    branches_for() generates a (possibly empty) sequence of all the branches
    of the specified repo for which the specified commit is the tip.
    """
    for branch in repo.get_branches():
        try:
            delta = repo.compare(base=commit, head=branch.name)
        except github.GithubException:
            continue

        if delta.ahead_by == 0 and delta.behind_by == 0:
            yield branch


def main(*raw_args):
    from argparse import ArgumentParser
    parser = ArgumentParser(description=  # noqa: E251
"%(prog)s reports the branch(es) for which the specified commit hash is the tip.",  # noqa: E128
                            epilog="""\
When GitHub Actions launches a tag build, it checks out the specific changeset
identified by the tag, and so 'git branch' reports detached HEAD. But we use
tag builds to build a GitHub 'release' of the tip of a particular branch, and
it's useful to be able to identify which branch that is.
""")
    parser.add_argument('-t', '--token', required=True,
                        help="""GitHub REST API access token""")
    parser.add_argument('-r', '--repo',
                        help="""GitHub repository name, in the form OWNER/REPOSITORY""")
    parser.add_argument('commit',
                        help="""commit hash at the tip of the sought branch""")
    args = parser.parse_args(raw_args)
    
    # If repo is omitted or None, assume the current directory is a local clone
    # whose 'origin' remote is the GitHub repository of interest.
    if not args.repo:
        url = subprocess.check_output(['git', 'remote', 'get-url', 'origin'],
                                      text=True)
        parts = re.split(r'[:/]', url.rstrip())
        args.repo = '/'.join(parts[-2:]).removesuffix('.git')

    gh = github.MainClass.Github(args.token)
    repo = gh.get_repo(args.repo)

    try:
        branch = next(iter(branches_for(repo=repo, commit=args.commit))).name
    except StopIteration:
        return

    # If we weren't run as a GitHub action (no $GITHUB_OUTPUT), just show user
    # output variables.
    GITHUB_OUTPUT = os.getenv("GITHUB_OUTPUT")
    if GITHUB_OUTPUT:
        outf = open(GITHUB_OUTPUT, "a")
    else:
        outf = sys.stdout

    print(f"branch={branch}", file=outf)

    # Can we find a pull request corresponding to this branch?
    # (Is there a better way than just searching PRs?)
    # Empirically, although get_pulls(head=branch) would seem to do exactly
    # what we want, we always end up with a list of all open PRs anyway.
    try:
        pr = next(pr for pr in repo.get_pulls(head=branch) if pr.head.ref == branch)
    except StopIteration:
        return

    # pr.body is the PR's description. Look for a line embedded in that
    # description containing only 'relnotes:'.
    lines = iter(pr.body.splitlines())
    try:
        next(line for line in lines if line.strip() == 'relnotes:')
    except StopIteration:
        return

    # Having found that line, the rest of the body is the release notes
    # header.
    outf.writelines((
        'relnotes<<EOF\n',
        '\n'.join(lines),
        '\n',
        'EOF\n'
    ))

if __name__ == "__main__":
    try:
        sys.exit(main(*sys.argv[1:]))
    except Error as err:
        sys.exit(str(err))
