"""Compatibilidad real C++/Python en el PC, sin ejecutar firmware o usar la red."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from iot_shared.angles import ServoLimits
from iot_shared.errors import ValidationError
from iot_shared.messages import DistanceReading, ServoCommand, ServoState
from tests.support import OfflineTestCase, PROJECT_ROOT


@unittest.skipUnless(shutil.which("g++"), "G++ no disponible para pruebas C++ en el PC")
class FirmwareContractTests(OfflineTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.directory = Path(temporary.name)
        cls.distributed = cls.compile("distributed/test_distributed.cpp", "distributed.exe")
        cls.diagnostic = cls.compile("diagnostics/test_servo_sequence.cpp", "diagnostic.exe")

    @classmethod
    def compile(cls, source, name):
        executable = cls.directory / name
        result = subprocess.run(
            [shutil.which("g++"), "-std=c++11", "-Wall", "-Wextra", "-Werror", "-pedantic",
             "-I", str(PROJECT_ROOT / "firmware/include"),
             str(PROJECT_ROOT / "firmware/test" / source), "-o", str(executable)],
            capture_output=True, text=True, timeout=90,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return executable

    def test_portable_reconnection_motion_and_confirmation_logic(self):
        result = subprocess.run([str(self.distributed)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_previous_diagnostic_sequence_still_passes(self):
        result = subprocess.run([str(self.diagnostic)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cpp_messages_are_accepted_by_unchanged_python_contracts(self):
        result = subprocess.run([str(self.distributed), "--encode"], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 5)
        for line in lines[:3]:
            reading = DistanceReading.from_json(line)
            self.assertEqual(reading.device_id, "sensor-01")
            self.assertEqual(reading.uptime_ms, 4294967295)
        for line in lines[3:]:
            state = ServoState.from_json(line)
            self.assertEqual(state.device_id, "actuator-01")
            self.assertEqual(state.command_id, "cmd-fixture-1")
            self.assertEqual(state.status, "applied")

    def test_cpp_command_parser_matches_python_for_valid_and_adverse_inputs(self):
        corpus = [json.dumps({"angle": value, "command_id": "cmd-1"}).encode()
                  for value in range(-10, 191)]
        for value in (True, False, None, "90", 90.0, 90.5, {}, [], 10**300, float("nan"), float("inf")):
            corpus.append(json.dumps({"angle": value, "command_id": "cmd-1"}).encode())
        for identifier in ("", "a" * 64, "a" * 65, "a b", "a/b", "-id", "_id", "ñ", None, True):
            corpus.append(json.dumps({"angle": 90, "command_id": identifier}, ensure_ascii=False).encode())
        corpus.extend(payload.encode() for payload in (
            "", "null", "true", "[]", "90", "{}",
            '{"angle":90}', '{"command_id":"a"}',
            '{"angle":90,"command_id":"a","other":0}',
            '{"angle":90,"angle":100,"command_id":"a"}',
            '{"angle":90,"command_id":"a","command_id":"b"}',
            '{angle:90,"command_id":"a"}', "{'angle':90,'command_id':'a'}",
            '{"angle":+90,"command_id":"a"}', '{"angle":090,"command_id":"a"}',
            '{"angle":-0,"command_id":"a"}', '{"angle":90e0,"command_id":"a"}',
            '{"angle":90.,"command_id":"a"}', '{"angle":90,"command_id":"a",}',
            '{"angle":90,"command_id":"a"} true',
            ' \r\n{ "command_id" : "CMD.1_a-2", "angle" : 90 }\t',
            r'{"\u0061ngle":90,"command\u005fid":"\u0063md-1"}',
            r'{"angle":90,"command_id":"\ud800"}',
            r'{"angle":90,"command_id":"a\n"}',
            r'{"angle":90,"command_id":"a\u0000b"}',
            r'{"angle":90,"\u0061ngle":91,"command_id":"a"}',
        ))
        corpus.extend([b'{"angle":90,"command_id":"\xff"}',
                       b'{"angle":90,"command_id":"a"}\x00',
                       b' ' * 1000 + b'{"angle":90,"command_id":"a"}'])
        for minimum, maximum in ((0, 180), (15, 165), (90, 91)):
            limits = ServoLimits(minimum, maximum)
            result = subprocess.run(
                [str(self.distributed), "--decode", str(minimum), str(maximum)],
                input="\n".join(payload.hex() for payload in corpus) + "\n",
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            decoded = result.stdout.splitlines()
            self.assertEqual(len(decoded), len(corpus))
            for payload, actual in zip(corpus, decoded):
                try:
                    command = ServoCommand.from_json(payload, limits)
                    expected = f"OK\t{command.angle}\t{command.command_id}"
                except ValidationError:
                    expected = "ERR"
                with self.subTest(limits=(minimum, maximum), payload=payload):
                    self.assertEqual(actual, expected)
