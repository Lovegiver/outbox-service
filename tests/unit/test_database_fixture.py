from sqlalchemy import text

def test_db_session_uses_test_database(db_session):
    current_database = db_session.execute(
        text("SELECT current_database()")
    ).scalar_one()

    assert current_database == "outbox_test"