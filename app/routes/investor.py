from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from ..models import db, Product, Investment, Transaction, User
import stripe
from datetime import datetime
from functools import wraps

investor_bp = Blueprint('investor', __name__)

def investor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'investor':
            flash('Access denied. Investor privileges required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@investor_bp.route('/investor/dashboard')
@login_required
@investor_required
def dashboard():
    # Get active investments
    investments = Investment.query.filter_by(
        investor_id=current_user.id
    ).order_by(Investment.created_at.desc()).all()
    
    # Get recent transactions
    transactions = Transaction.query.filter_by(
        buyer_id=current_user.id
    ).order_by(Transaction.created_at.desc()).limit(5).all()
    
    # Calculate total investment and returns
    total_invested = sum(inv.amount for inv in investments)
    total_returns = sum(inv.actual_return for inv in investments 
                       if inv.status in ['active', 'completed'])
    
    return render_template('investor/dashboard.html',
                         investments=investments,
                         transactions=transactions,
                         total_invested=total_invested,
                         total_returns=total_returns)

@investor_bp.route('/investor/investments')
@login_required
@investor_required
def investments():
    try:
        # Get all available investment requests (excluding own requests)
        investment_requests = Investment.query.filter(
            Investment.status == 'seeking',
            Investment.farmer_id != current_user.id,  # Exclude own requests
            Investment.investor_id == None  # Only show requests without an investor
        ).order_by(Investment.created_at.desc()).all()
        
        print(f"Found {len(investment_requests)} available investment requests")
        
        # Get my investment offers
        my_offers = Investment.query.filter_by(
            investor_id=current_user.id,
            status='offered'
        ).order_by(Investment.created_at.desc()).all()
        
        print(f"Found {len(my_offers)} pending offers")
        
        # Get my active investments
        active_investments = Investment.query.filter_by(
            investor_id=current_user.id,
            status='active'
        ).order_by(Investment.created_at.desc()).all()
        
        print(f"Found {len(active_investments)} active investments")
        
        # Get my completed investments
        completed_investments = Investment.query.filter_by(
            investor_id=current_user.id,
            status='completed'
        ).order_by(Investment.created_at.desc()).all()
        
        print(f"Found {len(completed_investments)} completed investments")
        
        # Calculate total statistics
        total_invested = sum(inv.amount for inv in active_investments)
        total_completed = sum(inv.amount for inv in completed_investments)
        
        # Calculate returns including both completed and active investments
        active_returns = sum(inv.actual_return for inv in active_investments)
        completed_returns = sum(inv.actual_return for inv in completed_investments)
        total_returns = active_returns + completed_returns
        
        print(f"Total invested: ${total_invested}, Total completed: ${total_completed}, Total returns: ${total_returns}")
        
        return render_template('investor/investments.html',
                             investment_requests=investment_requests,
                             my_offers=my_offers,
                             active_investments=active_investments,
                             completed_investments=completed_investments,
                             total_invested=total_invested,
                             total_completed=total_completed,
                             total_returns=total_returns)
                             
    except Exception as e:
        print(f"Error in investments route: {str(e)}")
        flash('An error occurred while loading investments. Please try again.', 'error')
        return redirect(url_for('investor.dashboard'))

@investor_bp.route('/investor/farmers')
@login_required
@investor_required
def farmers():
    # Get all farmers
    farmers = User.query.filter_by(role='farmer').all()
    return render_template('investor/farmers.html', farmers=farmers)

@investor_bp.route('/investor/farmer/<int:farmer_id>')
@login_required
@investor_required
def farmer_profile(farmer_id):
    farmer = User.query.get_or_404(farmer_id)
    if farmer.role != 'farmer':
        flash('Invalid farmer profile.', 'error')
        return redirect(url_for('investor.farmers'))
    
    # Get farmer's products
    products = Product.query.filter_by(
        seller_id=farmer_id,
        status='available'
    ).order_by(Product.created_at.desc()).all()
    
    # Get all investments with this farmer
    investments = Investment.query.filter_by(
        investor_id=current_user.id,
        farmer_id=farmer_id
    ).order_by(Investment.created_at.desc()).all()
    
    # Calculate investment statistics
    total_invested = sum(inv.amount for inv in investments if inv.status in ['active', 'completed'])
    active_investments = sum(1 for inv in investments if inv.status == 'active')
    completed_investments = sum(1 for inv in investments if inv.status == 'completed')
    pending_offers = sum(1 for inv in investments if inv.status == 'offered')
    
    # Calculate average return
    completed_returns = [inv.amount * (1 + inv.interest_rate/100) 
                        for inv in investments if inv.status == 'completed']
    avg_return = (sum(completed_returns) / len(completed_returns)) if completed_returns else 0
    
    return render_template('investor/farmer_profile.html',
                         farmer=farmer,
                         products=products,
                         investments=investments,
                         total_invested=total_invested,
                         active_investments=active_investments,
                         completed_investments=completed_investments,
                         pending_offers=pending_offers,
                         avg_return=avg_return)

@investor_bp.route('/investor/invest', methods=['POST'])
@login_required
@investor_required
def invest():
    try:
        print("Form data received:", request.form)  # Debug print
        
        # Check if this is a direct farmer investment or an investment request response
        investment_id = request.form.get('investment_id')
        farmer_id = request.form.get('farmer_id')
        
        if not investment_id and not farmer_id:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Investment details are required.'})
            flash('Investment details are required.', 'error')
            return redirect(url_for('investor.investments'))
        
        # Get and validate numeric fields
        try:
            amount = float(request.form.get('amount', 0))
            duration = int(request.form.get('duration', 0))
            interest_rate = float(request.form.get('interest_rate', 0))
            description = request.form.get('description', '')
            print(f"Amount: {amount}, Duration: {duration}, Rate: {interest_rate}")  # Debug print
        except (ValueError, TypeError) as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Please enter valid numeric values for amount, duration, and interest rate.'})
            flash('Please enter valid numeric values for amount, duration, and interest rate.', 'error')
            return redirect(url_for('investor.investments'))
        
        # Validate numeric values
        if amount <= 0:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Investment amount must be greater than zero.'})
            flash('Investment amount must be greater than zero.', 'error')
            return redirect(url_for('investor.investments'))
        if duration <= 0:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Duration must be greater than zero.'})
            flash('Duration must be greater than zero.', 'error')
            return redirect(url_for('investor.investments'))
        if interest_rate <= 0 or interest_rate > 20:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Interest rate must be between 0% and 20%.'})
            flash('Interest rate must be between 0% and 20%.', 'error')
            return redirect(url_for('investor.investments'))
        
        if investment_id:
            # Handle investment request response
            investment = Investment.query.get_or_404(investment_id)
            if investment.status != 'seeking':
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': 'This investment request is no longer available.'})
                flash('This investment request is no longer available.', 'error')
                return redirect(url_for('investor.investments'))
                
            # Validate amount matches or exceeds requested amount
            if amount < investment.amount:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': 'Investment offer must meet or exceed the requested amount.'})
                flash('Investment offer must meet or exceed the requested amount.', 'error')
                return redirect(url_for('investor.investments'))
        else:
            # Handle direct farmer investment
            farmer = User.query.get_or_404(farmer_id)
            if farmer.role != 'farmer':
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': 'Invalid farmer selected.'})
                flash('Invalid farmer selected.', 'error')
                return redirect(url_for('investor.farmers'))
            
            # Create new investment
            investment = Investment(
                farmer_id=farmer_id,
                investor_id=current_user.id,
                amount=amount,
                duration=duration,
                interest_rate=interest_rate,
                description=description,
                status='offered'
            )
            db.session.add(investment)
        
        # Update existing investment if handling a request
        if investment_id:
            investment.investor_id = current_user.id
            investment.amount = amount
            investment.duration = duration
            investment.interest_rate = interest_rate
            if description:
                investment.description = description
        
        # Add transaction details
        transaction = Transaction(
            buyer_id=current_user.id,
            seller_id=investment.farmer_id,
            investment_id=investment.id if investment_id else None,
            amount=amount,
            transaction_type='investment',
            payment_method='direct',
            status='pending'
        )
        db.session.add(transaction)
        
        # Update investment status
        success = investment.transition_to('offered') if investment_id else True
        
        if success:
            try:
                db.session.commit()
                print(f"Investment created/updated successfully")  # Debug print
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': True, 'message': 'Investment offer submitted successfully!'})
                flash('Investment offer submitted successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                print(f"Database Error: {str(e)}")  # Debug print
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': 'Database error occurred. Please try again.'})
                flash('Database error occurred. Please try again.', 'error')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Unable to submit offer at this time.'})
            flash('Unable to submit offer at this time.', 'error')
        
        # Redirect based on where the request came from
        if farmer_id:
            return redirect(url_for('investor.farmer_profile', farmer_id=farmer_id))
        return redirect(url_for('investor.investments'))
        
    except Exception as e:
        db.session.rollback()
        print(f"Investment Error: {str(e)}")  # Debug print
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'An unexpected error occurred. Please try again later.'})
        flash('An unexpected error occurred. Please try again later.', 'error')
        return redirect(url_for('investor.investments'))

@investor_bp.route('/investor/buy-product/<int:product_id>', methods=['POST'])
@login_required
@investor_required
def buy_product(product_id):
    try:
        # Validate and get product
        product = Product.query.get_or_404(product_id)
        if product.status != 'available':
            flash('This product is no longer available.', 'error')
            return redirect(url_for('investor.investments'))
        
        # Validate and get quantity
        try:
            quantity = float(request.form.get('quantity', 1))
            if quantity <= 0:
                flash('Quantity must be greater than zero.', 'error')
                return redirect(url_for('investor.farmer_profile', farmer_id=product.seller_id))
        except (ValueError, TypeError):
            flash('Please enter a valid quantity.', 'error')
            return redirect(url_for('investor.farmer_profile', farmer_id=product.seller_id))
        
        # Check available quantity
        if quantity > product.quantity:
            flash(f'Only {product.quantity} {product.unit} available.', 'error')
            return redirect(url_for('investor.farmer_profile', farmer_id=product.seller_id))
        
        # Calculate total amount
        total_amount = product.price * quantity
        
        # Create transaction record
        transaction = Transaction(
            buyer_id=current_user.id,
            seller_id=product.seller_id,
            product_id=product_id,
            amount=total_amount,
            transaction_type='product',
            payment_method='stripe',
            status='pending'
        )
        
        db.session.add(transaction)
        
        # Update product quantity
        product.quantity -= quantity
        if product.quantity == 0:
            product.status = 'sold'
        
        db.session.commit()
        
        # Redirect to payment processing
        return redirect(url_for('investor.process_payment', transaction_id=transaction.id))
        
    except Exception as e:
        db.session.rollback()
        print(f"Purchase Error: {str(e)}")  # Log the error
        flash('An error occurred while processing your purchase. Please try again.', 'error')
        return redirect(url_for('investor.farmer_profile', farmer_id=product.seller_id))

@investor_bp.route('/investor/payment/<int:transaction_id>')
@login_required
@investor_required
def process_payment(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    if transaction.buyer_id != current_user.id:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('investor.dashboard'))
    
    # Check if Stripe is configured
    if not current_app.config.get('STRIPE_SECRET_KEY'):
        flash('Payment system is not configured. Please contact the administrator.', 'error')
        return redirect(url_for('investor.dashboard'))
    
    try:
        # Initialize Stripe payment
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'Transaction #{transaction.id}',
                    },
                    'unit_amount': int(transaction.amount * 100),  # Convert to cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('investor.payment_success', transaction_id=transaction.id, _external=True),
            cancel_url=url_for('investor.payment_cancel', transaction_id=transaction.id, _external=True),
        )
        
        return render_template('investor/payment.html',
                             checkout_session_id=session.id,
                             transaction=transaction)
                             
    except stripe.error.StripeError as e:
        flash(f'Payment processing error: {str(e)}', 'error')
        return redirect(url_for('investor.dashboard'))
    except Exception as e:
        flash('An unexpected error occurred. Please try again later.', 'error')
        return redirect(url_for('investor.dashboard'))

@investor_bp.route('/investor/payment/success/<int:transaction_id>')
@login_required
@investor_required
def payment_success(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    transaction.status = 'completed'
    db.session.commit()
    
    flash('Payment successful!', 'success')
    return redirect(url_for('investor.dashboard'))

@investor_bp.route('/investor/payment/cancel/<int:transaction_id>')
@login_required
@investor_required
def payment_cancel(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    transaction.status = 'failed'
    db.session.commit()
    
    flash('Payment cancelled.', 'error')
    return redirect(url_for('investor.dashboard'))

@investor_bp.route('/investor/analytics')
@login_required
@investor_required
def analytics():
    try:
        # Get all investments
        investments = Investment.query.filter_by(
            investor_id=current_user.id
        ).order_by(Investment.created_at.desc()).all()
        
        # Get all product purchases
        purchases = Transaction.query.filter_by(
            buyer_id=current_user.id,
            transaction_type='product'
        ).order_by(Transaction.created_at.desc()).all()
        
        # Calculate analytics with safe defaults
        total_invested = sum(inv.amount for inv in investments if inv.amount is not None)
        active_investments = sum(1 for inv in investments if inv.status == 'active')
        completed_investments = sum(1 for inv in investments if inv.status == 'completed')
        
        # Calculate returns using actual_return property
        total_returns = sum(inv.actual_return for inv in investments 
                          if inv.status in ['active', 'completed'])
        
        # Calculate ROI percentage
        roi_percentage = ((total_returns - total_invested) / total_invested * 100) if total_invested > 0 else 0
        
        return render_template('investor/analytics.html',
                             investments=investments,
                             purchases=purchases,
                             total_invested=total_invested,
                             active_investments=active_investments,
                             completed_investments=completed_investments,
                             total_returns=total_returns,
                             roi_percentage=roi_percentage)
                             
    except Exception as e:
        print(f"Analytics Error: {str(e)}")  # Log the error
        flash('An error occurred while loading analytics. Please try again.', 'error')
        return redirect(url_for('investor.dashboard')) 