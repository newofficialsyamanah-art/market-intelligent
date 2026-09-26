import os
from flask import Flask, render_template
from flask_login import current_user, login_required

from app.config import Config, TestConfig
from app.extensions import db, login_manager, csrf


def create_app(config_class=None):
    app = Flask(__name__)
    if config_class is None:
        if os.getenv("FLASK_ENV") == "testing" or os.getenv("TESTING") == "1":
            config_class = TestConfig
        else:
            config_class = Config
    elif isinstance(config_class, str):
        if config_class.lower() in ("test", "testing"):
            config_class = TestConfig
        else:
            config_class = Config

    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Blueprints (mengikuti 7 kelompok use case pada diagram)
    from app.blueprints.auth.routes import auth_bp
    from app.blueprints.data_collection.routes import data_collection_bp
    from app.blueprints.data_processing.routes import data_processing_bp
    from app.blueprints.prospect.routes import prospect_bp
    from app.blueprints.market_analysis.routes import market_analysis_bp
    from app.blueprints.marketing.routes import marketing_bp
    from app.blueprints.reporting.routes import reporting_bp
    from app.blueprints.admin.routes import admin_bp
    from app.blueprints.events.routes import events_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(data_collection_bp, url_prefix="/data-collection")
    app.register_blueprint(data_processing_bp, url_prefix="/data-processing")
    app.register_blueprint(prospect_bp, url_prefix="/prospects")
    app.register_blueprint(market_analysis_bp, url_prefix="/market-analysis")
    app.register_blueprint(events_bp, url_prefix="/events")
    app.register_blueprint(marketing_bp, url_prefix="/marketing")
    app.register_blueprint(reporting_bp, url_prefix="/reporting")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.route("/")
    @login_required
    def dashboard():
        from app.models import (
            Prospect, RawData, Campaign, Organization, Event,
            CronJob, DuplicateCandidate, ActivityLog, User, CampaignTarget
        )
        from app.scheduler import is_scheduler_running

        user_role = current_user.role if hasattr(current_user, 'role') else 'guest'

        stats = {
            "total_prospects": Prospect.query.count(),
            "new_raw_data": RawData.query.filter_by(status="new").count(),
            "campaigns": Campaign.query.count(),
            "total_organizations": Organization.query.count(),
        }

        role_data = {}

        if user_role == "admin":
            role_data = {
                "scheduler_running": is_scheduler_running(),
                "total_users": User.query.count(),
                "active_jobs": CronJob.query.filter_by(is_active=True).count(),
                "failed_jobs": CronJob.query.filter(CronJob.last_status.like("error:%")).count(),
                "pending_duplicates": DuplicateCandidate.query.filter_by(status="pending").count(),
                "recent_logs": ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(8).all(),
                "cron_jobs": CronJob.query.order_by(CronJob.created_at.desc()).limit(6).all(),
                "total_orgs": stats["total_organizations"],
            }
        elif user_role == "business_analyst":
            edu_count = Organization.query.filter(
                Organization.organization_type.in_(["education", "school", "university"])
            ).count()
            comm_count = Organization.query.filter(
                Organization.organization_type.in_(["community", "sports_club", "student_org"])
            ).count()
            corp_count = Organization.query.filter(
                Organization.organization_type.in_(["corporate", "company", "brand"])
            ).count()
            social_count = Organization.query.filter(
                db.or_(
                    Organization.website.like("%instagram%"),
                    Organization.website.like("%tiktok%"),
                    Organization.source_url.like("%instagram%"),
                    Organization.source_url.like("%tiktok%"),
                    Organization.description.like("%instagram.com%"),
                    Organization.description.like("%tiktok.com%")
                )
            ).count()
            role_data = {
                "total_orgs": stats["total_organizations"],
                "total_prospects": stats["total_prospects"],
                "edu_count": edu_count,
                "comm_count": comm_count,
                "corp_count": corp_count,
                "other_count": max(0, stats["total_organizations"] - edu_count - comm_count - corp_count),
                "social_count": social_count,
                "total_events": Event.query.count(),
                "pending_duplicates": DuplicateCandidate.query.filter_by(status="pending").count(),
                "recent_orgs": Organization.query.order_by(Organization.last_seen.desc()).limit(6).all(),
            }
        elif user_role == "marketing":
            high_fit = Organization.query.filter(
                db.or_(
                    Organization.priority_tier == "high",
                    Organization.product_fit.in_(["high", "High", "HIGH"]),
                    Organization.opportunity_score >= 80
                )
            ).count()
            med_fit = Organization.query.filter(
                db.or_(
                    Organization.priority_tier == "medium",
                    Organization.product_fit.in_(["medium", "Medium"]),
                    db.and_(Organization.opportunity_score >= 50, Organization.opportunity_score < 80)
                )
            ).count()
            sports_targets = Organization.query.filter(
                db.or_(
                    Organization.sport.isnot(None),
                    Organization.organization_subtype.in_(["futsal_club", "football_club", "basketball_club", "running_club", "sports_club"])
                )
            ).count()
            active_campaigns = Campaign.query.filter_by(status="active").count()
            campaign_targets_count = CampaignTarget.query.count()
            top_accounts = Organization.query.order_by(Organization.opportunity_score.desc()).limit(6).all()
            recent_campaigns = Campaign.query.order_by(Campaign.created_at.desc()).limit(5).all()
            upcoming_events = Event.query.order_by(Event.created_at.desc()).limit(5).all()

            role_data = {
                "high_fit": high_fit,
                "med_fit": med_fit,
                "sports_targets": sports_targets,
                "total_targets": stats["total_organizations"],
                "active_campaigns": active_campaigns,
                "campaign_targets_count": campaign_targets_count,
                "top_accounts": top_accounts,
                "recent_campaigns": recent_campaigns,
                "upcoming_events": upcoming_events,
            }
        elif user_role == "management":
            high_fit = Organization.query.filter(
                db.or_(
                    Organization.priority_tier == "high",
                    Organization.product_fit.in_(["high", "High", "HIGH"]),
                    Organization.opportunity_score >= 80
                )
            ).count()
            total_campaigns = Campaign.query.count()
            active_campaigns = Campaign.query.filter_by(status="active").count()
            total_events = Event.query.count()
            campaigns = Campaign.query.order_by(Campaign.created_at.desc()).limit(5).all()

            edu_count = Organization.query.filter(Organization.organization_type.in_(["education", "school", "university"])).count()
            comm_count = Organization.query.filter(Organization.organization_type.in_(["community", "sports_club", "student_org"])).count()
            corp_count = Organization.query.filter(Organization.organization_type.in_(["corporate", "company", "brand"])).count()

            role_data = {
                "tam_universe": stats["total_organizations"],
                "total_prospects": stats["total_prospects"],
                "high_priority_market": high_fit,
                "edu_coverage": edu_count,
                "comm_coverage": comm_count,
                "corp_coverage": corp_count,
                "total_campaigns": total_campaigns,
                "active_campaigns": active_campaigns,
                "total_events": total_events,
                "recent_campaigns": campaigns,
            }

        return render_template("dashboard.html", stats=stats, role=user_role, role_data=role_data)

    try:
        with app.app_context():
            db.create_all()
    except Exception as e:
        app.logger.warning(f"Inisialisasi tabel database ditunda (MySQL belum aktif / unreachable): {e}")

    from app.scheduler import start_scheduler
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        try:
            start_scheduler(app)
        except Exception as e:
            app.logger.warning(f"Scheduler background ditunda: {e}")

    return app
