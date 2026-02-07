from flask import Flask, render_template, redirect, url_for, session
from flask_apscheduler import APScheduler

from routes.dashboard import dashboard_bp
from routes.transaction import transaction_bp
from routes.auth import auth_bp
from routes.account import account_bp
from routes.budget import budget_bp
from routes.goals import goals_bp
from routes.balance import balance_bp

from jobs.monthly_snapshot_job import run_monthly_snapshot

class Config:
    SCHEDULER_API_ENABLED = True
    SECRET_KEY = 'your_super_secret_key'  # secret key for sessions

scheduler = APScheduler()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(transaction_bp)
    app.register_blueprint(account_bp, url_prefix='/account')
    app.register_blueprint(budget_bp, url_prefix='/budget')
    app.register_blueprint(goals_bp, url_prefix='/goals')
    app.register_blueprint(balance_bp, url_prefix='/balance')
    
    # Scheduler init
    scheduler.init_app(app)
    scheduler.start()

    # Monthly snapshot job
    # Run once at app start for last month if missing
    run_monthly_snapshot()

    # Scheduler (optional) to continue daily runs
    scheduler.add_job(
        id='monthly_balance_snapshot',
        func=run_monthly_snapshot,
        trigger='cron',
        hour=2,
        minute=0
    )


    # Default route
    @app.route('/')
    def home():
        if 'user_id' in session:
            return redirect(url_for('dashboard.dashboard'))
        return redirect(url_for('auth.login'))

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
