## sign-pkg-mac

Retrieve and unpack the macOS-app artifact from the preceding viewer build. Since the artifact contains a tarball (as described in https://github.com/actions/upload-artifact/tree/main#maintaining-file-permissions-and-case-sensitive-files), extract the application bundle. Create a sparseimage and copy the app bundle into it, along with control files to customize the Finder display of the `.dmg` downloaded to a user's computer. Sign executables and notarize the app bundle, then convert to `.dmg` and post as a new artifact.

| Input | Description |
| ----- | ----------- |
| imagename | Intended basename of installer .dmg |
| channel | Viewer channel |
| cert_base64 | base64-encoded signing certificate |
| cert_name | full name of signing certificate |
| cert_pass | signing certificate password |
| note_user | notarization Apple ID |
| note_pass | app-specific password for note_user |
| note_team | Team ID for note_user |
