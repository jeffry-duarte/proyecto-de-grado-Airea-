import os
import tempfile
import unittest
from pathlib import Path


_test_directory = tempfile.TemporaryDirectory(prefix="airea-auth-tests-")
_test_database = Path(_test_directory.name) / "test.sqlite"
os.environ["AIREA_TEST_MODE"] = "1"
os.environ["AIREA_TEST_DATABASE_URL"] = (
    f"sqlite:///{_test_database.as_posix()}"
)
os.environ["AIREA_ADMIN_SETUP_TOKEN"] = "test-admin-setup-token"
os.environ["AIREA_PUBLIC_ORIGIN"] = "https://testserver"
os.environ["AIREA_JWT_SECRET"] = "test-secret-with-at-least-32-bytes-long"
os.environ["NODE_ENV"] = "production"

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import text

from core.security import hash_scrypt_password
from db.database import create_database_engine, initialize_database
from main import app


class AuthenticationMigrationTests(unittest.TestCase):
    def test_bcrypt_jwt_rbac_and_legacy_password_upgrade(self):
        origin = {"Origin": "https://testserver"}
        with TestClient(app, base_url="https://testserver") as client:
            admin = client.post(
                "/api/auth/bootstrap-admin",
                headers=origin,
                json={
                    "name": "Admin Example",
                    "email": "admin@example.com",
                    "password": "A-secure-test-password",
                    "locality": "Kennedy",
                    "favoriteStationId": "RMCAB-BOG-16",
                    "healthProfile": "general",
                    "notificationsEnabled": True,
                    "setupToken": "test-admin-setup-token",
                },
            )
            self.assertEqual(admin.status_code, 201, admin.text)

            with app.state.database_engine.connect() as connection:
                initial_hash = connection.execute(
                    text("""
                        SELECT password_hash, password_scheme FROM users
                        WHERE email = 'admin@example.com'
                    """)
                ).mappings().one()
            self.assertEqual(initial_hash["password_scheme"], "bcrypt")
            self.assertTrue(initial_hash["password_hash"].startswith("$2"))

            with app.state.database_engine.begin() as connection:
                connection.execute(
                    text("""
                        UPDATE users SET password_salt = :salt,
                            password_hash = :password_hash,
                            password_scheme = 'scrypt'
                        WHERE email = 'admin@example.com'
                    """),
                    dict(
                        zip(
                            ("salt", "password_hash"),
                            hash_scrypt_password("A-secure-test-password"),
                        )
                    ),
                )

            login = client.post(
                "/login",
                headers=origin,
                json={
                    "email": "admin@example.com",
                    "password": "A-secure-test-password",
                },
            )
            self.assertEqual(login.status_code, 200, login.text)
            claims = jwt.decode(
                client.cookies.get("airea_session"),
                os.environ["AIREA_JWT_SECRET"],
                algorithms=["HS256"],
            )
            self.assertEqual(claims["role"], "admin")
            with app.state.database_engine.connect() as connection:
                password_row = connection.execute(
                    text("""
                        SELECT password_hash, password_scheme FROM users
                        WHERE email = 'admin@example.com'
                    """)
                ).mappings().one()
            self.assertEqual(password_row["password_scheme"], "bcrypt")
            self.assertTrue(password_row["password_hash"].startswith("$2"))
            self.assertEqual(
                client.get("/api/admin/dashboard").status_code, 200
            )

            saved_token = client.cookies.get("airea_session")
            client.cookies.clear()
            client.cookies.set(
                "airea_session",
                saved_token + "invalid",
                domain="testserver",
                path="/",
            )
            self.assertEqual(
                client.get("/api/admin/dashboard").status_code, 401
            )
            client.cookies.clear()
            login = client.post(
                "/login",
                headers=origin,
                json={
                    "email": "admin@example.com",
                    "password": "A-secure-test-password",
                },
            )
            self.assertEqual(login.status_code, 200, login.text)

            citizen = client.post(
                "/api/auth/register",
                headers=origin,
                json={
                    "name": "Citizen Example",
                    "email": "citizen@example.com",
                    "password": "Another-secure-password",
                    "locality": "Suba",
                    "favoriteStationId": "RMCAB-BOG-08",
                    "healthProfile": "general",
                    "notificationsEnabled": True,
                },
            )
            self.assertEqual(citizen.status_code, 201, citizen.text)
            self.assertEqual(
                client.get("/api/admin/dashboard").status_code, 403
            )

    def test_alembic_migration_preserves_existing_user_and_role(self):
        with tempfile.TemporaryDirectory(prefix="airea-legacy-user-") as directory:
            database_url = (
                f"sqlite:///{(Path(directory) / 'legacy.sqlite').as_posix()}"
            )
            engine = create_database_engine(database_url)
            salt, password_hash = hash_scrypt_password("legacy-password")
            try:
                with engine.begin() as connection:
                    connection.exec_driver_sql("""
                        CREATE TABLE users (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            email TEXT NOT NULL UNIQUE,
                            password_salt TEXT NOT NULL,
                            password_hash TEXT NOT NULL,
                            locality TEXT NOT NULL,
                            favorite_station_id TEXT NOT NULL,
                            health_profile TEXT NOT NULL,
                            notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                            role TEXT NOT NULL DEFAULT 'citizen',
                            created_at TIMESTAMP WITH TIME ZONE NOT NULL
                        )
                    """)
                    connection.execute(
                        text("""
                            INSERT INTO users (
                                id, name, email, password_salt, password_hash,
                                locality, favorite_station_id, health_profile,
                                notifications_enabled, role, created_at
                            ) VALUES (
                                'legacy-user', 'Legacy Admin', 'legacy@example.com',
                                :salt, :password_hash, 'Kennedy', 'RMCAB-BOG-16',
                                'general', TRUE, 'admin', '2026-01-01T00:00:00'
                            )
                        """),
                        {"salt": salt, "password_hash": password_hash},
                    )

                initialize_database(engine)

                with engine.connect() as connection:
                    migrated = connection.execute(
                        text("""
                            SELECT users.password_hash, users.password_salt,
                                users.password_scheme, roles.name AS role
                            FROM users JOIN roles ON roles.id = users.role_id
                            WHERE users.id = 'legacy-user'
                        """)
                    ).mappings().one()
                self.assertEqual(migrated["password_hash"], password_hash)
                self.assertEqual(migrated["password_salt"], salt)
                self.assertEqual(migrated["password_scheme"], "scrypt")
                self.assertEqual(migrated["role"], "admin")
            finally:
                engine.dispose()

    @classmethod
    def tearDownClass(cls):
        _test_directory.cleanup()


if __name__ == "__main__":
    unittest.main()
