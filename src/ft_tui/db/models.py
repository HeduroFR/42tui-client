"""SQLAlchemy models for the local-first application database."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from ft_tui.services.project_kind import project_kind


class Base(DeclarativeBase):
    """Declarative base for all persisted entities."""


class Project(Base):
    """A project in the curriculum and its local development checkout."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    official_project_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)
    slug: Mapped[str] = mapped_column(String(256), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    setup_status: Mapped[str] = mapped_column(String(32), default="available")
    dev_repo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    subject_pdf_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    subject_pdf_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject_reference_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    time_logs: Mapped[list["TimeLog"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    activity_heartbeats: Mapped[list["ActivityHeartbeat"]] = relationship(
        back_populates="project", foreign_keys="ActivityHeartbeat.project_id", cascade="all, delete-orphan"
    )
    notes: Mapped[list["DevNote"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    cursus_memberships: Mapped[list["ProjectCursus"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    @property
    def catalog_data(self):
        data = getattr(self, "_catalog_data", {})
        if not isinstance(data.get('kind'), str):
            return data
        kind = project_kind(data['kind'], data.get('slug') or self.slug or '')
        return {**data, 'kind': kind} if kind != data['kind'] else data

    @property
    def progress_data(self):
        return getattr(self, "_progress_data", {})

    @property
    def status(self):
        raw = self.progress_data.get("status")
        if raw == "finished":
            return "completed" if self.validated is True else "failed"
        if raw in {"in_progress", "searching_a_group", "creating_group", "waiting_for_correction", "waiting_to_start"}:
            return "in_progress"
        return raw or self.setup_status or "unknown"

    @status.setter
    def status(self, value):
        self.setup_status = value

    @property
    def validated(self):
        return self.progress_data.get("validated")

    @validated.setter
    def validated(self, value):
        self._progress_data = {**self.progress_data, "validated": value}

    @property
    def last_defense_score(self):
        return self.progress_data.get("final_mark")

    @last_defense_score.setter
    def last_defense_score(self, value):
        self._progress_data = {**self.progress_data, "final_mark": value}

    @property
    def vogsphere_url(self):
        return self.progress_data.get("vogsphere_url")

    @vogsphere_url.setter
    def vogsphere_url(self, value):
        self._progress_data = {**self.progress_data, "vogsphere_url": value}

    @property
    def completed_at(self):
        return None

    @property
    def blackhole_date(self):
        return None

    @property
    def ui_key(self):
        return str(self.official_project_id) if self.official_project_id is not None else f"local:{self.id}"


class Cursus(Base):
    """A cursus membership cached from the centralized API."""

    __tablename__ = "cursuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    begin_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    project_memberships: Mapped[list["ProjectCursus"]] = relationship(
        back_populates="cursus", cascade="all, delete-orphan"
    )


class ProjectCursus(Base):
    """A cached membership linking one singular local project to a cursus."""

    __tablename__ = "project_cursuses"
    __table_args__ = (UniqueConstraint("project_id", "cursus_id", name="uq_project_cursus"),)

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    cursus_id: Mapped[int] = mapped_column(ForeignKey("cursuses.id", ondelete="CASCADE"), primary_key=True)
    project: Mapped[Project] = relationship(back_populates="cursus_memberships")
    cursus: Mapped[Cursus] = relationship(back_populates="project_memberships")


class TimeLog(Base):
    """A manual or automatic work session associated with a project."""

    __tablename__ = "time_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Elapsed seconds")
    project: Mapped[Project] = relationship(back_populates="time_logs")


class ActivityHeartbeat(Base):
    """Editor activity signal; file paths are intentionally never persisted."""

    __tablename__ = "activity_heartbeats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    editor: Mapped[str] = mapped_column(String(100), default="unknown")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    is_write: Mapped[bool] = mapped_column(default=False)
    credited_project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    credited_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    project: Mapped[Project] = relationship(
        back_populates="activity_heartbeats", foreign_keys=[project_id]
    )


class DevNote(Base):
    """Markdown note attached to a project."""

    __tablename__ = "dev_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    project: Mapped[Project] = relationship(back_populates="notes")


class Friend(Base):
    """A locally tracked friend identified by their 42 login."""

    __tablename__ = "friends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    login: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    progress: Mapped[list["FriendProjectProgress"]] = relationship(
        back_populates="friend", cascade="all, delete-orphan"
    )


class FriendProjectProgress(Base):
    """Manual progress note linking a friend to one catalog project."""

    __tablename__ = "friend_project_progress"
    __table_args__ = (UniqueConstraint("friend_id", "project_id", name="uq_friend_project"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    friend_id: Mapped[int] = mapped_column(ForeignKey("friends.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="in_progress")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    friend: Mapped[Friend] = relationship(back_populates="progress")
    project: Mapped[Project] = relationship()


class UserConfig(Base):
    """Key/value preferences stored locally."""

    __tablename__ = "user_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class CatalogCache(Base):
    """Public page/detail cache, keyed by context and immutable snapshot."""
    __tablename__ = "catalog_cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    cursus_id: Mapped[int] = mapped_column(Integer, index=True)
    campus_id: Mapped[int] = mapped_column(Integer, index=True)
    category: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class UserProjectState(Base):
    """Official API progress is private to a specific account."""
    __tablename__ = "user_project_states"
    account_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    official_project_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class AccountCurriculumCache(Base):
    __tablename__ = "account_curriculum_cache"
    account_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    cursus_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campus_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class FriendWatch(Base):
    """Account-owned friend membership; legacy manual records remain untouched."""

    __tablename__ = "friend_watches"
    __table_args__ = (UniqueConstraint("account_id", "login", name="uq_friend_watch"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[str] = mapped_column(String(100), index=True)
    login: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class FriendObservation(Base):
    """Last complete API snapshot, independently scoped by owner and cursus."""

    __tablename__ = "friend_observations"
    __table_args__ = (UniqueConstraint("account_id", "cursus_id", "login", name="uq_friend_observation"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[str] = mapped_column(String(100), index=True)
    cursus_id: Mapped[int] = mapped_column(Integer)
    login: Mapped[str] = mapped_column(String(100))
    data: Mapped[dict] = mapped_column(JSON)
