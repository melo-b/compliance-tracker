from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.worker.celery_app import celery_app
from app.db.database import SessionLocal
from app.models.standard import ProductCompliance, ComplianceStatus

@celery_app.task(name="scan_expiring_compliance_records")
def scan_expiring_compliance_records(days_threshold: int = 30):
    """
    Scans the database for compliance records expiring within the threshold.
    Automatically updates their status to EXPIRING_SOON or EXPIRED.
    """
    # Create an independent database session for the background worker
    db: Session = SessionLocal()
    
    try:
        today = date.today()
        target_date = today + timedelta(days=days_threshold)

        # 1. Flag records expiring within the threshold that are currently VALID
        expiring_records = db.query(ProductCompliance).filter(
            ProductCompliance.expiration_date <= target_date,
            ProductCompliance.expiration_date >= today,
            ProductCompliance.status == ComplianceStatus.VALID
        ).all()

        expiring_count = 0
        for record in expiring_records:
            record.status = ComplianceStatus.EXPIRING_SOON
            expiring_count += 1
            
        # 2. Flag records that have completely EXPIRED
        expired_records = db.query(ProductCompliance).filter(
            ProductCompliance.expiration_date < today,
            ProductCompliance.status != ComplianceStatus.EXPIRED
        ).all()

        expired_count = 0
        for record in expired_records:
            record.status = ComplianceStatus.EXPIRED
            expired_count += 1

        db.commit()
        return {
            "status": "success", 
            "expiring_updated": expiring_count, 
            "expired_updated": expired_count
        }
        
    except Exception as e:
        db.rollback()
        raise e
        
    finally:
        # Always close the session to prevent database lockups
        db.close()