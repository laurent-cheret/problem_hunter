from datetime import datetime, date, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    DateTime, Date, UniqueConstraint, ForeignKey
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Tweet(Base):
    """A tweet fetched from a monitored account."""
    __tablename__ = "tweets"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    tweet_id       = Column(String(64), unique=True, nullable=False, index=True)
    author_name    = Column(String(128), nullable=False)
    author_username= Column(String(64), nullable=False, index=True)
    text           = Column(Text, nullable=False)
    tweet_url      = Column(String(512))
    created_at     = Column(DateTime, nullable=False)
    fetched_at     = Column(DateTime, default=datetime.utcnow)

    # Pre-filter result
    passed_keyword_filter = Column(Boolean, default=False)

    # Haiku classification
    problem_score    = Column(Float, nullable=True)   # 0-10
    problem_summary  = Column(Text, nullable=True)    # Short description of the problem
    is_buildable     = Column(Boolean, nullable=True) # Is it technically buildable?
    classified_at    = Column(DateTime, nullable=True)

    # Downstream status
    status = Column(
        String(32), default="pending",
        # pending → classified → researching → report_generated → skipped
    )

    problem = relationship("Problem", back_populates="tweet", uselist=False)

    def __repr__(self) -> str:
        return f"<Tweet @{self.author_username}: {self.text[:60]}...>"


class Problem(Base):
    """A validated problem extracted from a tweet, ready for a full report."""
    __tablename__ = "problems"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    tweet_id_fk     = Column(Integer, ForeignKey("tweets.id"), unique=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    # Research output
    problem_title       = Column(String(256))
    why_it_matters      = Column(Text)          # Brief validated summary
    existing_solutions  = Column(Text)          # What exists, why it's insufficient
    market_signals      = Column(Text)          # Web search snippets / evidence
    viability_score     = Column(Float)         # 0-10, gates Sonnet report
    researched_at       = Column(DateTime)

    # Full Sonnet report
    report_markdown     = Column(Text, nullable=True)
    report_generated_at = Column(DateTime, nullable=True)

    # Telegram delivery
    telegram_sent       = Column(Boolean, default=False)
    telegram_sent_at    = Column(DateTime, nullable=True)

    tweet = relationship("Tweet", back_populates="problem")

    def __repr__(self) -> str:
        return f"<Problem: {self.problem_title}>"


class DailyQuota(Base):
    """Tracks daily Sonnet report generation to enforce MAX_DAILY_REPORTS."""
    __tablename__ = "daily_quotas"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    quota_date       = Column(Date, unique=True, nullable=False, default=date.today)
    reports_generated = Column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<DailyQuota {self.quota_date}: {self.reports_generated} reports>"


class AppSettings(Base):
    """Key-value store for persistent settings (e.g., Twitter cookies)."""
    __tablename__ = "app_settings"

    key   = Column(String(128), primary_key=True)
    value = Column(Text, nullable=False)
