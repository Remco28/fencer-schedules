from app import crud
from app.services import auth_service


def test_create_update_and_deactivate_tracked_club(db_session):
    password_hash = auth_service.hash_password("password123")
    user = crud.create_user(db_session, "clubber", "club@example.com", password_hash)

    club = crud.create_tracked_club(
        db_session,
        user_id=user.id,
        club_url="https://fencingtracker.com/club/10/Foil/registrations",
        club_name="Foil Club",
        weapon_filter="foil,epee",
    )
    db_session.commit()

    fetched = crud.get_tracked_club_by_user_and_url(db_session, user.id, club.club_url)
    assert fetched is not None
    assert fetched.active is True

    crud.update_tracked_club(db_session, club.id, weapon_filter="saber")
    db_session.commit()

    assert crud.get_tracked_club_by_id(db_session, club.id).weapon_filter == "saber"

    crud.deactivate_tracked_club(db_session, club.id)
    db_session.commit()

    assert crud.get_tracked_club_by_id(db_session, club.id).active is False
