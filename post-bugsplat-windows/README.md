## post-bugsplat-windows

This action retrieves and unpacks the Windows-app and Windows-symbols
artifacts from the preceding viewer build. It unpacks the viewer's `.pdb` file
from the symbols artifact, then engages BugSplat-Git/symbol-upload to post the
`.exe` and the `.pdb` to BugSplat.
