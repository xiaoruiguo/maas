# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test smartctl functions."""

__all__ = []

import random
from subprocess import (
    CalledProcessError,
    DEVNULL,
    PIPE,
    Popen,
    TimeoutExpired,
)
from unittest.mock import call

from maasserver.testing.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from metadataserver.builtin_scripts import smartctl


class TestSmartCTL(MAASTestCase):

    def test_list_supported_drives(self):
        mock_print = self.patch(smartctl, 'print')
        mock_check_output = self.patch(smartctl, 'check_output')
        mock_check_output.side_effect = [
            b'Attached scsi disk sda        State: running',
            b'/dev/sda -d scsi # /dev/sda, SCSI device\n'
            b'/dev/sdb -d scsi # /dev/sdb, SCSI device',
            b'NAME MODEL            SERIAL\n'
            b'sda  HGST HDN724040AL abc123\n'
            b'sdb  HGST HDN724040AL abc123\n'
            b'sdc  HGST HDN724040AL abc123',
        ]
        mock_popen = self.patch(smartctl, 'Popen')
        mock_popen.side_effect = [
            Popen(['echo', 'SMART support is: Available'], stdout=PIPE),
            Popen(['echo', 'SMART support is: Unavailable'], stdout=PIPE),
        ]

        self.assertItemsEqual(
            [['/dev/sdb', '-d', 'scsi']], smartctl.list_supported_drives())
        self.assertThat(
            mock_check_output, MockCallsMatch(
                call(
                    ['sudo', 'iscsiadm', '-m', 'session', '-P', '3'],
                    timeout=smartctl.TIMEOUT, stderr=DEVNULL),
                call(
                    ['sudo', 'smartctl', '--scan-open'],
                    timeout=smartctl.TIMEOUT),
                call(
                    [
                        'lsblk', '--exclude', '1,2,7', '-d', '-l', '-o',
                        'NAME,MODEL,SERIAL', '-x', 'NAME',
                    ], timeout=smartctl.TIMEOUT, stderr=DEVNULL)))
        self.assertThat(
            mock_popen, MockCalledOnceWith(
                ['sudo', 'smartctl', '-i', '/dev/sdb', '-d', 'scsi'],
                stdout=PIPE, stderr=DEVNULL))
        self.assertThat(
            mock_print, MockCallsMatch(
                call(),
                call('The following drives do not support SMART:'),
                call('NAME MODEL            SERIAL'),
                call('sdc  HGST HDN724040AL abc123'),
                call()))

    def test_list_supported_drives_ignores_iscsiadm_timeout(self):
        mock_print = self.patch(smartctl, 'print')
        mock_check_output = self.patch(smartctl, 'check_output')
        mock_check_output.side_effect = [
            TimeoutExpired('iscsiadm', 60),
            b'/dev/sda -d scsi # /dev/sda, SCSI device',
            b'NAME MODEL            SERIAL\n'
            b'sda  HGST HDN724040AL abc123',
        ]
        mock_popen = self.patch(smartctl, 'Popen')
        mock_popen.return_value = Popen(
            ['echo', 'SMART support is: Available'], stdout=PIPE)

        self.assertItemsEqual(
            [['/dev/sda', '-d', 'scsi']], smartctl.list_supported_drives())
        self.assertThat(
            mock_check_output, MockCallsMatch(
                call(
                    ['sudo', 'iscsiadm', '-m', 'session', '-P', '3'],
                    timeout=smartctl.TIMEOUT, stderr=DEVNULL),
                call(
                    ['sudo', 'smartctl', '--scan-open'],
                    timeout=smartctl.TIMEOUT),
                call(
                    [
                        'lsblk', '--exclude', '1,2,7', '-d', '-l', '-o',
                        'NAME,MODEL,SERIAL', '-x', 'NAME',
                    ], timeout=smartctl.TIMEOUT, stderr=DEVNULL)))
        self.assertThat(
            mock_popen, MockCalledOnceWith(
                ['sudo', 'smartctl', '-i', '/dev/sda', '-d', 'scsi'],
                stdout=PIPE, stderr=DEVNULL))
        self.assertThat(mock_print, MockNotCalled())

    def test_list_supported_drives_ignores_iscsiadm_errors(self):
        mock_print = self.patch(smartctl, 'print')
        mock_check_output = self.patch(smartctl, 'check_output')
        mock_check_output.side_effect = [
            CalledProcessError(1, 'iscsiadm'),
            b'/dev/sda -d scsi # /dev/sda, SCSI device',
            b'NAME MODEL            SERIAL\n'
            b'sda  HGST HDN724040AL abc123',
        ]
        mock_popen = self.patch(smartctl, 'Popen')
        mock_popen.return_value = Popen(
            ['echo', 'SMART support is: Available'], stdout=PIPE)

        self.assertItemsEqual(
            [['/dev/sda', '-d', 'scsi']], smartctl.list_supported_drives())
        self.assertThat(
            mock_check_output, MockCallsMatch(
                call(
                    ['sudo', 'iscsiadm', '-m', 'session', '-P', '3'],
                    timeout=smartctl.TIMEOUT, stderr=DEVNULL),
                call(
                    ['sudo', 'smartctl', '--scan-open'],
                    timeout=smartctl.TIMEOUT),
                call(
                    [
                        'lsblk', '--exclude', '1,2,7', '-d', '-l', '-o',
                        'NAME,MODEL,SERIAL', '-x', 'NAME',
                    ], timeout=smartctl.TIMEOUT, stderr=DEVNULL)))
        self.assertThat(
            mock_popen, MockCalledOnceWith(
                ['sudo', 'smartctl', '-i', '/dev/sda', '-d', 'scsi'],
                stdout=PIPE, stderr=DEVNULL))
        self.assertThat(mock_print, MockNotCalled())

    def test_run_smartctl_selftest(self):
        drive = factory.make_name('drive')
        test = factory.make_name('test')
        run_smartctl = smartctl.RunSmartCtl([drive], test)
        mock_check_call = self.patch(smartctl, 'check_call')
        mock_check_output = self.patch(smartctl, 'check_output')
        mock_check_output.return_value = (
            b'Self-test execution status:      (   0)')

        run_smartctl._run_smartctl_selftest()

        self.assertThat(
            mock_check_call, MockCalledOnceWith(
                ['sudo', 'smartctl', '-s', 'on', '-t', test, drive],
                timeout=smartctl.TIMEOUT, stdout=DEVNULL, stderr=DEVNULL))
        self.assertThat(
            mock_check_output, MockCalledOnceWith(
                ['sudo', 'smartctl', '-c', drive], timeout=smartctl.TIMEOUT))

    def test_run_smartctl_selftest_waits_for_finish(self):
        drive = factory.make_name('drive')
        test = factory.make_name('test')
        self.patch(smartctl, 'sleep')
        run_smartctl = smartctl.RunSmartCtl([drive], test)
        mock_check_call = self.patch(smartctl, 'check_call')
        mock_check_output = self.patch(smartctl, 'check_output')
        mock_check_output.side_effect = [
            b'Self-test execution status:      ( 249)',
            b'Self-test execution status:      ( 249)',
            b'Self-test execution status:      ( 249)',
            b'Self-test execution status:      (   0)',
        ]

        run_smartctl._run_smartctl_selftest()

        self.assertThat(
            mock_check_call, MockCalledOnceWith(
                ['sudo', 'smartctl', '-s', 'on', '-t', test, drive],
                timeout=smartctl.TIMEOUT, stdout=DEVNULL, stderr=DEVNULL))
        self.assertThat(
            mock_check_output, MockCallsMatch(
                call(
                    ['sudo', 'smartctl', '-c', drive],
                    timeout=smartctl.TIMEOUT),
                call(
                    ['sudo', 'smartctl', '-c', drive],
                    timeout=smartctl.TIMEOUT),
                call(
                    ['sudo', 'smartctl', '-c', drive],
                    timeout=smartctl.TIMEOUT),
                call(
                    ['sudo', 'smartctl', '-c', drive],
                    timeout=smartctl.TIMEOUT)))

    def test_run_smartctl_selftest_sets_failure_on_timeout_of_test_start(self):
        drive = factory.make_name('drive')
        test = factory.make_name('test')
        run_smartctl = smartctl.RunSmartCtl([drive], test)
        mock_check_call = self.patch(smartctl, 'check_call')
        mock_check_call.side_effect = TimeoutExpired('smartctl', 60)
        mock_check_output = self.patch(smartctl, 'check_output')

        run_smartctl._run_smartctl_selftest()

        self.assertTrue(run_smartctl.running_test_failed)
        self.assertThat(
            mock_check_call, MockCalledOnceWith(
                ['sudo', 'smartctl', '-s', 'on', '-t', test, drive],
                timeout=smartctl.TIMEOUT, stdout=DEVNULL, stderr=DEVNULL))
        self.assertThat(mock_check_output, MockNotCalled())

    def test_run_smartctl_selftest_sets_failure_on_exec_fail_test_start(self):
        drive = factory.make_name('drive')
        test = factory.make_name('test')
        run_smartctl = smartctl.RunSmartCtl([drive], test)
        mock_check_call = self.patch(smartctl, 'check_call')
        mock_check_call.side_effect = CalledProcessError(1, 'smartctl')
        mock_check_output = self.patch(smartctl, 'check_output')

        run_smartctl._run_smartctl_selftest()

        self.assertTrue(run_smartctl.running_test_failed)
        self.assertThat(
            mock_check_call, MockCalledOnceWith(
                ['sudo', 'smartctl', '-s', 'on', '-t', test, drive],
                timeout=smartctl.TIMEOUT, stdout=DEVNULL, stderr=DEVNULL))
        self.assertThat(mock_check_output, MockNotCalled())

    def test_run_smartctl_selftest_sets_failure_on_timeout_status_check(self):
        drive = factory.make_name('drive')
        test = factory.make_name('test')
        run_smartctl = smartctl.RunSmartCtl([drive], test)
        mock_check_call = self.patch(smartctl, 'check_call')
        mock_check_output = self.patch(smartctl, 'check_output')
        mock_check_output.side_effect = TimeoutExpired('smartctl', 60)

        run_smartctl._run_smartctl_selftest()

        self.assertTrue(run_smartctl.running_test_failed)
        self.assertThat(
            mock_check_call, MockCalledOnceWith(
                ['sudo', 'smartctl', '-s', 'on', '-t', test, drive],
                timeout=smartctl.TIMEOUT, stdout=DEVNULL, stderr=DEVNULL))
        self.assertThat(
            mock_check_output, MockCalledOnceWith(
                ['sudo', 'smartctl', '-c', drive], timeout=smartctl.TIMEOUT))

    def test_run_smartctl_selftest_sets_failure_on_exc_fail_status_check(self):
        drive = factory.make_name('drive')
        test = factory.make_name('test')
        run_smartctl = smartctl.RunSmartCtl([drive], test)
        mock_check_call = self.patch(smartctl, 'check_call')
        mock_check_output = self.patch(smartctl, 'check_output')
        mock_check_output.side_effect = CalledProcessError(1, 'smartctl')

        run_smartctl._run_smartctl_selftest()

        self.assertTrue(run_smartctl.running_test_failed)
        self.assertThat(
            mock_check_call, MockCalledOnceWith(
                ['sudo', 'smartctl', '-s', 'on', '-t', test, drive],
                timeout=smartctl.TIMEOUT, stdout=DEVNULL, stderr=DEVNULL))
        self.assertThat(
            mock_check_output, MockCalledOnceWith(
                ['sudo', 'smartctl', '-c', drive], timeout=smartctl.TIMEOUT))

    def test_was_successful(self):
        run_smartctl = smartctl.RunSmartCtl(
            [factory.make_name('drive')], factory.make_name('test'))
        run_smartctl.returncode = random.choice([0, 4])
        self.assertTrue(run_smartctl.was_successful)
        run_smartctl.returncode = random.randint(5, 256)
        self.assertFalse(run_smartctl.was_successful)
