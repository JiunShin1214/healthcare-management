from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.user import UserCreate


def test_user_create_accepts_valid_gender_and_birth_date():
    user = UserCreate(
        email="valid@example.com",
        password="TestPassword123!",
        name="Valid User",
        birth_date=date(2000, 1, 1),
        gender="male",
    )

    assert user.gender == "male"
    assert user.birth_date == date(2000, 1, 1)


def test_user_create_rejects_invalid_gender():
    with pytest.raises(ValidationError):
        UserCreate(
            email="invalid-gender@example.com",
            password="TestPassword123!",
            name="Invalid Gender",
            birth_date=date(2000, 1, 1),
            gender="other",
        )


def test_user_create_rejects_future_birth_date():
    with pytest.raises(ValidationError):
        UserCreate(
            email="future@example.com",
            password="TestPassword123!",
            name="Future User",
            birth_date=date.today() + timedelta(days=1),
            gender="female",
        )
