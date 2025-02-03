#!/usr/bin/env bash

# Usage: sign.sh 'My App Image.app'
# with environment variables:
# cert_base64: base64-encoded signing certificate
# cert_name: full name of signing certificate
# cert_pass: signing certificate password
# note_user: notarization username
# note_pass: password for note_user
# note_team: Team ID for note_user
# apps:      newline-separated relative pathnames of embedded applications
# files:     newline-separated relative pathnames of embedded executables/dylibs

mydir="$(dirname "$0")"
app_path="$1"

# shellcheck disable=SC1091
. "$mydir/retry_loop"

gotall=true
for var in app_path cert_base64 cert_name cert_pass note_user note_pass note_team apps files
do
    if [[ -z "${!var}" ]]
    then
        echo "Missing required parameter $var" >&2
        gotall=false
    fi
done
$gotall || exit 1

set -x -e
# ****************************************************************************
#   setup keychain
# ****************************************************************************
# The following is derived from
# https://federicoterzi.com/blog/automatic-code-signing-and-notarization-for-macos-apps-using-github-actions/
# shellcheck disable=SC2154
base64 --decode > certificate.p12 <<< "$cert_base64"

# We need to create a new keychain, otherwise using the certificate will prompt
# with a UI dialog asking for the certificate password, which we can't
# use in a headless CI environment
# Create a local keychain password
set +x
keychain_pass="$(dd bs=8 count=1 if=/dev/urandom 2>/dev/null | base64)"
echo "::add-mask::$keychain_pass"
set -x
sleep 1
security create-keychain -p "$keychain_pass" viewer.keychain
security default-keychain -s viewer.keychain
security unlock-keychain -p "$keychain_pass" viewer.keychain
# shellcheck disable=SC2154
security import certificate.p12 -k viewer.keychain -P "$cert_pass" \
         -T /usr/bin/codesign
security set-key-partition-list -S 'apple-tool:,apple:,codesign:' -s \
         -k "$keychain_pass" viewer.keychain
rm certificate.p12

# ****************************************************************************
#   sign executables
# ****************************************************************************
# arrange to retry signing, since empirically this is a
# low-reliability operation
retries=3
signwait=15
function signloop() {
    # save +x / -x state and suppress
    xtrace="$(set +o | grep xtrace)"
    set +x
    # shellcheck disable=SC2064
    trap "$xtrace" RETURN

    local exe
    # we pass the executable to sign as the last argument
    # shellcheck disable=SC1083
    eval exe=\${$#}
    exe="$(basename "$exe")"
    retry_loop "$exe signing" $retries $signwait /usr/bin/codesign "$@"
}

# Handle lines with pathnames containing spaces on a dumb bash 3 GH runner.
function splitlines {
    local IFS=$'\n'
    lines=($1)
}

# plain signing
# Read files into an array first, in case any pathnames contain spaces.
splitlines "$files"
files=("${lines[@]}")
for signwild in "${files[@]}"
do
    # We specifically need to allow both embedded spaces (that should NOT be
    # significant to bash) and wildcards (that SHOULD be expanded by bash).
    # That leads to input lines of the form:
    # "Contents/Frameworks/Chromium Embedded Framework.framework/Libraries"/*.dylib
    # The splitlines command above has hopefully preserved our double-quotes;
    # now expand wildcards too. First wrap $app_path in an extra layer of quotes.
    splitlines "$(eval ls "${app_path@Q}/$signwild")"
    for signee in "${lines[@]}"
    do
        # shellcheck disable=SC2154
        signloop --force --timestamp --keychain viewer.keychain \
                 --sign "$cert_name" "$signee"
    done
done
# deep signing
splitlines "$apps"
# don't forget the outer umbrella application
lines+=(.)
for signee in "${lines[@]}"
do
    signloop --verbose --deep --force \
             --entitlements "$mydir/installer/slplugin.entitlements" \
             --options runtime --keychain viewer.keychain \
             --sign "$cert_name" "$app_path/$signee"
done

spctl -a -texec -vvvv "$app_path"

# ****************************************************************************
#   notarize the app
# ****************************************************************************
# We can't notarize an app bundle directly, but we need to compress it as an
# archive. Therefore, we create a zip file containing our app bundle, so that
# we can send it to the notarization service. Kind of funny to do this when
# actions/download-archive just downloaded and unpacked the artifact .zip
# file, but oh well.
echo "Creating temp notarization archive"
app_base="$(basename "$app_path")"
# Don't put the zipfile in the same sparseimage we're trying to sign and
# notarize! That would require creating the sparseimage with extra room just
# for the .zip, and there's no point.
zip_file="$RUNNER_TEMP/${app_base/.app/.zip}"
ditto -c -k --keepParent "$app_path" "$zip_file"
if [[ ! -f "$zip_file" ]]
then
    echo "Notarization error: ditto failed"
    exit 1
fi
# shellcheck disable=SC2154,SC2064
trap "rm '$zip_file'" EXIT

credentials=(--apple-id "$note_user" --password "$note_pass" --team-id "$note_team")

# Here we send the notarization request to Apple's Notarization service,
# waiting for the result. This typically takes a few seconds inside a CI
# environment, but it might take more depending on the App characteristics.
# Visit the Notarization docs for more information and strategies on how to
# optimize it if you're curious.
echo "Notarize app"
# emit notarytool output to stderr in real time but also capture in variable
set +e
output="$(xcrun notarytool submit "$zip_file" --wait \
          "${credentials[@]}" 2>&1 | \
          tee /dev/stderr ; \
          exit "${PIPESTATUS[0]}")"
# Without the final 'exit' above, we'd be checking the rc from 'tee' rather
# than 'notarytool'.
rc=$?
set +x
[[ "$output" =~ 'id: '([^[:space:]]+) ]]
match=$?
set -x
# Run notarytool log if we find an id: anywhere in the output, regardless of
# rc: notarytool can terminate with rc 0 even if it fails.
if [[ $match -eq 0 ]]
then
    xcrun notarytool log "${BASH_REMATCH[1]}" "${credentials[@]}"
fi
[[ $rc -ne 0 ]] && exit $rc
set -e

# Finally, we need to "attach the staple" to our executable, which will allow
# our app to be validated by macOS even when an internet connection is not
# available.
echo "Attach staple"
xcrun stapler staple "$app_path"
