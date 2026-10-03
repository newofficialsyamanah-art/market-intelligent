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
    from app.blueprints.procurement.routes import procurement_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(data_collection_bp, url_prefix="/data-collection")
    app.register_blueprint(data_processing_bp, url_prefix="/data-processing")
    app.register_blueprint(prospect_bp, url_prefix="/prospects")
    app.register_blueprint(market_analysis_bp, url_prefix="/market-analysis")
    app.register_blueprint(events_bp, url_prefix="/events")
    app.register_blueprint(marketing_bp, url_prefix="/marketing")
    app.register_blueprint(reporting_bp, url_prefix="/reporting")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(procurement_bp, url_prefix="/procurement")

    from app.utils import parse_whatsapp
    app.jinja_env.filters["parse_wa"] = parse_whatsapp

    @app.context_processor
    def inject_helpers():
        return dict(parse_wa=parse_whatsapp)

    @app.route("/")
    @login_required
    def dashboard():
        from app.models import (
            Prospect, RawData, Campaign, Organization, Event,
            CronJob, DuplicateCandidate, ActivityLog, User, CampaignTarget, ProcurementSupplier
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
        elif user_role == "procurement":
            role_data = {
                "supplier_count": ProcurementSupplier.query.count(),
                "high_fit_suppliers": ProcurementSupplier.query.filter(ProcurementSupplier.fit_score >= 75).count(),
                "recent_suppliers": ProcurementSupplier.query.order_by(ProcurementSupplier.created_at.desc()).limit(6).all(),
            }
        elif user_role == "supplier":
            my_suppliers = ProcurementSupplier.query.filter_by(created_by=current_user.id).all() if current_user.is_authenticated else []
            role_data = {
                "my_supplier_count": len(my_suppliers),
                "total_suppliers": ProcurementSupplier.query.count(),
                "my_suppliers": my_suppliers,
            }

        # Ringkasan Kategori Lintas Modul untuk Dashboard Utama
        org_type_tuples = db.session.query(Organization.organization_type, db.func.count(Organization.id)).group_by(Organization.organization_type).all()
        org_types_map = {str(k).lower(): v for k, v in org_type_tuples if k}
        
        corp_sum = org_types_map.get("perusahaan", 0) + org_types_map.get("corporate", 0) + org_types_map.get("company", 0)
        comm_sum = org_types_map.get("community", 0) + org_types_map.get("komunitas olahraga", 0) + org_types_map.get("sports_club", 0)
        edu_sum = org_types_map.get("education", 0) + org_types_map.get("school", 0) + org_types_map.get("university", 0)
        mahasiswa_sum = org_types_map.get("student_organization", 0) + org_types_map.get("student_org", 0)
        other_sum = max(0, stats["total_organizations"] - corp_sum - comm_sum - edu_sum - mahasiswa_sum)

        supplier_prod_tuples = db.session.query(ProcurementSupplier.product, db.func.count(ProcurementSupplier.id)).group_by(ProcurementSupplier.product).all()
        supplier_prods_map = {str(k).lower(): v for k, v in supplier_prod_tuples if k}

        tier_tuples = db.session.query(Organization.priority_tier, db.func.count(Organization.id)).group_by(Organization.priority_tier).all()
        tier_map = {str(k): v for k, v in tier_tuples if k}

        category_summaries = {
            "organizations": {
                "perusahaan": corp_sum,
                "komunitas": comm_sum,
                "pendidikan": edu_sum,
                "mahasiswa": mahasiswa_sum,
                "lainnya": other_sum,
                "total": stats["total_organizations"]
            },
            "tiers": {
                "hot": tier_map.get("A - HOT", 0),
                "warm": tier_map.get("B - WARM", 0),
                "potential": tier_map.get("C - POTENTIAL", 0),
                "low": tier_map.get("D - LOW", 0)
            },
            "suppliers": {
                "raw_material": supplier_prods_map.get("raw material", 0) + supplier_prods_map.get("jersey", 0) + supplier_prods_map.get("kaos", 0) + supplier_prods_map.get("polo", 0) + supplier_prods_map.get("kemeja", 0) + supplier_prods_map.get("jaket", 0),
                "distributor": supplier_prods_map.get("distributor", 0),
                "elektrikal": supplier_prods_map.get("elektrikal", 0),
                "services": supplier_prods_map.get("services", 0),
                "pharmaceutical": supplier_prods_map.get("pharmaceutical", 0),
                "local": supplier_prods_map.get("local", 0),
                "hardware": supplier_prods_map.get("hardware", 0),
                "software": supplier_prods_map.get("software", 0),
                "total": sum(supplier_prods_map.values())
            },
            "events": {
                "total": Event.query.count(),
                "upcoming": Event.query.filter_by(status="upcoming").count(),
                "high_relevance": Event.query.filter(Event.relevance_score >= 60).count()
            }
        }

        return render_template(
            "dashboard.html",
            stats=stats,
            role=user_role,
            role_data=role_data,
            category_summaries=category_summaries
        )

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
