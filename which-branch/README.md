## which-branch

Discover and report which repository branch corresponds to `github.repository`'s `github.sha`.

This is necessary for a release action because release actions are driven by a tag, which means that `github.ref_name` reports the tag rather than the corresponding branch.

| Input | Description |
| ----- | ----------- |
| token | GitHub Personal Access Token with which to query the REST API |

| Output | Description |
| ------ | ----------- |
| branch | name of the branch whose tip is `github.sha`, or empty string |

