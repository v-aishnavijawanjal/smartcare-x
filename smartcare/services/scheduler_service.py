import logging

from apscheduler.schedulers.background import BackgroundScheduler

from smartcare.emails.mailer import send_bill_reminder
from smartcare.services.billing_service import get_bills_needing_reminder, mark_reminder_sent

logger = logging.getLogger(__name__)

_scheduler = None


def _send_due_bill_reminders(app):
    """Send payment reminder emails for due medicine bills."""
    with app.app_context():
        bills = get_bills_needing_reminder()
        for bill in bills:
            send_bill_reminder(bill)
            mark_reminder_sent(bill)
        if bills:
            logger.info("Sent %d medicine bill payment reminder(s).", len(bills))


def init_scheduler(app):
    global _scheduler
    if _scheduler is not None:
        return  # Scheduler already running.

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        func=lambda: _send_due_bill_reminders(app),
        trigger="interval",
        hours=24,
        id="bill_payment_reminders",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Background scheduler started (bill payment reminders every 24h).")