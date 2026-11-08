"""Login, roles (RBAC), admin accounts and temporary passwords."""


def test_login_and_wrong_password(client, audit):
    assert client.post("/auth/login", json={"username": "chv1", "password": "wrong"}).status_code == 401
    assert client.post("/auth/login", json={"username": "nobody", "password": "wrong"}).status_code == 401
    res = client.post("/auth/login", json={"username": "chv1", "password": "Demo@1234"})
    assert res.status_code == 200 and res.json()["user"]["role"] == "chv"
    assert audit()[-3:] == ["login_failed", "login_failed", "login"]


def test_token_required_and_role_checked(client, login):
    assert client.get("/patients").status_code in (401, 403)  # no token
    assert client.get("/patients", headers={"Authorization": "Bearer fake"}).status_code == 401
    assert client.get("/patients", headers=login("nurse1")).status_code == 403  # wrong role
    assert client.get("/surveillance/summary", headers=login("chv1")).status_code == 403
    assert client.get("/admin/users", headers=login("ghs1")).status_code == 403


def test_admin_list_has_no_secrets(client, login):
    data = client.get("/admin/users", headers=login("admin1")).json()
    assert len(data["users"]) == 8
    assert all("password_hash" not in u for u in data["users"])


def create(client, admin, **extra):
    body = {"username": "nurse_new", "full_name": "Fake Nurse", "role": "nurse", "facility": "Test Health Centre", **extra}
    return client.post("/admin/users", headers=admin, json=body)


def test_admin_create_validation(client, login):
    admin = login("admin1")
    assert create(client, admin).status_code == 200
    assert create(client, admin).status_code == 409  # username taken
    assert create(client, admin, username="Bad Name!").status_code == 422
    assert create(client, admin, username="chv_x", role="chv", facility="").status_code == 422  # CHV needs facility
    assert create(client, admin, username="ghs_x", role="ghs", district="Atlantis").status_code == 422


def test_temporary_password_must_be_changed(client, login):
    temp = create(client, login("admin1")).json()["temporary_password"]
    nurse = login("nurse_new", temp)
    # The server blocks everything except "who am I" and "change password"
    assert client.get("/referrals", headers=nurse).status_code == 403
    assert client.get("/calls/active", headers=nurse).status_code == 403
    assert client.get("/auth/me", headers=nurse).status_code == 200

    def change(current, new):
        return client.post("/auth/change-password", headers=nurse, json={"current_password": current, "new_password": new})

    assert change(temp, "short1").status_code == 422  # under 8 characters
    assert change(temp, "abcdefghij").status_code == 422  # no number
    assert change(temp, "nurse_new123").status_code == 422  # contains username
    assert change("wrong", "Goodpass2026").status_code == 400
    assert change(temp, "Goodpass2026").status_code == 200
    assert client.get("/referrals", headers=nurse).status_code == 200  # unlocked
    assert client.post("/auth/login", json={"username": "nurse_new", "password": temp}).status_code == 401


def test_disable_locks_out_at_once(client, login, audit):
    admin = login("admin1")
    chv = login("chv1")
    users = client.get("/admin/users", headers=admin).json()["users"]
    chv_id = next(u["id"] for u in users if u["username"] == "chv1")
    admin_id = next(u["id"] for u in users if u["username"] == "admin1")

    assert client.post(f"/admin/users/{chv_id}/active", headers=admin, json={"active": False}).status_code == 200
    assert client.get("/patients", headers=chv).status_code == 401  # old token stops working
    assert client.post("/auth/login", json={"username": "chv1", "password": "Demo@1234"}).status_code == 403
    assert client.post(f"/admin/users/{admin_id}/active", headers=admin, json={"active": False}).status_code == 400
    assert client.post(f"/admin/users/{chv_id}/active", headers=admin, json={"active": True}).status_code == 200
    assert client.get("/patients", headers=login("chv1")).status_code == 200
    assert {"disable_user", "login_disabled", "enable_user"} <= set(audit())


def test_admin_reset_password(client, login):
    admin = login("admin1")
    users = client.get("/admin/users", headers=admin).json()["users"]
    chv_id = next(u["id"] for u in users if u["username"] == "chv1")
    temp = client.post(f"/admin/users/{chv_id}/reset-password", headers=admin).json()["temporary_password"]
    assert client.post("/auth/login", json={"username": "chv1", "password": "Demo@1234"}).status_code == 401
    res = client.post("/auth/login", json={"username": "chv1", "password": temp})
    assert res.json()["user"]["must_change_password"] is True
