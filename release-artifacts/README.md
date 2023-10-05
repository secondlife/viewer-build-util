## release-artifacts

Given a directory containing artifact subtrees downloaded by (e.g.)
[actions/download-artifact](https://github.com/actions/download-artifact),
organize their contents into a single flat directory suitable for posting as
release assets using (e.g.)
[secondlife-3p/action-gh-release](https://github.com/secondlife-3p/action-gh-release).
Resolve filename conflicts by prepending some or all of the original
subdirectory path.

This way you need not keep manually updating a list of files to post as
release assets as you change the contents of the build artifacts.

| Input | Description |
| ----- | ----------- |
| input-path | Path into which build artifacts have been downloaded and unzipped |
| output-path | Path into which flattened artifact files should be placed |
| exclude | Newline-separated list of artifacts to ignore |
| prefix | Newline-separated list of artifact-name=prefix: to resolve filename collisions, prepend 'prefix' instead of 'artifact-name' |

The script [flatten_files.py](flatten_files.py) performs the rearrangement.
