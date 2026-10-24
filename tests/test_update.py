"""Unit tests for update.py's key handling. No network: fetch is mocked."""
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import update  # noqa: E402

MGMT = "sk-or-v1-FAKEMANAGEMENT"
APP = "sk-or-v1-FAKEAPPKEY"
LISTING = [
    {"name": "Hermes", "label": "sk-or-v1-abc...123", "disabled": False, "usage_daily": 0.1,
     "usage_weekly": 1.0, "usage_monthly": 3.0, "limit": 10, "limit_remaining": 9, "limit_reset": "weekly"},
    {"name": "", "label": "sk-or-v1-def...456", "disabled": False, "usage_daily": 0.2,
     "usage_weekly": 2.0, "usage_monthly": 4.0, "limit": None, "limit_remaining": None, "limit_reset": None},
    {"name": "Old", "label": "sk-or-v1-ghi...789", "disabled": True, "usage_daily": 9,
     "usage_weekly": 9, "usage_monthly": 9},
]
APP_KD = {"usage_daily": 5.0, "usage_weekly": 5.0, "usage_monthly": 5.0, "limit": 0}


def http_error(code):
    return urllib.error.HTTPError("https://x", code, "nope", {}, None)


def fake_fetch(key, path):
    if key == MGMT:
        if path == "/api/v1/auth/key":
            raise http_error(401)
        if path.startswith("/api/v1/keys"):
            return {"data": LISTING}
        if path == "/api/v1/credits":
            return {"data": {"total_credits": 20.0, "total_usage": 7.0}}
    if key == APP:
        if path == "/api/v1/auth/key":
            return {"data": APP_KD}
        if path.startswith("/api/v1/keys"):
            raise http_error(401)
        if path == "/api/v1/credits":
            return {"data": {"total_credits": 20.0, "total_usage": 7.0}}
    raise AssertionError("unexpected call %s" % path)


class UpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "overview.json")
        patches = [
            mock.patch.object(update, "OUT", self.out),
            mock.patch.object(update, "HISTORY", os.path.join(self.tmp, "history.jsonl")),
            mock.patch.object(update, "fetch", side_effect=fake_fetch),
            mock.patch.object(update, "load_names", return_value={}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def run_with(self, keys):
        with mock.patch.object(update, "load_keys", return_value=keys):
            rc = update.main()
        with open(self.out) as f:
            return rc, json.load(f)

    def test_management_key_lists_every_key(self):
        rc, rec = self.run_with([MGMT])
        self.assertEqual(rc, 0)
        self.assertTrue(rec["managementKey"])
        self.assertEqual(rec["keys"], 2)  # disabled key skipped
        self.assertEqual([k["label"] for k in rec["keyBreakdown"]], ["Hermes", "Key 2"])
        self.assertAlmostEqual(rec["week"]["cost"], 3.0)
        self.assertEqual(rec["credits"]["total"], 20.0)

    def test_management_key_reports_more_than_three_keys(self):
        many = [dict(LISTING[0], name="Key%d" % i, label="sk-or-v1-x...%d" % i) for i in range(6)]
        with mock.patch.dict(globals(), {"LISTING": many}):
            rc, rec = self.run_with([MGMT])
        self.assertEqual(rc, 0)
        self.assertEqual(rec["keys"], 6)
        self.assertEqual(len(rec["keyBreakdown"]), 6)  # the dropdown lists all of these
        self.assertEqual(rec["key3"]["label"], "Key3")  # old fields kept for compatibility

    def test_management_key_replaces_app_keys(self):
        rc, rec = self.run_with([APP, MGMT])
        self.assertEqual(rc, 0)
        self.assertTrue(rec["managementKey"])
        self.assertAlmostEqual(rec["today"]["cost"], 0.3)  # app key not double-counted

    def test_normal_key_fallback(self):
        rc, rec = self.run_with([APP])
        self.assertEqual(rc, 0)
        self.assertFalse(rec["managementKey"])
        self.assertEqual(rec["keys"], 1)
        self.assertAlmostEqual(rec["today"]["cost"], 5.0)

    def test_no_key_is_a_clear_state(self):
        rc, rec = self.run_with([])
        self.assertEqual(rec["error"], "no-api-key")

    def test_label_never_comes_from_the_key(self):
        _, rec = self.run_with([MGMT])
        self.assertNotIn("sk-or", json.dumps(rec))


if __name__ == "__main__":
    unittest.main()
