"""First-run locale detection must not replace a saved preference."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ft_tui.db.database import make_session_factory
from ft_tui.features.settings.adapters.storage import get_setting, save_settings
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.ui.select import Select


class LanguageDetectionTests(unittest.TestCase):
    def test_primary_locale_and_english_fallback(self):
        from ft_tui.i18n import detect_language
        cases = [
            ({'LANGUAGE': 'fr_FR:en', 'LANG': 'en_US.UTF-8'}, 'fr'),
            ({'LC_ALL': 'es_ES.UTF-8', 'LANG': 'fr_FR.UTF-8'}, 'es'),
            ({'LC_MESSAGES': 'fr-CA', 'LANG': 'en_US.UTF-8'}, 'fr'),
            ({'LANG': 'es_MX.UTF-8'}, 'es'),
            ({'LANGUAGE': 'de:fr'}, 'en'),
            ({'LANG': 'C.UTF-8'}, 'en'),
            ({'LANG': 'invalid'}, 'en'),
            ({}, 'en'),
        ]
        for environment, expected in cases:
            with self.subTest(environment=environment), patch.dict('os.environ', environment, clear=True), patch('locale.getlocale', return_value=(None, None)):
                self.assertEqual(detect_language(), expected)
        with patch.dict('os.environ', {}, clear=True), patch('locale.getlocale', return_value=('fr_FR', 'UTF-8')):
            self.assertEqual(detect_language(), 'fr')


class OnboardingLanguageTests(unittest.IsolatedAsyncioTestCase):
    async def test_detected_language_is_visible_and_persisted_when_skipping(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "ui.sqlite"}')
            try:
                with patch.dict('os.environ', {'LANGUAGE': 'fr_FR:en'}, clear=True):
                    app = FortyTwoTuiApp(factory, None)
                    async with app.run_test(size=(140, 50)):
                        self.assertEqual(app.language, 'fr')
                        self.assertEqual(app.screen.query_one('#onboarding-language', Select).value, 'fr')
                        self.assertIn('Connectez', str(app.screen.query_one('#onboarding-title').render()))
                        await app._finish_onboarding(None)
                    with factory() as session:
                        self.assertEqual(get_setting(session, 'language'), 'fr')
            finally:
                factory.kw['bind'].dispose()

    async def test_saved_language_and_existing_installations_are_preserved(self):
        for settings, expected in [({'language': 'es'}, 'es'), ({'onboarding_completed': 'true'}, 'en'), ({'favorite_editor': 'vim'}, 'en')]:
            with self.subTest(settings=settings), TemporaryDirectory() as directory:
                factory = make_session_factory(f'sqlite:///{Path(directory) / "ui.sqlite"}')
                try:
                    with factory() as session:
                        save_settings(session, settings)
                    with patch.dict('os.environ', {'LANGUAGE': 'fr'}, clear=True):
                        app = FortyTwoTuiApp(factory, None)
                        async with app.run_test(size=(140, 50)):
                            self.assertEqual(app.language, expected)
                            self.assertNotEqual(type(app.screen).__name__, 'OnboardingScreen')
                finally:
                    factory.kw['bind'].dispose()
