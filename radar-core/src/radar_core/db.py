from sqlalchemy import Engine
from sqlmodel import Session, create_engine


def get_engine(database_url: str) -> Engine:
    return create_engine(database_url)


def get_session(engine: Engine) -> Session:
    return Session(engine)
