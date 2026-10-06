import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PATCHED_CLI = str(Path(__file__).resolve().parents[1] / 'llama-mtmd-cli-patched')
os.environ.setdefault('OVISOCR_CLI', PATCHED_CLI)

import app


class OvisOCRTests(unittest.TestCase):
    def test_ovisocr2_uses_cuda_for_model_and_projector(self):
        expected = ['--device', 'CUDA0', '--mmproj-device', 'CUDA0', '-ngl', '99', '-t', '4']
        self.assertEqual(app.MODELS['ovisocr2'].get('cli_args'), expected)

    def test_teleocr_uses_cuda_model_and_cpu_projector(self):
        expected = ['--device', 'CUDA0', '--mmproj-device', 'none', '-ngl', '99', '-t', '4']
        self.assertEqual(app.MODELS['teleocr'].get('cli_args'), expected)

    def test_run_one_passes_model_specific_cuda_flags_to_the_ovis_cli(self):
        for name in ('ovisocr2', 'teleocr'):
            with self.subTest(model=name):
                model = app.MODELS[name]
                def fake_run(command, **kwargs):
                    return SimpleNamespace(returncode=0, stdout='OCR text', stderr='')
                with patch('app.subprocess.run', side_effect=fake_run) as runner:
                    result = asyncio.run(app.run_one('image.png', 'model.gguf', 'mmproj.gguf', model['cli'], model['cli_args']))
                command = runner.call_args.args[0]
                self.assertEqual(command[0], PATCHED_CLI)
                self.assertEqual(command[-len(model['cli_args']):], model['cli_args'])
                self.assertEqual(result, 'OCR text')

    def test_pdf_and_tiff_page_limits_are_checked_before_rendering(self):
        for suffix, stdout in (('.pdf', 'Pages: 51' + chr(10)), ('.tiff', chr(10).join(['51'] * 51))):
            with tempfile.TemporaryDirectory() as td, self.subTest(format=suffix):
                with patch('app.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=stdout)) as runner:
                    with self.assertRaises(app.HTTPException) as raised:
                        app.render_pages('document' + suffix, suffix, td)
                self.assertEqual(raised.exception.status_code, 413)
                self.assertEqual(runner.call_count, 1)

    def test_tiff_page_count_matches_number_of_rendered_images(self):
        with tempfile.TemporaryDirectory() as td:
            def fake_run(command, **kwargs):
                if command[0:3] == ['magick', 'identify', '-format']:
                    return SimpleNamespace(returncode=0, stdout='1' + chr(10))
                Path(td, 'page-0000.png').touch()
                return SimpleNamespace(returncode=0, stdout='')
            with patch('app.subprocess.run', side_effect=fake_run) as runner:
                pages = app.render_pages('document.tiff', '.tiff', td)
        self.assertEqual(len(pages), 1)
        self.assertEqual(runner.call_count, 2)

    def test_pdf_incomplete_render_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            def fake_run(command, **kwargs):
                if command[0] == 'pdfinfo':
                    return SimpleNamespace(returncode=0, stdout='Pages: 2' + chr(10))
                Path(td, 'page-1.jpg').touch()
                return SimpleNamespace(returncode=0, stdout='')
            with patch('app.subprocess.run', side_effect=fake_run):
                with self.assertRaises(app.HTTPException) as raised:
                    app.render_pages('document.pdf', '.pdf', td)
        self.assertEqual(raised.exception.status_code, 400)

    def test_malformed_pdf_page_count_is_bad_request(self):
        with tempfile.TemporaryDirectory() as td:
            with patch('app.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='Pages: invalid' + chr(10))):
                with self.assertRaises(app.HTTPException) as raised:
                    app.render_pages('document.pdf', '.pdf', td)
        self.assertEqual(raised.exception.status_code, 400)

    def test_models_and_health_schema_are_documented(self):
        self.assertEqual(set(app.MODELS), {'ovisocr2', 'teleocr'})
        health = app.health()
        self.assertEqual(set(health['models']), {'ovisocr2', 'teleocr'})
        root = Path(__file__).resolve().parents[1]
        skill = (root / 'SKILL.md').read_text()
        prompt = (root / 'HERMES-INTEGRATION-PROMPT.md').read_text()
        self.assertIn('"models":{"ovisocr2":true,"teleocr":true}', skill)
        self.assertIn('"models":{"ovisocr2":true,"teleocr":true}', prompt)

    def test_cuda_service_config_and_no_cpu_only_documentation(self):
        root = Path(__file__).resolve().parents[1]
        service = (root / 'ovisocr.service').read_text()
        readme = (root / 'README.md').read_text()
        self.assertIn('CUDA_VISIBLE_DEVICES=0', service)
        self.assertNotIn('LLAMA_ARG_DEVICE=none', service)
        self.assertIn('CUDA0', readme)
        self.assertNotIn('CPU-only', readme)

    def test_wimpy_postdeploy_verification_is_documented(self):
        root = Path(__file__).resolve().parents[1]
        self.assertIn('tools/verify_ovisocr_llama_isolation.py', (root / 'README.md').read_text())
        self.assertIn('ocr-smoke.png', (root / 'README.md').read_text())
        self.assertIn('tools/verify_ovisocr_llama_isolation.py', (root / 'HERMES-INTEGRATION-PROMPT.md').read_text())

    def test_shared_gpu_use_is_not_misrepresented_as_isolation(self):
        root = Path(__file__).resolve().parents[1]
        self.assertIn('same physical GPU', (root / 'README.md').read_text())
        self.assertIn('contend for GPU resources', (root / 'SKILL.md').read_text())
        self.assertIn('shares the physical GPU', (root / 'HERMES-INTEGRATION-PROMPT.md').read_text())

    def test_page_cap_and_render_result_count_are_enforced(self):
        source = (Path(__file__).resolve().parents[1] / 'app.py').read_text()
        self.assertEqual(app.MAX_PAGES, 50)
        self.assertEqual(source.count('page_count > MAX_PAGES'), 2)
        self.assertIn('len(pages) != page_count', source)

    def test_api_includes_selected_model_page_count_and_duration(self):
        source = (Path(__file__).resolve().parents[1] / 'app.py').read_text()
        self.assertIn("'model':model", source)
        self.assertIn("'page_count':len(results)", source)
        self.assertIn("'elapsed_seconds':round", source)
        self.assertIn('"model":"ovisocr2"', (Path(__file__).resolve().parents[1] / 'SKILL.md').read_text())

    def test_size_timeout_and_frontend_contracts_remain(self):
        import inspect
        self.assertEqual(app.MAX_BYTES, 100 * 1024 * 1024)
        self.assertIn('timeout=300', inspect.getsource(app.run_one))
        html = (Path(__file__).resolve().parents[1] / 'static' / 'index.html').read_text()
        self.assertIn('Save Markdown', html)
        self.assertIn('application/pdf', html)
        self.assertIn('image/tiff', html)

    def test_fixture_is_present(self):
        self.assertTrue((Path(__file__).resolve().parent / 'fixtures' / 'ocr-smoke.png').is_file())

    def test_only_teleocr_keeps_projector_on_cpu(self):
        self.assertEqual(app.MODELS['ovisocr2']['cli_args'][3], 'CUDA0')
        self.assertEqual(app.MODELS['teleocr']['cli_args'][3], 'none')

    def test_page_only_advertises_ocr_models_and_disables_cache(self):
        response = app.index()
        html = (Path(app.STATIC) / 'index.html').read_text()
        self.assertIn('OvisOCR2-F16', html)
        self.assertIn('TeleOCR (NaviDC-OCR)', html)
        self.assertNotIn('Holo', html)
        self.assertIn('no-store', response.headers.get('cache-control', '').lower())


if __name__ == '__main__':
    unittest.main()
