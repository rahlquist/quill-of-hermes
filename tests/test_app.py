import asyncio
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PATCHED_CLI = str(Path(__file__).resolve().parents[1] / 'llama-mtmd-cli-patched')
os.environ.setdefault('OVISOCR_CLI', PATCHED_CLI)

import app


class OvisOCRTests(unittest.TestCase):
    def test_ovisocr2_uses_cpu_only_cli_options(self):
        expected = [
            '--device', 'none',
            '--mmproj-device', 'none',
            '-ngl', '0',
            '-t', '4',
        ]
        self.assertEqual(app.MODELS['ovisocr2'].get('cli_args'), expected)

    def test_run_one_passes_cpu_only_flags_to_the_ovis_cli(self):
        model = app.MODELS['ovisocr2']
        def fake_run(command, **kwargs):
            return SimpleNamespace(returncode=0, stdout='OCR text', stderr='')
        with patch('app.subprocess.run', side_effect=fake_run) as runner:
            asyncio.run(app.run_one('image.png', 'model.gguf', 'mmproj.gguf', model['cli'], model['cli_args']))
        command = runner.call_args.args[0]
        self.assertEqual(command[0], PATCHED_CLI)
        self.assertIn('--device', command)
        self.assertIn('none', command)
        self.assertIn('--mmproj-device', command)
        self.assertIn('-ngl', command)
        self.assertIn('0', command)
        self.assertIn('-t', command)
        self.assertIn('4', command)

    def test_page_only_advertises_ocr_models_and_disables_cache(self):
        response = app.index()
        html = (Path(app.STATIC) / 'index.html').read_text()
        self.assertIn('OvisOCR2-F16', html)
        self.assertIn('TeleOCR (NaviDC-OCR)', html)
        self.assertNotIn('Holo', html)
        self.assertIn('no-store', response.headers.get('cache-control', '').lower())


if __name__ == '__main__':
    unittest.main()
