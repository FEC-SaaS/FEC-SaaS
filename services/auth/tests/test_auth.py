"""Tests for authentication endpoints."""
import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client: TestClient):
        """Test health endpoint returns healthy status."""
        response = client.get("/api/v1/auth/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data


class TestRegistration:
    """Test user registration endpoints."""

    def test_register_success(self, client: TestClient, test_user_data: dict):
        """Test successful user registration."""
        response = client.post("/api/v1/auth/register", json=test_user_data)
        assert response.status_code == 201
        data = response.json()

        # Check user data
        assert data["user"]["email"] == test_user_data["email"]
        assert data["user"]["first_name"] == test_user_data["first_name"]
        assert data["user"]["last_name"] == test_user_data["last_name"]
        assert data["user"]["email_verified"] is False

        # Check tokens
        assert "access_token" in data["tokens"]
        assert "refresh_token" in data["tokens"]
        assert data["tokens"]["token_type"] == "bearer"

    def test_register_duplicate_email(self, client: TestClient, test_user_data: dict):
        """Test registration fails with duplicate email."""
        # First registration
        client.post("/api/v1/auth/register", json=test_user_data)

        # Duplicate registration
        response = client.post("/api/v1/auth/register", json=test_user_data)
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_register_invalid_email(self, client: TestClient):
        """Test registration fails with invalid email."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "SecurePass123",
            },
        )
        assert response.status_code == 422


class TestLogin:
    """Test login endpoints."""

    def test_login_success(self, client: TestClient, test_user_data: dict):
        """Test successful login."""
        # Register first
        client.post("/api/v1/auth/register", json=test_user_data)

        # Login
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["user"]["email"] == test_user_data["email"]
        assert "access_token" in data["tokens"]
        assert "refresh_token" in data["tokens"]

    def test_login_wrong_password(self, client: TestClient, test_user_data: dict):
        """Test login fails with wrong password."""
        # Register first
        client.post("/api/v1/auth/register", json=test_user_data)

        # Login with wrong password
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": "WrongPassword123",
            },
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self, client: TestClient):
        """Test login fails for non-existent user."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "SomePassword123",
            },
        )
        assert response.status_code == 401


class TestCurrentUser:
    """Test current user endpoints."""

    def test_get_current_user(self, client: TestClient, auth_headers: dict):
        """Test get current user profile."""
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert "id" in data

    def test_get_current_user_no_auth(self, client: TestClient):
        """Test get current user fails without auth."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_update_current_user(self, client: TestClient, auth_headers: dict):
        """Test update current user profile."""
        response = client.put(
            "/api/v1/auth/me",
            headers=auth_headers,
            json={"first_name": "Updated", "last_name": "Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert data["last_name"] == "Name"


class TestTokenRefresh:
    """Test token refresh endpoints."""

    def test_refresh_token(self, client: TestClient, registered_user: dict):
        """Test token refresh."""
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": registered_user["tokens"]["refresh_token"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_invalid_token(self, client: TestClient):
        """Test refresh fails with invalid token."""
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 401


class TestLogout:
    """Test logout endpoints."""

    def test_logout(self, client: TestClient, registered_user: dict):
        """Test logout invalidates session."""
        response = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": registered_user["tokens"]["refresh_token"]},
        )
        assert response.status_code == 204

        # Verify refresh token is now invalid
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": registered_user["tokens"]["refresh_token"]},
        )
        assert response.status_code == 401


class TestPasswordReset:
    """Test password reset flow."""

    def test_forgot_password(self, client: TestClient, test_user_data: dict):
        """Test forgot password request."""
        # Register first
        client.post("/api/v1/auth/register", json=test_user_data)

        # Request password reset
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": test_user_data["email"]},
        )
        assert response.status_code == 200
        # Should always return success to prevent email enumeration
        assert response.json()["success"] is True

    def test_forgot_password_nonexistent(self, client: TestClient):
        """Test forgot password for non-existent email."""
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nonexistent@example.com"},
        )
        # Should still return 200 to prevent enumeration
        assert response.status_code == 200


class TestChangePassword:
    """Test change password endpoint."""

    def test_change_password(self, client: TestClient, auth_headers: dict, test_user_data: dict):
        """Test change password for authenticated user."""
        response = client.post(
            "/api/v1/auth/change-password",
            headers=auth_headers,
            json={
                "current_password": test_user_data["password"],
                "new_password": "NewSecurePass123",
            },
        )
        assert response.status_code == 204

    def test_change_password_wrong_current(self, client: TestClient, auth_headers: dict):
        """Test change password fails with wrong current password."""
        response = client.post(
            "/api/v1/auth/change-password",
            headers=auth_headers,
            json={
                "current_password": "WrongPassword123",
                "new_password": "NewSecurePass123",
            },
        )
        assert response.status_code == 400
