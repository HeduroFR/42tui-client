"""Bounded trusted metadata, exact compatibility, custom pins and offline behavior."""
from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import Mock, patch

import httpx

from ft_tui.features.projects.adapters.tester_catalog import bundled_catalog, load_catalog
from ft_tui.features.projects.adapters import tester_updates as updates


class TesterUpdateTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        location = patch.object(updates, 'data_dir', return_value=self.root)
        location.start()
        self.addCleanup(location.stop)
        self.catalog = bundled_catalog()
        self.tester = self.catalog.testers[0]
        self.manifest = {'version': 1, 'testers': [
            {'id': self.tester.id, 'base': self.tester.update_key, 'ref': 'a' * 40}]}
        self.terminal = Mock()

    def cache(self, manifest=None, checked=None):
        (self.root / 'tester-updates.json').write_text(json.dumps({
            'manifest': self.manifest if manifest is None else manifest,
            'checked': time.time() if checked is None else checked}))

    def test_only_the_exact_bundled_definition_can_change_and_image_identity_changes(self):
        result = updates.apply_manifest(self.catalog, self.manifest)
        self.assertEqual(result.testers[0], replace(self.tester, ref='a' * 40))
        self.assertNotEqual(result.testers[0].image, self.tester.image)
        self.assertEqual(result.testers[1:], self.catalog.testers[1:])
        incompatible = replace(self.tester, update_key='f' * 64)
        catalog = replace(self.catalog, testers=(incompatible,))
        self.assertEqual(updates.apply_manifest(catalog, self.manifest), catalog)
        # Keep the base identity after an update so a second approved revision applies.
        self.manifest['testers'][0]['ref'] = 'b' * 40
        self.assertEqual(updates.apply_manifest(result, self.manifest).testers[0].ref, 'b' * 40)

    def test_user_overrides_and_disabled_testers_stay_user_controlled(self):
        from importlib.resources import files
        content = files('ft_tui').joinpath('testers.toml').read_text()
        path = self.root / 'custom.toml'
        # Even an override identical to the bundled entry is an explicit pin.
        path.write_text(content.split('[[testers]]')[0] + '[[testers]]' + content.split('[[testers]]')[1])
        catalog = load_catalog(path)
        self.assertFalse(catalog.testers[0].update_key)
        self.assertEqual(updates.apply_manifest(catalog, self.manifest), catalog)
        path.write_text(f'[[testers]]\nid="{self.tester.id}"\nenabled=false\n')
        disabled = load_catalog(path)
        self.assertNotIn(self.tester.id, {t.id for t in updates.apply_manifest(disabled, self.manifest).testers})

    def test_changed_recipe_or_definition_invalidates_approval(self):
        from ft_tui.features.projects.adapters import tester_catalog
        with patch.object(tester_catalog.Tester, 'image', new_callable=unittest.mock.PropertyMock,
                          return_value='new recipe'):
            changed = bundled_catalog().testers[0]
        self.assertNotEqual(changed.update_key, self.tester.update_key)
        catalog = replace(self.catalog, testers=(changed,))
        self.assertEqual(updates.apply_manifest(catalog, self.manifest).testers[0], changed)

    def test_download_uses_fixed_origin_and_bounds_metadata(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, json=self.manifest)
        with httpx.Client(transport=httpx.MockTransport(handler), trust_env=False, follow_redirects=False) as client:
            self.assertEqual(updates.fetch_manifest(client), self.manifest)
        self.assertEqual(str(requests[0].url), updates.CATALOG_URL)
        self.assertNotIn('authorization', requests[0].headers)
        for response in (httpx.Response(302, headers={'Location': 'https://example.com/catalog'}),
                         httpx.Response(200, content=b'x' * (updates.MAX_BYTES + 1)),
                         httpx.Response(200, content=b'not JSON')):
            with (self.subTest(response=response),
                  httpx.Client(transport=httpx.MockTransport(lambda request: response)) as client):
                with self.assertRaises((httpx.HTTPError, ValueError)):
                    updates.fetch_manifest(client)
        with (httpx.Client(transport=httpx.MockTransport(handler)) as client,
              patch.object(updates, 'time') as clock):
            clock.monotonic.side_effect = (0, 6)
            with self.assertRaisesRegex(ValueError, 'time limit'):
                updates.fetch_manifest(client)

    def test_schema_rejects_unknown_fields_duplicate_approvals_and_unpinned_refs(self):
        entry = self.manifest['testers'][0]
        invalid = [[], {}, {**self.manifest, 'version': True}, {**self.manifest, 'extra': 1},
                   {**self.manifest, 'testers': [entry, entry]},
                   {**self.manifest, 'testers': [entry] * 257}]
        for key, value in (('ref', 'main'), ('ref', '../escape'), ('ref', True), ('base', 'a' * 40),
                           ('id', None), ('id', 'x' * 64), ('repository', 'https://example.com/evil.git')):
            invalid.append({'version': 1, 'testers': [{**entry, key: value}]})
        for manifest in invalid:
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                updates.validate_manifest(manifest)

    def test_success_is_cached_atomically_and_reused_for_an_hour(self):
        with patch.object(updates, 'fetch_manifest', return_value=self.manifest) as fetch:
            first = updates.refresh_catalog(self.catalog, self.terminal)
            self.assertEqual(first.testers[0].ref, 'a' * 40)
            self.assertEqual(updates.refresh_catalog(self.catalog, self.terminal), first)
            fetch.assert_called_once_with()
        value = json.loads((self.root / 'tester-updates.json').read_text())
        self.assertEqual(value['manifest'], self.manifest)
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ['tester-updates.json'])

    def test_offline_or_invalid_download_preserves_previous_cache_or_bundled_pin(self):
        for failure in (httpx.ConnectError('offline'), ValueError('invalid metadata')):
            for cached in (False, True):
                with self.subTest(failure=failure, cached=cached):
                    path = self.root / 'tester-updates.json'
                    if cached:
                        self.cache(checked=0)
                    else:
                        path.unlink(missing_ok=True)
                    before = path.read_bytes() if cached else None
                    with patch.object(updates, 'fetch_manifest', side_effect=failure):
                        result = updates.refresh_catalog(self.catalog, self.terminal)
                    self.assertEqual(result.testers[0].ref, 'a' * 40 if cached else self.tester.ref)
                    if cached:
                        self.assertEqual(path.read_bytes(), before)

    def test_bad_or_future_cache_is_checked_again(self):
        for value in ('bad JSON', '[]', 'x' * (updates.MAX_BYTES * 2 + 1),
                      json.dumps({'checked': 'never', 'manifest': self.manifest}),
                      json.dumps({'checked': time.time() + 3600, 'manifest': self.manifest})):
            with self.subTest(value=value[:80]):
                (self.root / 'tester-updates.json').write_text(value)
                with patch.object(updates, 'fetch_manifest', return_value=self.manifest) as fetch:
                    self.assertEqual(updates.refresh_catalog(self.catalog, self.terminal).testers[0].ref, 'a' * 40)
                    fetch.assert_called_once()

    def test_cache_write_failure_does_not_block_the_run(self):
        (self.root / 'tester-updates.json').mkdir()
        with patch.object(updates, 'fetch_manifest', return_value=self.manifest):
            self.assertEqual(updates.refresh_catalog(self.catalog, self.terminal).testers[0].ref, 'a' * 40)
        self.assertEqual(len(list(self.root.iterdir())), 1)
        self.terminal.write.assert_any_call('Tester update cache could not be saved. Updates still apply to this run.')

    def test_custom_only_catalog_never_uses_network(self):
        catalog = replace(self.catalog, testers=(replace(self.tester, update_key=''),))
        with patch.object(updates, 'fetch_manifest') as fetch:
            self.assertIs(updates.refresh_catalog(catalog, self.terminal), catalog)
            fetch.assert_not_called()

    def test_published_catalog_covers_current_bundled_testers(self):
        path = Path(__file__).resolve().parents[1] / 'tester-updates/v1.json'
        manifest = json.loads(path.read_text())
        updates.validate_manifest(manifest)
        entries = {(entry['id'], entry['base']) for entry in manifest['testers']}
        self.assertTrue({(tester.id, tester.update_key) for tester in self.catalog.testers} <= entries)
