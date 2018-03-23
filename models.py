import os

from sqlalchemy import create_engine, Column, Integer, String, Unicode
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine(os.environ.get('DATABASE_URL'), echo=False)
Base = declarative_base(bind=engine)


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)

    twitter_screen_name = Column(String)
    pledge_amount = Column(Integer)
    stripe_token = Column(String)
    stripe_customer_id = Column(String)
    email = Column(Unicode)
    twitter_token = Column(String)
    twitter_uid = Column(String)
    twitter_photo = Column(Unicode)
    mattress_vote = Column(Integer)
    name = Column(Unicode)
    city = Column(Unicode)
    state = Column(Unicode)
    address = Column(Unicode)
    zip_code = Column(Unicode)
    country = Column(Unicode)

    def __repr__(self):
        return "<User(twitter_screen_name='%s')>" % self.twitter_screen_name
