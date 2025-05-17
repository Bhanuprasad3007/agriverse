from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from ..models import db, Product, Investment, SoilReport, Transaction, GovScheme, SchemeApplication
from datetime import datetime, timedelta
from functools import wraps
from sqlalchemy import func

farmer_bp = Blueprint('farmer', __name__)

def farmer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'farmer':
            flash('Access denied. Farmer privileges required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@farmer_bp.route('/farmer/dashboard')
@login_required
@farmer_required
def dashboard():
    # Get farmer's products
    products = Product.query.filter_by(seller_id=current_user.id).all()
    
    # Get all types of investments
    investment_requests = Investment.query.filter_by(
        farmer_id=current_user.id,
        status='seeking'
    ).order_by(Investment.created_at.desc()).all()
    
    investment_offers = Investment.query.filter_by(
        farmer_id=current_user.id,
        status='offered'
    ).order_by(Investment.created_at.desc()).all()
    
    active_investments = Investment.query.filter_by(
        farmer_id=current_user.id,
        status='active'
    ).order_by(Investment.created_at.desc()).all()
    
    # Get completed investments
    completed_investments = Investment.query.filter_by(
        farmer_id=current_user.id,
        status='completed'
    ).order_by(Investment.created_at.desc()).all()

    print(f"Debug: Number of completed investments fetched: {len(completed_investments)}") # Debug print

    # Get recent transactions
    transactions = Transaction.query.filter_by(
        seller_id=current_user.id
    ).order_by(Transaction.created_at.desc()).limit(5).all()
    
    # Get sales data for the past 6 months for the chart
    six_months_ago = datetime.now() - timedelta(days=180)
    sales_data = Transaction.query.with_entities( 
        func.strftime('%Y-%m', Transaction.created_at).label('month'), 
        func.sum(Transaction.amount).label('total_sales') 
    ).filter(
        Transaction.seller_id == current_user.id,
        Transaction.transaction_type == 'product',
        Transaction.status == 'completed',
        Transaction.created_at >= six_months_ago
    ).group_by(
        func.strftime('%Y-%m', Transaction.created_at)
    ).order_by(
        func.strftime('%Y-%m', Transaction.created_at)
    ).all()

    # Format sales data for Chart.js
    sales_labels = [datetime.strptime(row.month, '%Y-%m').strftime('%b') for row in sales_data] # e.g., Jan, Feb
    sales_values = [row.total_sales for row in sales_data]

    # Get soil reports
    soil_reports = SoilReport.query.filter_by(
        farmer_id=current_user.id
    ).order_by(SoilReport.report_date.desc()).all()
    
    # Calculate total active investment amount
    total_active_amount = sum(inv.amount for inv in active_investments)

    # Calculate total completed investment amount and total returns
    total_completed_amount = sum(inv.amount for inv in completed_investments)
    total_returns = sum(inv.amount * (1 + inv.interest_rate/100) for inv in completed_investments)

    print(f"Debug: Total completed amount: {total_completed_amount}") # Debug print
    print(f"Debug: Total returns: {total_returns}") # Debug print
    
    return render_template('farmer/dashboard.html',
                         products=products,
                         investment_requests=investment_requests,
                         investment_offers=investment_offers,
                         active_investments=active_investments,
                         total_active_amount=total_active_amount,
                         total_completed_amount=total_completed_amount,
                         total_returns=total_returns,
                         transactions=transactions,
                         sales_labels=sales_labels,
                         sales_values=sales_values,
                         soil_reports=soil_reports)

@farmer_bp.route('/farmer/products', methods=['GET', 'POST'])
@login_required
@farmer_required
def products():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price'))
        quantity = float(request.form.get('quantity'))
        unit = request.form.get('unit')
        category = request.form.get('category')
        
        # Handle image upload
        image = request.files.get('image')
        image_url = None
        if image:
            filename = secure_filename(image.filename)
            image.save(os.path.join('app/static/uploads/products', filename))
            image_url = f'/static/uploads/products/{filename}'
        
        product = Product(
            name=name,
            description=description,
            price=price,
            quantity=quantity,
            unit=unit,
            category=category,
            image_url=image_url,
            seller_id=current_user.id
        )
        
        db.session.add(product)
        db.session.commit()
        
        flash('Product added successfully!', 'success')
        return redirect(url_for('farmer.products'))
    
    products = Product.query.filter_by(seller_id=current_user.id).all()
    return render_template('farmer/products.html', products=products)

@farmer_bp.route('/farmer/investments', methods=['GET', 'POST'])
@login_required
@farmer_required
def investments():
    if request.method == 'POST':
        try:
            # Get and validate form data
            try:
                amount = float(request.form.get('amount', 0))
                duration = int(request.form.get('duration', 0))
                interest_rate = float(request.form.get('interest_rate', 0))
            except (ValueError, TypeError):
                flash('Please enter valid numeric values for amount, duration, and interest rate.', 'error')
                return redirect(url_for('farmer.investments'))
            
            # Validate numeric values
            if amount <= 0:
                flash('Investment amount must be greater than zero.', 'error')
                return redirect(url_for('farmer.investments'))
            if duration <= 0:
                flash('Duration must be greater than zero.', 'error')
                return redirect(url_for('farmer.investments'))
            if interest_rate <= 0 or interest_rate > 20:
                flash('Interest rate must be between 0% and 20%.', 'error')
                return redirect(url_for('farmer.investments'))
            
            # Get project details
            crop_type = request.form.get('crop_type', '')
            land_size = request.form.get('land_size', '')
            expected_yield = request.form.get('expected_yield', '')
            project_title = request.form.get('project_title', '')
            description = request.form.get('description', '')
            
            # Create investment request
            description_text = f"""
Project: {project_title}

Investment Request Details:
- Crop Type: {crop_type}
- Land Size: {land_size} acres
- Expected Yield: {expected_yield}
- Additional Details: {description}

Farmer Details:
- Name: {current_user.name}
- Farm Name: {current_user.farm_name}
- Location: {current_user.farm_location}
- Experience: {current_user.farm_size} acres managed
"""
            
            investment = Investment(
                farmer_id=current_user.id,
                investor_id=None,  # Will be set when an investor makes an offer
                amount=amount,
                duration=duration,
                interest_rate=interest_rate,
                description=description_text,
                status='seeking'  # Initial status for investment requests
            )
            
            db.session.add(investment)
            db.session.commit()
            
            flash('Investment request created successfully!', 'success')
            return redirect(url_for('farmer.investments'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Investment Request Error: {str(e)}")
            flash('An error occurred while creating the investment request. Please try again.', 'error')
            return redirect(url_for('farmer.investments'))
    
    # Get my investment requests
    my_requests = Investment.query.filter_by(
        farmer_id=current_user.id,
        status='seeking'  # Only show active requests
    ).order_by(Investment.created_at.desc()).all()
    
    # Get investment offers
    investment_offers = Investment.query.filter_by(
        farmer_id=current_user.id,
        status='offered'
    ).order_by(Investment.created_at.desc()).all()
    
    # Get active investments
    active_investments = Investment.query.filter_by(
        farmer_id=current_user.id,
        status='active'
    ).order_by(Investment.created_at.desc()).all()
    
    # Get completed investments
    completed_investments = Investment.query.filter_by(
        farmer_id=current_user.id,
        status='completed'
    ).order_by(Investment.created_at.desc()).all()
    
    # Calculate total statistics
    total_active_amount = sum(inv.amount for inv in active_investments)
    total_completed_amount = sum(inv.amount for inv in completed_investments)
    total_returns = sum(inv.amount * (1 + inv.interest_rate/100) for inv in completed_investments)
    
    return render_template('farmer/investments.html',
                         my_requests=my_requests,
                         investment_offers=investment_offers,
                         active_investments=active_investments,
                         completed_investments=completed_investments,
                         total_active_amount=total_active_amount,
                         total_completed_amount=total_completed_amount,
                         total_returns=total_returns)

@farmer_bp.route('/farmer/investment/<int:investment_id>/action', methods=['POST'])
@login_required
@farmer_required
def investment_action(investment_id):
    try:
        investment = Investment.query.get_or_404(investment_id)
        
        # Verify ownership
        if investment.farmer_id != current_user.id:
            flash('Unauthorized action.', 'error')
            return redirect(url_for('farmer.investments'))
        
        action = request.form.get('action')
        if action not in ['accept', 'reject', 'cancel']:
            flash('Invalid action.', 'error')
            return redirect(url_for('farmer.investments'))
        
        # Map actions to status transitions
        action_status_map = {
            'accept': 'active',
            'reject': 'rejected',
            'cancel': 'cancelled'
        }
        
        new_status = action_status_map[action]
        
        # Attempt status transition
        if investment.transition_to(new_status):
            db.session.commit()
            flash(f'Investment {action}ed successfully!', 'success')
        else:
            flash(f'Cannot {action} investment in its current status.', 'error')
        
        return redirect(url_for('farmer.investments'))
        
    except Exception as e:
        db.session.rollback()
        print(f"Investment Action Error: {str(e)}")
        flash('An error occurred while processing your request.', 'error')
        return redirect(url_for('farmer.investments'))

@farmer_bp.route('/farmer/soil-reports', methods=['GET', 'POST'])
@login_required
@farmer_required
def soil_reports():
    if request.method == 'POST':
        try:
            # Handle soil report upload
            report_file = request.files.get('report_file')
            if not report_file:
                flash('No file was uploaded.', 'error')
                return redirect(url_for('farmer.soil_reports'))
            
            if not report_file.filename:
                flash('No file was selected.', 'error')
                return redirect(url_for('farmer.soil_reports'))
            
            # Validate file type
            allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png'}
            if '.' not in report_file.filename or \
               report_file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
                flash('Invalid file type. Allowed types are: PDF, JPG, JPEG, PNG', 'error')
                return redirect(url_for('farmer.soil_reports'))
            
            # Create upload directory if it doesn't exist
            upload_dir = os.path.join('app', 'static', 'uploads', 'soil_reports')
            os.makedirs(upload_dir, exist_ok=True)
            
            filename = secure_filename(report_file.filename)
            file_path = os.path.join(upload_dir, filename)
            report_file.save(file_path)
            report_url = f'/static/uploads/soil_reports/{filename}'
            
            # Validate form data
            try:
                report = SoilReport(
                    farmer_id=current_user.id,
                    ph_level=float(request.form.get('ph_level')),
                    nitrogen_level=float(request.form.get('nitrogen_level')),
                    phosphorus_level=float(request.form.get('phosphorus_level')),
                    potassium_level=float(request.form.get('potassium_level')),
                    organic_matter=float(request.form.get('organic_matter')),
                    moisture_content=float(request.form.get('moisture_content')),
                    report_file_url=report_url,
                    notes=request.form.get('notes')
                )
            except ValueError as e:
                flash('Please enter valid numerical values for all soil measurements.', 'error')
                # Clean up the uploaded file if data validation fails
                if os.path.exists(file_path):
                    os.remove(file_path)
                return redirect(url_for('farmer.soil_reports'))
            
            db.session.add(report)
            db.session.commit()
            
            flash('Soil report uploaded successfully!', 'success')
            return redirect(url_for('farmer.soil_reports'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while uploading the soil report: {str(e)}', 'error')
            return redirect(url_for('farmer.soil_reports'))
    
    reports = SoilReport.query.filter_by(farmer_id=current_user.id).all()
    return render_template('farmer/soil_reports.html', reports=reports)

@farmer_bp.route('/farmer/schemes')
@login_required
@farmer_required
def schemes():
    active_schemes = GovScheme.query.filter_by(status='active').all()
    my_applications = SchemeApplication.query.filter_by(farmer_id=current_user.id).all()
    return render_template('farmer/schemes.html',
                         schemes=active_schemes,
                         applications=my_applications)

@farmer_bp.route('/farmer/apply-scheme/<int:scheme_id>', methods=['POST'])
@login_required
@farmer_required
def apply_scheme(scheme_id):
    scheme = GovScheme.query.get_or_404(scheme_id)
    
    # Check if already applied
    existing_application = SchemeApplication.query.filter_by(
        farmer_id=current_user.id,
        scheme_id=scheme_id
    ).first()
    
    if existing_application:
        flash('You have already applied for this scheme.', 'error')
        return redirect(url_for('farmer.schemes'))
    
    # Handle document upload
    documents = request.files.get('documents')
    documents_url = None
    if documents:
        filename = secure_filename(documents.filename)
        documents.save(os.path.join('app/static/uploads/scheme_docs', filename))
        documents_url = f'/static/uploads/scheme_docs/{filename}'
    
    application = SchemeApplication(
        farmer_id=current_user.id,
        scheme_id=scheme_id,
        documents_url=documents_url,
        notes=request.form.get('notes')
    )
    
    db.session.add(application)
    db.session.commit()
    
    flash('Application submitted successfully!', 'success')
    return redirect(url_for('farmer.schemes'))

@farmer_bp.route('/farmer/materials')
@login_required
@farmer_required
def materials():
    return render_template('farmer/materials.html')

@farmer_bp.route('/farmer/analytics')
@login_required
@farmer_required
def analytics():
    # Get sales data
    sales = Transaction.query.filter_by(
        seller_id=current_user.id,
        transaction_type='product'
    ).all()
    
    # Get investment data
    investments = Investment.query.filter_by(farmer_id=current_user.id).all()
    
    return render_template('farmer/analytics.html',
                         sales=sales,
                         investments=investments)

@farmer_bp.route('/farmer/products/<int:product_id>/delete', methods=['POST'])
@login_required
@farmer_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Ensure the product belongs to the current user
    if product.seller_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        # Delete the product image if it exists
        if product.image_url:
            image_path = os.path.join('app', 'static', product.image_url.lstrip('/'))
            if os.path.exists(image_path):
                os.remove(image_path)
        
        db.session.delete(product)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}) 