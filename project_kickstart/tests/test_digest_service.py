from types import SimpleNamespace
from unittest.mock import patch

from app import crud
from app.services import auth_service, digest_service


def test_apply_weapon_filter_returns_matching_events():
    registrations = [
        SimpleNamespace(events="Junior Women's Foil"),
        SimpleNamespace(events="Cadet Men's Saber"),
    ]

    filtered = digest_service.apply_weapon_filter(registrations, "foil")

    assert len(filtered) == 1
    assert filtered[0].events == "Junior Women's Foil"


def test_send_user_digest_skips_when_no_registrations(db_session):
    password_hash = auth_service.hash_password("password123")
    user = crud.create_user(db_session, "tester", "tester@example.com", password_hash)
    crud.create_tracked_club(
        db_session,
        user_id=user.id,
        club_url="https://fencingtracker.com/club/1/Example/registrations",
        club_name="Example Club",
    )
    db_session.commit()

    with patch("app.services.digest_service.send_registration_notification") as mock_send:
        sent = digest_service.send_user_digest(db_session, user)

    assert sent is False
    mock_send.assert_not_called()


def test_send_user_digest_sends_email(db_session):
    password_hash = auth_service.hash_password("password123")
    user = crud.create_user(db_session, "digest", "digest@example.com", password_hash)
    tracked = crud.create_tracked_club(
        db_session,
        user_id=user.id,
        club_url="https://fencingtracker.com/club/2/Elite/registrations",
        club_name="Elite FC",
        weapon_filter="foil",
    )

    fencer = crud.get_or_create_fencer(db_session, "Jane Doe")
    tournament = crud.get_or_create_tournament(db_session, "Autumn Open", "2025-10-01")
    crud.update_or_create_registration(
        db_session,
        fencer,
        tournament,
        events="Junior Women's Foil",
        club_url=tracked.club_url,
    )
    db_session.commit()

    with patch("app.services.digest_service.send_registration_notification") as mock_send:
        sent = digest_service.send_user_digest(db_session, user)

    assert sent is True
    mock_send.assert_called_once()
    args, kwargs = mock_send.call_args
    assert kwargs["recipients"] == [user.email]


def test_send_user_digest_dedupes_fencer_entries(db_session):
    password_hash = auth_service.hash_password("password123")
    user = crud.create_user(db_session, "dedupe", "dedupe@example.com", password_hash)

    tracked_club = crud.create_tracked_club(
        db_session,
        user_id=user.id,
        club_url="https://fencingtracker.com/club/3/Swords/registrations",
        club_name="Swords Club",
    )
    tracked_fencer = crud.create_tracked_fencer(
        db_session,
        user_id=user.id,
        fencer_id="54321",
        display_name="Alex Foil",
    )

    fencer = crud.get_or_create_fencer(db_session, "Alex Foil")
    fencer.fencingtracker_id = tracked_fencer.fencer_id
    tournament = crud.get_or_create_tournament(db_session, "Winter Classic", "2025-11-01")
    crud.update_or_create_registration(
        db_session,
        fencer,
        tournament,
        events="Senior Women's Foil",
        club_url=tracked_club.club_url,
    )
    db_session.commit()

    with patch("app.services.digest_service.send_registration_notification") as mock_send:
        sent = digest_service.send_user_digest(db_session, user)

    assert sent is True
    mock_send.assert_called_once()
    body = mock_send.call_args.kwargs["body"]
    assert body.count("Senior Women's Foil") == 1
    assert "TRACKED FENCERS" not in body

def test_send_user_digest_with_mixed_weapon_filters(db_session):
    password_hash = auth_service.hash_password("password123")
    user = crud.create_user(db_session, "mixedfilter", "mixedfilter@example.com", password_hash)

    crud.create_tracked_club(
        db_session,
        user_id=user.id,
        club_url="https://fencingtracker.com/club/4/Mixed/registrations",
        club_name="Mixed Club",
        weapon_filter="epee",
    )
    crud.create_tracked_fencer(
        db_session,
        user_id=user.id,
        fencer_id="67890",
        display_name="Alex Saber",
        weapon_filter="saber",
    )

    fencer1 = crud.get_or_create_fencer(db_session, "John Epee")
    fencer2 = crud.get_or_create_fencer(db_session, "Alex Saber")
    fencer2.fencingtracker_id = "67890"
    tournament = crud.get_or_create_tournament(db_session, "State Games", "2025-11-05")
    crud.update_or_create_registration(
        db_session, fencer1, tournament, "Senior Men's Epee", "https://fencingtracker.com/club/4/Mixed/registrations"
    )
    crud.update_or_create_registration(
        db_session, fencer2, tournament, "Senior Men's Saber", "https://fencingtracker.com/p/67890"
    )
    db_session.commit()

    with patch("app.services.digest_service.send_registration_notification") as mock_send:
        digest_service.send_user_digest(db_session, user)

    mock_send.assert_called_once()
    body = mock_send.call_args.kwargs["body"]
    assert "Senior Men's Epee" in body
    assert "Senior Men's Saber" in body
    assert "TRACKED CLUBS" in body
    assert "TRACKED FENCERS" in body

def test_send_user_digest_with_fencer_only(db_session):
    password_hash = auth_service.hash_password("password123")
    user = crud.create_user(db_session, "fenceronly", "fenceronly@example.com", password_hash)
    crud.create_tracked_fencer(
        db_session,
        user_id=user.id,
        fencer_id="11111",
        display_name="Zoe Foil",
    )

    fencer = crud.get_or_create_fencer(db_session, "Zoe Foil")
    fencer.fencingtracker_id = "11111"
    tournament = crud.get_or_create_tournament(db_session, "National Champs", "2025-12-01")
    crud.update_or_create_registration(
        db_session, fencer, tournament, "Div 1 Women's Foil", "https://fencingtracker.com/p/11111"
    )
    db_session.commit()

    with patch("app.services.digest_service.send_registration_notification") as mock_send:
        digest_service.send_user_digest(db_session, user)

    mock_send.assert_called_once()
    body = mock_send.call_args.kwargs["body"]
    assert "TRACKED CLUBS" not in body
    assert "TRACKED FENCERS" in body
    assert "Div 1 Women's Foil" in body

