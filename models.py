# models.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    weight = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    age = Column(Integer, nullable=True)
    activity = Column(Integer, nullable=True)
    city = Column(String, nullable=True)
    calorie_goal = Column(Float, nullable=True)
    sex = Column(String, nullable=True)  # Добавим пол пользователя

    logged_water = relationship("WaterLog", back_populates="user")
    logged_food = relationship("FoodLog", back_populates="user")
    logged_workouts = relationship("WorkoutLog", back_populates="user")


class WaterLog(Base):
    __tablename__ = "water_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    amount = Column(Float)  # в мл
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="logged_water")


class FoodLog(Base):
    __tablename__ = "food_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    product_name = Column(String)
    amount = Column(Float)  # в граммах
    calories = Column(Float)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="logged_food")


class WorkoutLog(Base):
    __tablename__ = "workout_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    workout_type = Column(String)
    duration = Column(Integer)  # в минутах
    calories_burned = Column(Float)
    water_consumed = Column(Float)  # дополнительная вода
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="logged_workouts")
