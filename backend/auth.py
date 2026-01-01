import os
from functools import wraps

from flask import session, redirect, url_for, flash, request
from passlib.hash import bcrypt
from sqlalchemy.exc import OperationalError

from backend.models import User
from backend.db import db


def is_logged_in() -> bool:
    return bool(session.get("user_id"))


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return User.query.get(uid)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_logged_in():
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or not user.is_admin:
            flash("Admin access required.", "danger")
            return redirect(url_for("index"))
        return view(*args, **kwargs)
    return wrapped

def approved_required(view):
    """
    Blocks pending/blocked users from running sensitive actions (like /run).
    Admin is always allowed.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))

        if user.is_admin:
            return view(*args, **kwargs)

        if user.status == "pending":
            flash("Your account is pending approval. Please wait for admin approval.", "warning")
            return redirect(url_for("index"))

        if user.status == "blocked":
            flash("Your account is blocked. Please contact the admin.", "danger")
            return redirect(url_for("index"))

        if user.status != "approved":
            flash("Your account is not approved.", "warning")
            return redirect(url_for("index"))

        return view(*args, **kwargs)
    return wrapped



def create_user(email: str, password: str) -> User:
    email = email.strip().lower()
    if User.query.filter_by(email=email).first():
        raise ValueError("Email already registered.")

    # bcrypt has a 72 byte password limit; enforce it clearly
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password too long. Please keep it under 72 characters.")

    user = User(
        email=email,
        password_hash=bcrypt.hash(password),
        status="pending",
        is_admin=False,
    )
    db.session.add(user)
    db.session.commit()
    return user


def authenticate(email: str, password: str):
    email = email.strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        return None

    if not bcrypt.verify(password, user.password_hash):
        return None

    # pending/blocked users cannot login (admins can)
    if user.status != "approved" and not user.is_admin:
        return "NOT_APPROVED"

    return user


def ensure_admin_seed():
    """
    Creates/ensures an admin user from env vars:
      ADMIN_EMAIL, ADMIN_PASSWORD

    Safe when tables aren't migrated yet.
    """
    try:
        admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        admin_password = os.getenv("ADMIN_PASSWORD", "").strip()

        if not admin_email or not admin_password:
            return

        # bcrypt has a 72 byte password limit
        if len(admin_password.encode("utf-8")) > 72:
            # Don't crash the app; just skip seeding
            return

        user = User.query.filter_by(email=admin_email).first()
        if user:
            if not user.is_admin or user.status != "approved":
                user.is_admin = True
                user.status = "approved"
                db.session.commit()
            return

        admin = User(
            email=admin_email,
            password_hash=bcrypt.hash(admin_password),
            status="approved",
            is_admin=True,
        )
        db.session.add(admin)
        db.session.commit()

    except OperationalError:
        # users table doesn't exist yet (migrations not applied)
        return
