from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.mysql import LONGTEXT
from app.extensions import db


def utc_now():
    """Mengembalikan datetime UTC naive yang kompatibel dengan kolom DATETIME MySQL."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.Enum("admin", "business_analyst", "marketing", "management", "procurement", name="role_enum"),
        default="business_analyst",
    )
    is_active_flag = db.Column("is_active", db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def is_active(self):
        return self.is_active_flag


class DataSource(db.Model):
    __tablename__ = "data_sources"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    source_type = db.Column(db.Enum("file", "url", "api", "manual", name="source_type_enum"), nullable=False)
    config_json = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utc_now)


class RawData(db.Model):
    __tablename__ = "raw_data"
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey("data_sources.id"))
    source_type = db.Column(db.Enum("file", "url", "api", "manual", name="rd_source_type_enum"), nullable=False)
    original_name = db.Column(db.String(255))
    raw_excerpt = db.Column(db.Text)
    extracted_json = db.Column(db.Text().with_variant(LONGTEXT, "mysql"))
    ai_classification = db.Column(db.String(100))
    column_mapping_json = db.Column(db.Text)
    status = db.Column(
        db.Enum("new", "extracted", "classified", "mapped", "validated", "processed", "error", name="rd_status_enum"),
        default="new",
    )
    error_message = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utc_now)


class Prospect(db.Model):
    """
    KOMPATIBILITAS LAYER:
    Tabel ini dipertahankan khusus untuk backward compatibility modul-modul
    analisis & marketing lama (market_analysis, marketing, reporting).
    Master single source of truth untuk Company Intelligence adalah entitas Organization.
    """
    __tablename__ = "prospects"
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(255), nullable=False)
    industry = db.Column(db.String(150))
    region = db.Column(db.String(150))
    company_size = db.Column(db.String(50))
    website = db.Column(db.String(255))
    contact_name = db.Column(db.String(150))
    contact_email = db.Column(db.String(150))
    contact_phone = db.Column(db.String(50))
    description = db.Column(db.Text)
    segment = db.Column(db.String(100))
    score = db.Column(db.Integer, default=0)
    score_reason = db.Column(db.Text)
    status = db.Column(
        db.Enum("new", "qualified", "contacted", "converted", "rejected", name="prospect_status_enum"),
        default="new",
    )
    raw_data_id = db.Column(db.Integer, db.ForeignKey("raw_data.id"))
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    organization = db.relationship("Organization", backref=db.backref("prospects_legacy", lazy="dynamic"))


class MarketAnalysis(db.Model):
    __tablename__ = "market_analyses"
    id = db.Column(db.Integer, primary_key=True)
    analysis_type = db.Column(
        db.Enum("trend", "industry_distribution", "region_distribution", "company_size",
                "product_recommendation", name="analysis_type_enum"),
        nullable=False,
    )
    title = db.Column(db.String(255))
    result_json = db.Column(db.Text().with_variant(LONGTEXT, "mysql"))
    ai_summary = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utc_now)


class Campaign(db.Model):
    """
    CAMPAIGN ENTITY:
    Pencatatan aktivitas marketing terhadap target tertentu dalam periode tertentu.
    BUKAN CRM: Berfokus pada pengelolaan segmentasi target Master Organizations,
    penentuan produk (Jersey / Custom Teamwear), channel, dan ekspor target.
    """
    __tablename__ = "campaigns"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    product = db.Column(db.String(150), default="Jersey / Custom Teamwear")
    target_segment = db.Column(db.String(150), nullable=True)
    organization_type = db.Column(db.String(100), nullable=True)
    province = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    channel = db.Column(db.String(100), nullable=True)
    segment_filter_json = db.Column(db.Text)
    prospect_count = db.Column(db.Integer, default=0)
    status = db.Column(
        db.Enum("draft", "ready", "exported", "active", "completed", "closed", name="campaign_status_enum"),
        default="draft"
    )
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    owner = db.relationship("User", foreign_keys=[created_by])
    targets = db.relationship("CampaignTarget", back_populates="campaign", cascade="all, delete-orphan")

    @property
    def campaign_name(self):
        return self.name

    @campaign_name.setter
    def campaign_name(self, value):
        self.name = value

    @property
    def target_count(self):
        cnt = len(self.targets) if self.targets else 0
        return cnt if cnt > 0 else (self.prospect_count or 0)


class CampaignTarget(db.Model):
    """
    CAMPAIGN TARGET ENTITY:
    Menghubungkan Campaign Marketing dengan entitas Master Organization.
    Menyimpan snapshot intelijen (Product Fit, Opportunity Score) dan status tindak lanjut.
    """
    __tablename__ = "campaign_targets"
    __table_args__ = (
        db.UniqueConstraint("campaign_id", "organization_id", name="uq_campaign_target_org"),
    )

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    product_fit_snapshot = db.Column(db.String(255), nullable=True)
    opportunity_score_snapshot = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default="targeted")
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)

    campaign = db.relationship("Campaign", back_populates="targets")
    organization = db.relationship("Organization", back_populates="campaign_targets")


class Report(db.Model):
    __tablename__ = "reports"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))
    report_type = db.Column(db.String(100))
    content_json = db.Column(db.Text().with_variant(LONGTEXT, "mysql"))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utc_now)


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(150))
    detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utc_now)


class CronJob(db.Model):
    __tablename__ = "cron_jobs"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    task_type = db.Column(db.String(100))
    schedule_cron = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime, nullable=True)
    last_status = db.Column(db.String(255))
    duration_seconds = db.Column(db.Float, nullable=True)
    records_processed = db.Column(db.Integer, default=0)
    success_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    error_summary = db.Column(db.Text, nullable=True)
    next_run = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)


class AIAgentConfig(db.Model):
    __tablename__ = "ai_agent_configs"
    id = db.Column(db.Integer, primary_key=True)
    agent_task = db.Column(db.String(100), nullable=False)
    model_name = db.Column(db.String(100), default="llama-3.3-70b-versatile")
    prompt_template = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)


class DiscoverySource(db.Model):
    __tablename__ = "discovery_sources"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    source_kind = db.Column(db.Enum("organization", "event", name="discovery_kind_enum"), nullable=False)
    category = db.Column(db.String(100))
    query_text = db.Column(db.String(500))
    region = db.Column(db.String(100))
    source_urls_json = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime, nullable=True)
    last_status = db.Column(db.String(255))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utc_now)


class ProcurementSupplier(db.Model):
    """Kandidat pemasok bahan apparel dengan provenance hasil pencarian web."""
    __tablename__ = "procurement_suppliers"

    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(255), nullable=False)
    product = db.Column(db.String(100), nullable=False)
    material = db.Column(db.String(255))
    region = db.Column(db.String(150))
    website = db.Column(db.String(500))
    source_url = db.Column(db.String(500), nullable=False)
    contact_email = db.Column(db.String(150))
    contact_phone = db.Column(db.String(100))
    description = db.Column(db.Text)
    fit_score = db.Column(db.Integer, default=0)
    recommendation_json = db.Column(db.Text)
    verification_status = db.Column(db.String(50), default="discovered")
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utc_now)


class Organization(db.Model):
    """
    MASTER ENTITY:
    Single source of truth untuk Company & Organization Intelligence.
    Menyimpan profil lengkap perusahaan dari berbagai sumber data akuisisi (BPS, Web, Vendor, Event).
    """
    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    normalized_name = db.Column(db.String(255), index=True, nullable=True)
    domain = db.Column(db.String(150), index=True, nullable=True)
    organization_type = db.Column(db.String(100), nullable=False, default="Perusahaan")
    industry = db.Column(db.String(150))
    address = db.Column(db.String(500))
    city = db.Column(db.String(100))
    province = db.Column(db.String(100))
    phone = db.Column(db.String(100))
    email = db.Column(db.String(150))
    website = db.Column(db.String(500))
    social_json = db.Column(db.Text)
    source_url = db.Column(db.String(500), nullable=True)
    description = db.Column(db.Text)
    product_fit = db.Column(db.String(255), nullable=True)
    opportunity_score = db.Column(db.Integer, default=0, index=True)
    priority_tier = db.Column(db.String(50), index=True, nullable=True)
    source_id = db.Column(db.Integer, db.ForeignKey("data_sources.id"), nullable=True)
    source_type = db.Column(db.String(50), default="bps")
    employee_size = db.Column(db.String(50), nullable=True)
    sport = db.Column(db.String(100), nullable=True)
    organization_subtype = db.Column(db.String(100), nullable=True)
    ai_scoring_json = db.Column(db.Text, nullable=True)
    relevance_score = db.Column(db.Integer, default=0)
    verification_status = db.Column(db.String(50), default="discovered")
    provenance_json = db.Column(db.Text, nullable=True)
    data_freshness = db.Column(db.DateTime, default=utc_now)
    last_seen = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    department_contacts_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)

    participations = db.relationship("EventParticipant", back_populates="organization", cascade="all, delete-orphan")
    campaign_targets = db.relationship("CampaignTarget", back_populates="organization", cascade="all, delete-orphan")

    def get_department_contacts(self) -> dict:
        import json
        if not self.department_contacts_json:
            return {}
        try:
            val = json.loads(self.department_contacts_json)
            return val if isinstance(val, dict) else {}
        except Exception:
            return {}

    @property
    def purchasing_contact(self) -> dict:
        return self.get_department_contacts().get("purchasing") or {}

    @property
    def procurement_contact(self) -> dict:
        return self.get_department_contacts().get("procurement") or {}

    @property
    def hr_contact(self) -> dict:
        return self.get_department_contacts().get("hr") or {}

    @property
    def community_pic_contact(self) -> dict:
        return self.get_department_contacts().get("pic_komunitas") or {}

    def get_ai_scoring(self) -> dict:
        import json
        if not self.ai_scoring_json:
            return {}
        try:
            return json.loads(self.ai_scoring_json) if isinstance(json.loads(self.ai_scoring_json), dict) else {}
        except Exception:
            return {}

    @property
    def ai_product_fit_score(self):
        sc = self.get_ai_scoring().get("product_fit_score")
        if sc is not None:
            return sc
        return self.opportunity_score or 0

    @property
    def ai_product_fit_label(self):
        lbl = self.get_ai_scoring().get("product_fit_label")
        if lbl:
            return lbl
        tier = self.priority_tier or ""
        if "HOT" in tier:
            return "High Fit"
        elif "WARM" in tier:
            return "Medium Fit"
        elif "POTENTIAL" in tier:
            return "Low Fit"
        return "Review"

    @property
    def ai_reasoning(self):
        return self.get_ai_scoring().get("reasoning", "")

    @property
    def ai_evidence(self):
        return self.get_ai_scoring().get("evidence_used", [])


class Event(db.Model):
    """
    EVENT INTELLIGENCE ENTITY:
    Menyimpan data pameran, expo, dan konferensi B2B di Indonesia.
    Terhubung dengan Organization melalui penyelenggara (organizer_id) dan peserta (EventParticipant).
    """
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    event_type = db.Column(db.String(150))
    organizer = db.Column(db.String(255))
    organizer_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    status = db.Column(db.String(50), default="upcoming", index=True)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    venue = db.Column(db.String(255))
    city = db.Column(db.String(100))
    province = db.Column(db.String(100))
    address = db.Column(db.String(500))
    website = db.Column(db.String(500))
    social_json = db.Column(db.Text)
    source_url = db.Column(db.String(500), nullable=True)
    description = db.Column(db.Text)
    relevance_notes = db.Column(db.Text, nullable=True)
    relevance_score = db.Column(db.Integer, default=0)
    verification_status = db.Column(db.String(50), default="discovered")
    department_contacts_json = db.Column(db.Text, nullable=True)
    last_seen = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    created_at = db.Column(db.DateTime, default=utc_now)

    organizer_org = db.relationship("Organization", foreign_keys=[organizer_id])
    participants = db.relationship("EventParticipant", back_populates="event", cascade="all, delete-orphan")

    def get_department_contacts(self) -> dict:
        import json
        if not self.department_contacts_json:
            return {}
        try:
            val = json.loads(self.department_contacts_json)
            return val if isinstance(val, dict) else {}
        except Exception:
            return {}

    @property
    def panitia_contact(self) -> dict:
        contacts = self.get_department_contacts()
        return contacts.get("panitia") or contacts.get("sponsorship") or contacts.get("sekretariat") or {}


class EventParticipant(db.Model):
    """
    RELASI EVENT PARTICIPANTS:
    Menghubungkan Event dengan Organization secara Many-to-Many untuk peran
    Organizer, Exhibitor, Sponsor, Partner, atau Speaker.
    """
    __tablename__ = "event_participants"
    __table_args__ = (
        db.UniqueConstraint("event_id", "organization_id", "role", name="uq_event_org_role"),
    )

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = db.Column(
        db.Enum("organizer", "exhibitor", "sponsor", "partner", "speaker", name="event_participant_role_enum"),
        nullable=False,
    )
    booth_number = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)

    event = db.relationship("Event", back_populates="participants")
    organization = db.relationship("Organization", back_populates="participations")


class DuplicateCandidate(db.Model):
    """
    KANDIDAT DUPLIKASI UNTUK REVIEW:
    Menyimpan pasangan entitas yang memiliki sinyal kecocokan ambigu (Tier 4 / conflict)
    yang memerlukan review manual sebelum disetujui / ditolak untuk digabungkan.
    """
    __tablename__ = "duplicate_candidates"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_name = db.Column(db.String(255), nullable=False)
    candidate_source = db.Column(db.String(100), nullable=True)
    candidate_payload_json = db.Column(db.Text, nullable=True)
    match_tier = db.Column(db.String(50), nullable=False)
    confidence_score = db.Column(db.Float, nullable=False)
    status = db.Column(
        db.Enum("pending", "approved", "rejected", name="candidate_status_enum"),
        default="pending",
        index=True,
    )
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)

    organization = db.relationship("Organization", backref=db.backref("duplicate_candidates", cascade="all, delete-orphan"))
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])


