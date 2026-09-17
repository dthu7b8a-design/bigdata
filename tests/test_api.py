"""Run: python -m unittest discover -s tests -p test_api.py -v.

Set BIGDATA_MYSQL_INTEGRATION=1 to also test an isolated, disposable database
on the dedicated 3307 instance. Never uses the pre-existing 3306 instance.
"""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

import pymysql
from dotenv import dotenv_values

from api import create_app, db
from api.import_results import import_snapshot


def fixture():
    return {"meta": {"source": "API test", "run": 1}, "kpis": {"sessions": 3},
            "charts": {name: [{"label": "测试", "value": 3}] for name in db.CHART_NAMES},
            "quality": {"valid": 3}, "model": {"status": "ok"}}


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "index.html").write_text("<html>dashboard</html>", encoding="utf-8")
        (self.root / "assets").mkdir()
        (self.root / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
        (self.root / ".env").write_text("SECRET", encoding="utf-8")
        self.client = create_app({"TESTING": True, "FRONTEND_DIST": str(self.root)}).test_client()

    def test_dashboard_and_sections(self):
        snapshot = fixture()
        with patch("api.db.load_snapshot", return_value=snapshot):
            self.assertEqual(self.client.get("/api/dashboard").json, snapshot)
            for section in ("quality", "model"):
                response = self.client.get("/api/" + section)
                self.assertEqual(response.json, snapshot[section])
                self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_filters_rejected_without_database_access(self):
        with patch("api.db.load_snapshot") as load:
            for query in ("start=2026-01-01", "end=", "start=bad&end=bad"):
                response = self.client.get("/api/dashboard?" + query)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json["error"]["code"], "DATE_FILTER_UNSUPPORTED")
            self.assertEqual(self.client.get("/api/dashboard?unknown=1").status_code, 400)
            load.assert_not_called()

    def test_database_errors_never_fallback(self):
        for exc, code in ((db.DatabaseUnavailable(), "DATABASE_UNAVAILABLE"),
                          (db.NoResults(), "RESULTS_NOT_IMPORTED"),
                          (db.InvalidStoredResults(), "INVALID_STORED_RESULTS")):
            with patch("api.db.load_snapshot", side_effect=exc):
                response = self.client.get("/api/dashboard")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json["error"]["code"], code)

    def test_health_unavailable(self):
        with patch("api.db.connect", side_effect=db.DatabaseUnavailable("secret password")):
            response = self.client.get("/api/health")
            self.assertEqual(response.status_code, 503)
            self.assertFalse(response.json["ready"])
            self.assertNotIn("secret", response.text)

    def test_static_and_safe_spa(self):
        for path in ("/", "/analysis/stations"):
            with self.client.get(path) as response:
                self.assertEqual(response.status_code, 200)
        with self.client.get("/assets/app.js") as response:
            self.assertIn("console.log", response.text)
        for path in ("/api", "/api/missing", "/assets/missing.js", "/assets/missing", "/missing.css", "/.env", "/%2e%2e/api/.env", "/..%5capi%5c.env"):
            self.assertEqual(self.client.get(path).status_code, 404, path)
        self.assertEqual(self.client.post("/api/dashboard").status_code, 405)

    def test_validate_before_connect(self):
        invalids = []
        value = fixture()
        del value["charts"]["daily"]
        invalids.append(value)
        value = fixture()
        value["charts"]["daily"] = {}
        invalids.append(value)
        value = fixture()
        value["kpis"]["sessions"] = float("nan")
        invalids.append(value)
        with patch("api.db.connect") as connect:
            for value in invalids:
                with self.assertRaises(ValueError):
                    import_snapshot(value)
            connect.assert_not_called()


@unittest.skipUnless(os.getenv("BIGDATA_MYSQL_INTEGRATION") == "1", "Opt-in real MySQL integration")
class MysqlIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        values = dotenv_values(Path(__file__).resolve().parents[1] / "api" / ".env")
        cls.admin = pymysql.connect(host="127.0.0.1", port=3307, user="root", password=values["MYSQL_ADMIN_PASSWORD"], autocommit=True)
        cls.database = "bigdata_api_test_" + uuid.uuid4().hex
        with cls.admin.cursor() as cur:
            cur.execute(f"CREATE DATABASE `{cls.database}` CHARACTER SET utf8mb4")
        cls.env = patch.dict(os.environ, {"MYSQL_HOST": "127.0.0.1", "MYSQL_PORT": "3307", "MYSQL_USER": "root", "MYSQL_PASSWORD": values["MYSQL_ADMIN_PASSWORD"], "MYSQL_DATABASE": cls.database})
        cls.env.start()
        cls.client = create_app({"TESTING": True}).test_client()

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        # Exact random test database created by this class, never the app database.
        with cls.admin.cursor() as cur:
            cur.execute(f"DROP DATABASE `{cls.database}`")
        cls.admin.close()

    def test_01_empty_schema(self):
        with db.connect() as conn:
            db.initialize_schema(conn)
        self.assertEqual(self.client.get("/api/dashboard").json["error"]["code"], "RESULTS_NOT_IMPORTED")
        self.assertEqual(self.client.get("/api/health").status_code, 503)

    def test_02_roundtrip_and_version_switch(self):
        original = fixture()
        first = import_snapshot(original)
        self.assertEqual(self.client.get("/api/dashboard").json, original)
        updated = copy.deepcopy(original)
        updated["meta"]["run"] = 2
        updated["charts"]["daily"] = []
        second = import_snapshot(updated)
        self.assertNotEqual(first, second)
        self.assertEqual(self.client.get("/api/dashboard").json, updated)
        self.assertEqual(self.client.get("/api/quality").json, updated["quality"])
        self.assertEqual(self.client.get("/api/model").json, updated["model"])
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json["run_id"], second)
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM dashboard_runs")
                self.assertEqual(cur.fetchone()["n"], 2)
                cur.execute("SELECT COUNT(*) AS n FROM dashboard_charts")
                self.assertEqual(cur.fetchone()["n"], 24)

    def test_03_failed_chart_insert_rolls_back(self):
        previous = db.load_snapshot()
        with patch.object(pymysql.cursors.DictCursor, "executemany", side_effect=pymysql.OperationalError(1644, "injected failure")):
            with self.assertRaises(db.DatabaseUnavailable):
                import_snapshot(fixture())
        self.assertEqual(db.load_snapshot(), previous)
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM dashboard_runs")
                self.assertEqual(cur.fetchone()["n"], 2)


if __name__ == "__main__":
    unittest.main()
