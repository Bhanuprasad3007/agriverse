from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ..models import db, User, Product, Investment, Transaction, SoilReport, GovScheme, SchemeApplication
from datetime import datetime, timedelta
from sqlalchemy import func, desc, and_, or_
from functools import wraps
import json

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/admin/dashboard')
@login_required
@admin_required
def dashboard():
    try:
        # Get user statistics with error handling
        total_users = User.query.count()
        total_farmers = User.query.filter_by(role='farmer').count()
        total_investors = User.query.filter_by(role='investor').count()
        
        # Get transaction volume with NULL handling
        total_volume = db.session.query(func.coalesce(func.sum(Transaction.amount), 0.0)).scalar()
        
        # Get pending users with validation
        pending_users = User.query.filter(
            User.is_verified == False,
            User.created_at != None
        ).order_by(User.created_at.desc()).all()
        
        # Get recent transactions with validation
        recent_transactions = Transaction.query.filter(
            Transaction.status.in_(['pending', 'completed', 'failed']),
            Transaction.amount != None,
            Transaction.created_at != None
        ).order_by(Transaction.created_at.desc()).limit(10).all()
        
        return render_template('admin/dashboard.html',
                             total_users=total_users,
                             total_farmers=total_farmers,
                             total_investors=total_investors,
                             total_volume=total_volume,
                             pending_users=pending_users,
                             recent_transactions=recent_transactions)
    except Exception as e:
        print(f"Admin Dashboard Error: {str(e)}")  # Log the error
        flash('An error occurred while loading the dashboard. Please try again.', 'error')
        return redirect(url_for('main.index'))

@admin_bp.route('/admin/users')
@login_required
@admin_required
def users():
    try:
        users = User.query.order_by(User.created_at.desc()).all()
        return render_template('admin/users.html', users=users)
    except Exception as e:
        flash(f'Error loading users: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/admin/verify-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def verify_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        user.is_verified = True
        db.session.commit()
        flash(f'User {user.name} has been verified.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error verifying user: {str(e)}', 'error')
    return redirect(request.referrer or url_for('admin.users'))

@admin_bp.route('/admin/toggle-user-status/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    try:
        user = User.query.get_or_404(user_id)
        if user.role == 'admin':
            flash('Cannot modify admin user status.', 'error')
            return redirect(request.referrer or url_for('admin.users'))
            
        user.is_active = not user.is_active
        db.session.commit()
        status = 'activated' if user.is_active else 'deactivated'
        flash(f'User {user.name} has been {status}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating user status: {str(e)}', 'error')
    return redirect(request.referrer or url_for('admin.users'))

@admin_bp.route('/admin/transactions')
@login_required
@admin_required
def transactions():
    try:
        # Get transactions with validation
        transactions = Transaction.query.filter(
            Transaction.status.in_(['pending', 'completed', 'failed']),
            Transaction.amount != None,
            Transaction.created_at != None
        ).order_by(Transaction.created_at.desc()).all()
        
        return render_template('admin/transactions.html', transactions=transactions)
    except Exception as e:
        print(f"Admin Transactions Error: {str(e)}")  # Log the error
        flash('An error occurred while loading transactions. Please try again.', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/admin/soil-reports')
@login_required
@admin_required
def soil_reports():
    reports = SoilReport.query.order_by(SoilReport.report_date.desc()).all()
    return render_template('admin/soil_reports.html', reports=reports)

@admin_bp.route('/admin/soil-report/<int:report_id>/update', methods=['POST'])
@login_required
@admin_required
def update_soil_report(report_id):
    report = SoilReport.query.get_or_404(report_id)
    status = request.form.get('status')
    notes = request.form.get('notes')
    
    if status in ['approved', 'rejected']:
        report.status = status
        report.notes = notes
        db.session.commit()
        
        flash(f'Soil report has been {status}.', 'success')
    return redirect(url_for('admin.soil_reports'))

@admin_bp.route('/admin/schemes')
@login_required
@admin_required
def schemes():
    try:
        # Get schemes with validation
        schemes = GovScheme.query.filter(
            GovScheme.start_date != None,
            GovScheme.end_date != None
        ).order_by(GovScheme.created_at.desc()).all()
        
        # Get applications with validation
        applications = SchemeApplication.query.filter(
            SchemeApplication.application_date != None
        ).order_by(SchemeApplication.application_date.desc()).all()
        
        return render_template('admin/schemes.html',
                             schemes=schemes,
                             applications=applications)
    except Exception as e:
        print(f"Admin Schemes Error: {str(e)}")  # Log the error
        flash('An error occurred while loading schemes. Please try again.', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/admin/scheme/add', methods=['POST'])
@login_required
@admin_required
def add_scheme():
    try:
        # Validate required fields
        name = request.form.get('name')
        description = request.form.get('description')
        eligibility = request.form.get('eligibility')
        benefits = request.form.get('benefits')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        
        if not all([name, description, eligibility, benefits, start_date_str, end_date_str]):
            flash('All fields are required.', 'error')
            return redirect(url_for('admin.schemes'))
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            
            if start_date >= end_date:
                flash('End date must be after start date.', 'error')
                return redirect(url_for('admin.schemes'))
                
            if start_date < datetime.now():
                flash('Start date cannot be in the past.', 'error')
                return redirect(url_for('admin.schemes'))
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'error')
            return redirect(url_for('admin.schemes'))
        
        scheme = GovScheme(
            name=name,
            description=description,
            eligibility_criteria=eligibility,
            benefits=benefits,
            start_date=start_date,
            end_date=end_date,
            status='active'
        )
        
        db.session.add(scheme)
        db.session.commit()
        
        flash('New government scheme added successfully!', 'success')
        return redirect(url_for('admin.schemes'))
        
    except Exception as e:
        db.session.rollback()
        print(f"Add Scheme Error: {str(e)}")  # Log the error
        flash('An error occurred while adding the scheme. Please try again.', 'error')
        return redirect(url_for('admin.schemes'))

@admin_bp.route('/admin/scheme-application/<int:application_id>/update', methods=['POST'])
@login_required
@admin_required
def update_scheme_application(application_id):
    try:
        application = SchemeApplication.query.get_or_404(application_id)
        status = request.form.get('status')
        notes = request.form.get('notes')
        
        if not status or status not in ['approved', 'rejected']:
            flash('Invalid status specified.', 'error')
            return redirect(url_for('admin.schemes'))
        
        application.status = status
        application.notes = notes
        
        try:
            db.session.commit()
            flash(f'Scheme application has been {status}.', 'success')
        except Exception as db_error:
            db.session.rollback()
            print(f"Database Error: {str(db_error)}")
            flash('An error occurred while updating the application. Please try again.', 'error')
            
        return redirect(url_for('admin.schemes'))
        
    except Exception as e:
        print(f"Update Application Error: {str(e)}")  # Log the error
        flash('An error occurred while processing the application. Please try again.', 'error')
        return redirect(url_for('admin.schemes'))

@admin_bp.route('/admin/chatbot')
@login_required
@admin_required
def chatbot():
    return render_template('admin/chatbot.html')

@admin_bp.route('/admin/traceability')
@login_required
@admin_required
def traceability():
    return render_template('admin/traceability.html') 