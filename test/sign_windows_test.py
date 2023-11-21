import io
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import MagicMock, patch

from viewerutil.sign_windows import SignError, cli, sign

EXPIRES_FORMAT = '%b %d %H:%M:%S %Y'


class SignWindowsTest(TestCase):
    @patch('viewerutil.sign_windows.subprocess.run')
    def test_fail(self, run):
        run_return = MagicMock()
        run_return.returncode = 1
        run.return_value = run_return
        with self.assertRaises(SignError) as ctx:
            sign('executable-1',
                 vault_uri='vault_uri',
                 cert_name='cert_name',
                 client_id='client_id',
                 client_secret='client_secret',
                 tenant_id='tenant_id',
                 )
        self.assertTrue('executable-1 signing failed' in str(ctx.exception))

    @patch('viewerutil.sign_windows.subprocess.run')
    def test_no_expiration(self, run):
        run_return = MagicMock()
        run_return.returncode = 0
        run_return.stdout = ''
        run.return_value = run_return
        f = io.StringIO()
        with redirect_stdout(f):
            sign('executable-1',
                 vault_uri='vault_uri',
                 cert_name='cert_name',
                 client_id='client_id',
                 client_secret='client_secret',
                 tenant_id='tenant_id',
                 )
        self.assertTrue('::warning::Failed to find certificate expiration date' in f.getvalue())

    @patch('viewerutil.sign_windows.subprocess.run')
    def test_sign(self, run):
        run_return = MagicMock()
        run_return.returncode = 0
        future = (datetime.now() + timedelta(days=365)).strftime(EXPIRES_FORMAT)
        # Provide certificate expiration date
        run_return.stdout = f'Expires: {future}'
        run.return_value = run_return
        rc = sign('executable-1',
                  vault_uri='vault_uri',
                  cert_name='cert_name',
                  client_id='client_id',
                  client_secret='client_secret',
                  tenant_id='tenant_id',
                  )
        self.assertEqual(rc, 0)


def mock_glob(input):
    if "*" in input:
        return [input.replace("*", str(i)) for i in range(1, 3)]
    return [input]


class CLITest(TestCase):
    @patch('viewerutil.sign_windows.glob.glob', side_effect=mock_glob)
    @patch('viewerutil.sign_windows.sign')
    def test_multiple_files(self, sign, glob):

        cli(["""file1,file2
             file3
             foo*
             """,
             '-v', 'vault_uri',
             '-c', 'cert_name',
             '-i', 'client_id',
             '-s', 'client_secret',
             '-t', 'tenant_id',
             ])

        kwargs = {"vault_uri": "vault_uri",
                  "cert_name": "cert_name",
                  "client_id": "client_id",
                  "client_secret": "client_secret",
                  "tenant_id": "tenant_id",
                  "certwarning": 14,
                  }

        sign.assert_any_call("file1", **kwargs)
        sign.assert_any_call("file2", **kwargs)
        sign.assert_any_call("file3", **kwargs)
        sign.assert_any_call("foo1", **kwargs)
        sign.assert_any_call("foo2", **kwargs)
