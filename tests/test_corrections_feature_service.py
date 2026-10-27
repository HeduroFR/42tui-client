"""Headless correction operations retain account and dispatch boundaries."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from ft_tui.slots.model import Slot
from ft_tui.features.corrections.service import (
    CorrectionsService, MutationFailure, StaleCorrectionsContext,
)

B = datetime(2026, 10, 27, 10, tzinfo=timezone.utc)
E = B + timedelta(hours=1)
S = Slot(('1',), B, E)
T = Slot(('2',), E, E + timedelta(hours=1))

class Provider:
    def __init__(self):
        self.calls = []
        self.value = {'account_id': '42', 'can_write': True, 'slots': (S,)}
    def get_correction_slots(self, begin, end):
        self.calls.append('read'); return self.value
    def save_correction_slot(self, slot, begin, end):
        self.calls.append(('save', slot, begin, end))
    def delete_correction_slot(self, slot):
        self.calls.append(('delete', slot))

class CorrectionsServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_rejects_wrong_account_and_malformed_values(self):
        provider = Provider(); service = CorrectionsService(provider)
        for value in ({**provider.value, 'account_id': '43'},
                      {**provider.value, 'can_write': 1},
                      {**provider.value, 'slots': (S, S)},
                      {**provider.value, 'slots': ({'id': 1},)}):
            provider.value = value
            with self.assertRaises(ValueError):
                await service.snapshot(B, E, account_id='42', current=lambda: True)

    async def test_snapshot_rejects_context_changed_during_request(self):
        provider = Provider(); live = [True]
        def read(*args):
            live[0] = False; return provider.value
        provider.get_correction_slots = read
        with self.assertRaises(StaleCorrectionsContext):
            await CorrectionsService(provider).snapshot(B, E, account_id='42', current=lambda: live[0])

    async def test_queued_mutation_is_fenced_at_actual_dispatch(self):
        provider = Provider(); live = [True]
        async def queued(function, *args):
            live[0] = False
            return function(*args)
        with patch('ft_tui.features.corrections.service.asyncio.to_thread', queued):
            with self.assertRaises(StaleCorrectionsContext):
                await CorrectionsService(provider).save(None, B, E, current=lambda: live[0])
        self.assertEqual(provider.calls, [])

    async def test_each_delete_is_fenced_and_stops_after_context_change(self):
        provider = Provider(); live = [True]
        def delete(slot):
            provider.calls.append(slot); live[0] = False
        provider.delete_correction_slot = delete
        with self.assertRaises(StaleCorrectionsContext):
            await CorrectionsService(provider).delete((S, T), current=lambda: live[0])
        self.assertEqual(provider.calls, [S])

    async def test_whole_batch_validation_protects_booked_slots_before_first_write(self):
        provider = Provider()
        with self.assertRaises(ValueError):
            await CorrectionsService(provider).delete((S, Slot(T.ids, T.begin, T.end, True)), current=lambda: True)
        self.assertEqual(provider.calls, [])

    async def test_unknown_save_outcome_is_never_retried(self):
        provider = Provider(); failure = TimeoutError('unknown outcome')
        def save(*args):
            provider.calls.append(args); raise failure
        provider.save_correction_slot = save
        with self.assertRaises(MutationFailure) as caught:
            await CorrectionsService(provider).save(S, B, E, current=lambda: True)
        self.assertIs(caught.exception.error, failure)
        self.assertEqual(caught.exception.completed, 0)
        self.assertEqual(len(provider.calls), 1)

    async def test_partial_delete_retains_completed_count_and_never_retries(self):
        provider = Provider(); failure = TimeoutError('unknown outcome')
        def delete(slot):
            provider.calls.append(slot)
            if slot == T: raise failure
        provider.delete_correction_slot = delete
        with self.assertRaises(MutationFailure) as caught:
            await CorrectionsService(provider).delete((S, T), current=lambda: True)
        self.assertIs(caught.exception.error, failure)
        self.assertEqual(caught.exception.completed, 1)
        self.assertEqual(provider.calls, [S, T])

    async def test_valid_snapshot_and_single_save_preserve_provider_arguments(self):
        provider = Provider(); service = CorrectionsService(provider)
        self.assertEqual(await service.snapshot(B, E, account_id='42', current=lambda: True), provider.value)
        await service.save(S, B, E, current=lambda: True)
        self.assertEqual(provider.calls, ['read', ('save', S, B, E)])

    async def test_explicit_provider_overrides_constructor_binding(self):
        old = Provider(); new = Provider(); service = CorrectionsService(old)
        await service.save(None, B, E, current=lambda: True, provider=new)
        self.assertEqual(old.calls, [])
        self.assertEqual(new.calls, [('save', None, B, E)])

    async def test_queued_second_delete_is_fenced_before_dispatch(self):
        provider = Provider(); live = [True]; queued = [0]
        async def thread(function):
            queued[0] += 1
            if queued[0] == 2: live[0] = False
            return function()
        with patch('ft_tui.features.corrections.service.asyncio.to_thread', thread):
            with self.assertRaises(StaleCorrectionsContext):
                await CorrectionsService(provider).delete((S, T), current=lambda: live[0])
        self.assertEqual(provider.calls, [('delete', S)])

    async def test_booked_save_and_invalid_interval_are_rejected_without_dispatch(self):
        provider = Provider(); service = CorrectionsService(provider)
        for slot, begin, end in ((Slot(S.ids, B, E, True), B, E),
                                 (None, E, B), (None, B.replace(minute=1), E)):
            with self.assertRaises(ValueError):
                await service.save(slot, begin, end, current=lambda: True)
        self.assertEqual(provider.calls, [])

    def test_legacy_module_and_dataclass_and_patch_identity(self):
        from importlib import import_module
        for old, new in (('ft_tui.slots.model', 'model'),
                         ('ft_tui.api.slots_types', 'types'),
                         ('ft_tui.ui.correction_slots', 'views'),
                         ('ft_tui.ui.slots_calendar', 'calendar')):
            self.assertIs(import_module(old), import_module('ft_tui.features.corrections.' + new))
        from ft_tui.features.corrections.model import Slot as OwnedSlot
        self.assertIs(Slot, OwnedSlot)
        with patch('ft_tui.ui.slots_calendar.datetime', sentinel := object()):
            self.assertIs(import_module('ft_tui.features.corrections.calendar').datetime, sentinel)
