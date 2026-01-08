#!/usr/bin/env python3
"""
ORM models for multi-user settings, jobs, bids, events, and queue items
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Hashed password
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    settings: Mapped['UserSettings'] = relationship('UserSettings', back_populates='user', uselist=False)


class UserSettings(Base):
    __tablename__ = 'user_settings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), unique=True)

    categories: Mapped[str] = mapped_column(Text, default='["web"]')
    keywords: Mapped[str] = mapped_column(Text, default='')
    interval: Mapped[int] = mapped_column(Integer, default=60)
    past_time: Mapped[int] = mapped_column(Integer, default=24)
    notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    sound_alert: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_bid: Mapped[bool] = mapped_column(Boolean, default=False)
    chatgpt_api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_skills: Mapped[str] = mapped_column(Text, default='')
    min_suitability_score: Mapped[int] = mapped_column(Integer, default=70)
    bid_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    custom_prompts: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    selected_model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_jobs: Mapped[int] = mapped_column(Integer, default=50)  # Maximum number of jobs to display
    
    # Notification settings
    discord_webhook: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    telegram_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped['User'] = relationship('User', back_populates='settings')


class Job(Base):
    __tablename__ = 'jobs'
    __table_args__ = (
        UniqueConstraint('external_id', name='uq_jobs_external_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    original_description: Mapped[Optional[str]] = mapped_column(Text)
    link: Mapped[str] = mapped_column(Text)
    client: Mapped[Optional[str]] = mapped_column(String(255))
    client_username: Mapped[Optional[str]] = mapped_column(String(255))
    client_display_name: Mapped[Optional[str]] = mapped_column(String(255))
    avatar: Mapped[Optional[str]] = mapped_column(Text)
    employer_id: Mapped[Optional[str]] = mapped_column(String(64))
    employer_contracts_count: Mapped[Optional[int]] = mapped_column(Integer)
    employer_completed_count: Mapped[Optional[int]] = mapped_column(Integer)
    employer_last_activity: Mapped[Optional[int]] = mapped_column(Integer)  # minutes ago (stored in minutes for accurate unit preservation)
    category: Mapped[Optional[str]] = mapped_column(String(64))
    posted_at: Mapped[Optional[str]] = mapped_column(String(64))
    posted_time_formatted: Mapped[Optional[str]] = mapped_column(String(64))
    posted_time_relative: Mapped[Optional[str]] = mapped_column(String(64))
    job_price_type: Mapped[Optional[str]] = mapped_column(String(64))
    job_price_amount: Mapped[Optional[str]] = mapped_column(String(64))
    job_price_currency: Mapped[Optional[str]] = mapped_column(String(16))
    job_price_formatted: Mapped[Optional[str]] = mapped_column(String(128))
    budget_info_json: Mapped[Optional[str]] = mapped_column(Text)
    keywords: Mapped[Optional[str]] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    bid_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    bid_content: Mapped[Optional[str]] = mapped_column(Text)
    bid_generated_by: Mapped[Optional[str]] = mapped_column(String(64))
    bid_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_bid_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    suitability_score: Mapped[Optional[int]] = mapped_column(Integer)

    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Bid(Base):
    __tablename__ = 'bids'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey('jobs.id'))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    content: Mapped[str] = mapped_column(Text)
    generated_by: Mapped[Optional[str]] = mapped_column(String(64))
    model: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QueueItem(Base):
    __tablename__ = 'queue_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey('jobs.id'), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(64))  # analyze, generate_bid, submit_bid
    status: Mapped[str] = mapped_column(String(32), default='pending')  # pending, processing, done, failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FavoriteClient(Base):
    __tablename__ = 'favorite_clients'
    __table_args__ = (
        UniqueConstraint('user_id', 'employer_id', name='uq_favorite_client_user_employer'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    employer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    employer_name: Mapped[Optional[str]] = mapped_column(String(255))
    employer_display_name: Mapped[Optional[str]] = mapped_column(String(255))
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    profile_url: Mapped[Optional[str]] = mapped_column(Text)
    
    # Status fields (updated by background task)
    last_activity_hours: Mapped[Optional[int]] = mapped_column(Integer)  # minutes ago (stored in minutes for accurate unit preservation)
    contracts_count: Mapped[Optional[int]] = mapped_column(Integer)
    completed_count: Mapped[Optional[int]] = mapped_column(Integer)
    last_status_update: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)



class BlockedUser(Base):
    __tablename__ = 'blocked_users'
    __table_args__ = (
        UniqueConstraint('user_id', 'employer_id', name='uq_blocked_user_user_employer'),
        UniqueConstraint('user_id', 'client_username', name='uq_blocked_user_user_username'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    employer_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    client_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    employer_name: Mapped[Optional[str]] = mapped_column(String(255))
    employer_display_name: Mapped[Optional[str]] = mapped_column(String(255))
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    profile_url: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
