from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from ..models import db, User
from ..forms import LoginForm, SignupForm

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/signup/<role>', methods=['GET', 'POST'])
def signup(role):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if role not in ['farmer', 'investor']:
        return redirect(url_for('main.index'))
    
    form = SignupForm()
    
    if form.validate_on_submit():
        # Check if user already exists
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered', 'danger')
            return render_template('auth/signup.html', form=form, role=role)
        
        # Create new user
        user = User(
            name=form.name.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data),
            role=role
        )
        
        # Add farmer-specific fields
        if role == 'farmer':
            user.farm_location = form.location.data
            user.farm_size = form.farm_size.data
        
        try:
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('auth.login', role=role))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred. Please try again.', 'danger')
            print(f"Registration Error: {str(e)}")
    
    return render_template('auth/signup.html', form=form, role=role)

@auth_bp.route('/login/<role>', methods=['GET', 'POST'])
def login(role):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if role not in ['farmer', 'investor', 'admin']:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data, role=role).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            if role == 'farmer':
                return redirect(url_for('farmer.dashboard'))
            elif role == 'investor':
                return redirect(url_for('investor.dashboard'))
            else:
                return redirect(url_for('admin.dashboard'))
        flash('Invalid email or password', 'danger')
    
    return render_template('auth/login.html', form=form, role=role)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))

@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html')

@auth_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    try:
        # Update basic information
        current_user.name = request.form.get('name')
        
        # Update role-specific information
        if current_user.role == 'farmer':
            current_user.farm_name = request.form.get('farm_name')
            current_user.farm_location = request.form.get('farm_location')
            current_user.farm_size = float(request.form.get('farm_size', 0))
        elif current_user.role == 'investor':
            current_user.company_name = request.form.get('company_name')
            current_user.investment_capacity = float(request.form.get('investment_capacity', 0))
        
        # Handle password change
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if current_password and new_password:
            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('auth.profile'))
                
            if check_password_hash(current_user.password_hash, current_password):
                current_user.password_hash = generate_password_hash(new_password)
                flash('Password updated successfully.', 'success')
            else:
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('auth.profile'))
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while updating your profile: {str(e)}', 'error')
    
    return redirect(url_for('auth.profile')) 