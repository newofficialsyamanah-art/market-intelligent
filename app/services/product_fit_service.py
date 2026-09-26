"""AI Product Fit & Explainable Scoring Service.

Mengevaluasi kesesuaian entitas Master Organization terhadap produk (Produk Utama: JERSEY / CUSTOM TEAMWEAR;
dapat diskalakan ke Merchandise, Seragam Kantor, Kaos Event, Training Wear).

Fitur Utama:
1. Menggunakan AI (Groq LLM / llama-3.3-70b-versatile) untuk menilai relevansi secara holistik.
2. Mempertimbangkan evidence nyata:
   - organization_type & organization_subtype
   - industry & description
   - sport (futsal, sepak bola, basket, running, cycling, dll)
   - activity signals (turnamen, liga, event, dies natalis, gathering, dll)
   - event participations & event relevance score
   - social signals (Instagram, TikTok, Facebook, LinkedIn)
   - contactability & location
3. Output Terstandar & Explainable:
   - product_fit_score (0-100)
   - product_fit_label (High Fit, Medium Fit, Low Fit, Unfit, Review)
   - reasoning (Jawaban: "Mengapa organisasi ini relevan dengan Jersey?")
   - confidence (0.0 - 1.0)
   - evidence_used (Daftar fakta yang diverifikasi)
   - model_provider & scored_at
4. PENTING: AI TIDAK BOLEH mengarang evidence. Jika data minim -> confidence rendah / label Review.
5. Resilient: Jika AI unavailable, fallback ke evidentiary scoring tanpa menghapus data yang ada.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.extensions import db
from app.models import Organization, EventParticipant, utc_now
from app import ai_agent
from app.services.social_connector import SocialConnectorService

logger = logging.getLogger(__name__)

DEFAULT_PRODUCT = "Jersey / Custom Teamwear"

SUPPORTED_PRODUCTS = [
    "Jersey / Custom Teamwear",
    "Custom Teamwear",
    "Seragam Kantor / Corporate Uniform",
    "Kaos Event & Merchandise",
    "Wearpack & Industrial Safety",
    "Jaket Kontingen / Almamater"
]


class ProductFitService:
    """Service modular untuk penilaian AI Product Fit yang explainable dan berbasis evidence."""

    @classmethod
    def collect_organization_evidence(cls, org: Organization) -> Dict[str, Any]:
        """Mengumpulkan seluruh sinyal dan bukti nyata yang ada dari profil Master Organization."""
        evidence = {
            "organization_id": org.id,
            "name": org.name,
            "organization_type": org.organization_type or "Perusahaan",
            "organization_subtype": org.organization_subtype or "Umum",
            "industry": org.industry or "Umum",
            "sport": org.sport or None,
            "description": org.description or "",
            "location": f"{org.city or ''}, {org.province or ''}".strip(", "),
            "has_website": bool(org.website and org.website != "nan"),
            "has_phone": bool(org.phone and org.phone != "nan"),
            "has_email": bool(org.email and org.email != "nan"),
            "employee_size": org.employee_size or "Tidak diketahui",
            "social_platforms": [],
            "social_signals": [],
            "events_participated": []
        }

        # 1. Media Sosial
        if org.social_json:
            try:
                soc = json.loads(org.social_json) if isinstance(json.loads(org.social_json), dict) else {}
                evidence["social_platforms"] = list(soc.keys())
            except Exception:
                pass

        # 2. Sinyal dari Provenance / Teks
        social_conn = SocialConnectorService()
        text_corp = f"{org.name} {org.description or ''} {org.product_fit or ''}"
        extracted_sig = social_conn.extract_social_signals(text_corp)
        evidence["social_signals"] = extracted_sig.get("evidence", [])

        if not evidence["sport"] and extracted_sig.get("sport_signals"):
            evidence["sport"] = extracted_sig["sport_signals"][0].title()

        # 3. Keterkaitan Event
        if org.participations:
            for part in org.participations:
                if part.event:
                    evidence["events_participated"].append({
                        "event_name": part.event.name,
                        "event_type": part.event.event_type or "Event",
                        "role": part.role,
                        "relevance_score": part.event.relevance_score or 0
                    })

        return evidence

    @classmethod
    def evaluate_organization(
        cls,
        org: Organization,
        target_product: str = DEFAULT_PRODUCT,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Mengevaluasi kesesuaian satu entitas Master Organization terhadap target produk menggunakan AI.
        Hasil disimpan dalam `ai_scoring_json` dan merefleksikan score, reasoning, evidence, dan confidence.
        """
        evidence_data = cls.collect_organization_evidence(org)
        now_str = utc_now().isoformat()

        # Siapkan prompt untuk AI Agent
        system_prompt = (
            "Kamu adalah Senior B2B Marketing Intelligence & Product-Fit Evaluator untuk industri apparel & teamwear di Indonesia.\n"
            f"Produk Target: '{target_product}'.\n"
            "TUGAS: Analisis profil organisasi di bawah dan tentukan apakah mereka membutuhkan produk ini.\n"
            "KRITERIA PENILAIAN:\n"
            "1. Komunitas Olahraga (Futsal, Sepak Bola, Basket, Running, Cycling, Esports) -> Kebutuhan Jersey SANGAT TINGGI.\n"
            "2. Organisasi Mahasiswa / UKM Olahraga / BEM / HIMA -> Kebutuhan Jersey / Kaos Angkatan / Jaket TINGGI.\n"
            "3. Sekolah / Universitas -> Kebutuhan Seragam Olahraga / Kaos Kelas / Almamater TINGGI.\n"
            "4. Perusahaan Industri / Korporat -> Kebutuhan Seragam Kerja / Polo Shirt / Wearpack TINGGI, Jersey Olahraga SEDANG.\n"
            "5. Jika ada partisipasi turnamen / event olahraga -> Tambahan peluang signifikan.\n"
            "PENTING:\n"
            "- JANGAN MENGARANG DATA / EVENT YANG TIDAK ADA DALAM EVIDENCE.\n"
            "- Jika data sangat minim, beri confidence < 0.60 dan label 'Review'.\n"
            "- Reasoning HARUS menjelaskan secara spesifik alasan relevansi dalam 2-4 kalimat bahasa Indonesia."
        )

        user_prompt = (
            f"Data Evidence Organisasi:\n{json.dumps(evidence_data, ensure_ascii=False, indent=2)}\n\n"
            "Balas HANYA dengan JSON valid format:\n"
            "{\n"
            '  "product_fit_score": 0-100,\n'
            '  "product_fit_label": "High Fit / Medium Fit / Low Fit / Unfit / Review",\n'
            '  "reasoning": "Penjelasan spesifik mengapa organisasi ini cocok/tidak cocok dengan produk...",\n'
            '  "confidence": 0.0-1.0,\n'
            '  "evidence_used": ["daftar poin evidence yang benar-benar ada di atas"],\n'
            '  "recommended_apparel": "Daftar apparel spesifik (misal: Jersey Futsal, Rompi Latihan, Kaos Polo)"\n'
            "}"
        )

        ai_res = None
        model_used = "llama-3.3-70b-versatile"

        try:
            ai_res = ai_agent._chat_json(system_prompt, user_prompt, temperature=0.2, task_name="ai_product_fit")
        except Exception as e:
            logger.warning(f"Groq AI call failed for org #{org.id}: {e}")
            ai_res = None

        # Fallback evidentiary deterministik jika AI tidak merespons / gagal
        if not ai_res or not isinstance(ai_res, dict) or "product_fit_score" not in ai_res:
            ai_res = cls._evidentiary_rule_fallback(evidence_data, target_product)
            model_used = "rule_evidentiary_fallback"

        score = int(ai_res.get("product_fit_score", 50))
        score = min(100, max(0, score))
        label = ai_res.get("product_fit_label", "Review")
        reasoning = ai_res.get("reasoning", "Evaluasi otomatis berbasis data profil.")
        confidence = float(ai_res.get("confidence", 0.7))
        evidence_used = ai_res.get("evidence_used", [])
        recommended_apparel = ai_res.get("recommended_apparel", target_product)

        # Mapping Tier
        if score >= 80:
            tier = "A - HOT"
        elif score >= 65:
            tier = "B - WARM"
        elif score >= 50:
            tier = "C - POTENTIAL"
        else:
            tier = "D - LOW"

        scoring_payload = {
            "target_product": target_product,
            "product_fit_score": score,
            "product_fit_label": label,
            "reasoning": reasoning,
            "confidence": confidence,
            "evidence_used": evidence_used,
            "recommended_apparel": recommended_apparel,
            "model_provider": model_used,
            "scored_at": now_str
        }

        if not dry_run:
            org.ai_scoring_json = json.dumps(scoring_payload, ensure_ascii=False)
            org.product_fit = recommended_apparel or target_product
            org.opportunity_score = score
            org.priority_tier = tier
            org.data_freshness = datetime.now(timezone.utc).replace(tzinfo=None)
            db.session.commit()

        return scoring_payload

    @classmethod
    def _evidentiary_rule_fallback(cls, evidence: Dict[str, Any], target_product: str) -> Dict[str, Any]:
        """Fallback evaluasi deterministik berbasis fakta nyata jika AI provider tidak dapat dihubungi."""
        org_type = (evidence.get("organization_type") or "").lower()
        sport = (evidence.get("sport") or "").lower()
        desc = (evidence.get("description") or "").lower()
        name = (evidence.get("name") or "").lower()
        events = evidence.get("events_participated") or []

        score = 40
        reasons = []
        evidence_used = []
        apparel = target_product

        # 1. Tipe Organisasi
        if "olahraga" in org_type or "sport" in org_type or "club" in name:
            score += 35
            reasons.append("Tipe organisasi merupakan komunitas/klub olahraga yang memerlukan seragam bertanding.")
            evidence_used.append(f"organization_type: {evidence.get('organization_type')}")
        elif "mahasiswa" in org_type or "bem" in name or "ukm" in name:
            score += 30
            reasons.append("Organisasi mahasiswa rutin menyelenggarakan kompetisi, porseni, dan seragam angkatan.")
            evidence_used.append("student_organization")
        elif "pendidikan" in org_type or "universitas" in name or "sekolah" in name:
            score += 25
            reasons.append("Institusi pendidikan memiliki kebutuhan seragam olahraga, almamater, dan event kampus.")
            evidence_used.append("education_institution")
        elif "perusahaan" in org_type:
            score += 15
            reasons.append("Perusahaan korporat membutuhkan polo shirt seragam, seragam kantor, dan pakaian kerja.")
            evidence_used.append("corporate_entity")

        # 2. Sinyal Olahraga
        if sport or any(s in desc for s in ("futsal", "sepak bola", "basket", "voli", "lari", "sepeda")):
            score += 15
            active_sport = sport or "olahraga"
            reasons.append(f"Teridentifikasi aktivitas spesifik pada cabang olahraga {active_sport}.")
            evidence_used.append(f"sport: {active_sport}")
            apparel = f"Jersey {active_sport.title()}, Kaos Tim, Jaket Training"

        # 3. Keterkaitan Event
        if events:
            score += 10
            ev_names = [e["event_name"] for e in events[:2]]
            reasons.append(f"Berpartisipasi dalam event B2B/pameran: {', '.join(ev_names)}.")
            evidence_used.append(f"event_participation: {len(events)} events")

        # 4. Kelengkapan Kontak
        if evidence.get("has_phone") or evidence.get("has_email"):
            score += 5
            evidence_used.append("contactable")

        score = min(98, max(20, score))

        if score >= 80:
            label = "High Fit"
        elif score >= 65:
            label = "Medium Fit"
        elif score >= 50:
            label = "Low Fit"
        else:
            label = "Review"

        return {
            "product_fit_score": score,
            "product_fit_label": label,
            "reasoning": " ".join(reasons) or "Evaluasi rule-backed berbasis kategori profil.",
            "confidence": 0.85 if evidence_used else 0.50,
            "evidence_used": evidence_used,
            "recommended_apparel": apparel,
            "model_provider": "rule_evidentiary_fallback"
        }

    @classmethod
    def batch_evaluate(
        cls,
        target_product: str = DEFAULT_PRODUCT,
        limit: int = 25,
        organization_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Menjalankan evaluasi AI Product Fit secara batch untuk sejumlah organisasi master."""
        query = Organization.query
        if organization_ids:
            query = query.filter(Organization.id.in_(organization_ids))
        else:
            # Prioritaskan organisasi yang belum memiliki ai_scoring_json
            query = query.filter(
                db.or_(Organization.ai_scoring_json.is_(None), Organization.ai_scoring_json == "")
            )

        orgs = query.order_by(Organization.opportunity_score.desc()).limit(limit).all()

        results = []
        high_fit_count = 0

        for org in orgs:
            res = cls.evaluate_organization(org, target_product=target_product, dry_run=False)
            results.append({"org_id": org.id, "name": org.name, "score": res["product_fit_score"], "label": res["product_fit_label"]})
            if res["product_fit_score"] >= 80:
                high_fit_count += 1

        return {
            "product": target_product,
            "total_scored": len(results),
            "high_fit_count": high_fit_count,
            "details": results
        }
