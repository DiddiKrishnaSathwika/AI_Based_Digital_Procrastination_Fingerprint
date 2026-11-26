
if __package__:
    from .app import app, init_db
else:
    from app import app, init_db

init_db()
