from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request, session, send_file, jsonify
from flask_login import login_required, current_user
from ..models import Product, User, Transaction, db
from datetime import datetime
import stripe
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
import os

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'farmer':
            return redirect(url_for('farmer.dashboard'))
        elif current_user.role == 'investor':
            return redirect(url_for('investor.dashboard'))
        elif current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
    return render_template('main/index.html')

@main_bp.route('/about')
def about():
    return render_template('main/about.html')

@main_bp.route('/contact')
def contact():
    return render_template('main/contact.html')

@main_bp.route('/terms')
def terms():
    return render_template('main/terms.html')

@main_bp.route('/privacy')
def privacy():
    return render_template('main/privacy.html')

@main_bp.route('/marketplace')
@login_required
def marketplace():
    # Add role check for farmers
    if current_user.role == 'farmer':
        flash('Farmers do not have access to the marketplace.', 'error')
        return redirect(url_for('farmer.dashboard'))

    # Get all available products
    products = Product.query.filter_by(
        status='available'
    ).order_by(Product.created_at.desc()).all()
    
    # Group products by category
    products_by_category = {}
    for product in products:
        if product.category not in products_by_category:
            products_by_category[product.category] = []
        products_by_category[product.category].append(product)
    
    return render_template('main/marketplace.html',
                         products_by_category=products_by_category)

@main_bp.route('/select-payment/<int:product_id>', methods=['GET', 'POST'])
@login_required
def select_payment(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Get quantity and calculate total amount
    try:
        quantity = float(request.form.get('quantity', 1))
        total_amount = quantity * product.price
        
        # Validate quantity
        if quantity <= 0 or quantity > product.quantity:
            flash('Invalid quantity selected.', 'error')
            return redirect(url_for('main.marketplace'))
            
        if product.status != 'available':
            flash('This product is no longer available.', 'error')
            return redirect(url_for('main.marketplace'))
            
    except ValueError:
        flash('Invalid quantity format.', 'error')
        return redirect(url_for('main.marketplace'))
    
    return render_template('main/payment_selection.html',
                         product=product,
                         quantity=quantity,
                         total_amount=total_amount)

@main_bp.route('/checkout/<int:product_id>', methods=['POST'])
@login_required
def checkout(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Get form data
    try:
        quantity = float(request.form.get('quantity', 0))
        total_amount = float(request.form.get('total_amount', 0))
        payment_method = request.form.get('payment_method')
        
        # Validate quantity and amount
        if quantity <= 0 or quantity > product.quantity:
            flash('Invalid quantity selected.', 'error')
            return redirect(url_for('main.marketplace'))
        
        if total_amount <= 0:
            flash('Invalid amount.', 'error')
            return redirect(url_for('main.marketplace'))
            
        # Calculate total with processing fee
        total_with_fee = total_amount * 1.02  # 2% processing fee
        
        # Create pending transaction
        transaction = Transaction(
            buyer_id=current_user.id,
            seller_id=product.seller_id,
            product_id=product.id,
            quantity=quantity,
            amount=total_with_fee,
            payment_method=payment_method,
            transaction_type='product',  # Set transaction type for product purchase
            status='pending'
        )
        db.session.add(transaction)
        db.session.commit()
        
        # Process payment based on method
        if payment_method == 'wallet':
            if current_user.wallet_balance < total_with_fee:
                flash('Insufficient wallet balance.', 'error')
                return redirect(url_for('main.select_payment', product_id=product_id))
            
            try:
                # Deduct from buyer's wallet
                current_user.wallet_balance -= total_with_fee
                # Add to seller's wallet (excluding processing fee)
                product.seller.wallet_balance += total_amount
                
                # Update product quantity
                product.quantity -= quantity
                if product.quantity <= 0:
                    product.status = 'sold'
                
                # Mark transaction as completed
                transaction.status = 'completed'
                db.session.commit()
                
                return redirect(url_for('main.purchase_success', transaction_id=transaction.id))
                
            except Exception as e:
                db.session.rollback()
                flash('Error processing wallet payment. Please try again.', 'error')
                return redirect(url_for('main.select_payment', product_id=product_id))
                
        elif payment_method == 'upi':
            # Get UPI details
            upi_id = request.form.get('upi_id')
            # if not upi_id:
            #     flash('Please enter a valid UPI ID.', 'error')
            #     return redirect(url_for('main.select_payment', product_id=product_id))
            
            try:
                # Initialize UPI payment (integrate with UPI payment gateway)
                # For now, simulate successful payment

                # Mark transaction as completed immediately after getting UPI ID
                transaction.status = 'completed'
                db.session.commit()

                # Update product quantity
                product.quantity -= quantity
                if product.quantity <= 0:
                    product.status = 'sold'

                # Add amount to seller's wallet (excluding processing fee)
                product.seller.wallet_balance += total_amount

                # Move redirect here to ensure success page is shown
                return redirect(url_for('main.purchase_success', transaction_id=transaction.id))

            except Exception as e:
                db.session.rollback()
                flash('Error processing UPI payment. Please try again.', 'error')
                return redirect(url_for('main.select_payment', product_id=product_id))
                
        elif payment_method == 'card':
            try:
                # Initialize Stripe payment
                stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
                
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'usd',
                            'product_data': {
                                'name': f'{product.name} ({quantity} {product.unit})',
                                'description': f'Purchase from {product.seller.name}',
                            },
                            'unit_amount': int(total_with_fee * 100),  # Convert to cents
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    success_url=url_for('main.stripe_success', transaction_id=transaction.id, _external=True),
                    cancel_url=url_for('main.stripe_cancel', transaction_id=transaction.id, _external=True),
                )
                
                return redirect(checkout_session.url)
                
            except Exception as e:
                db.session.rollback()
                flash('Error initializing card payment. Please try again.', 'error')
                return redirect(url_for('main.select_payment', product_id=product_id))
                
        elif payment_method == 'cash':
            try:
                # Mark transaction as pending for cash on delivery
                transaction.status = 'completed'
                
                # Reserve the product quantity
                product.quantity -= quantity
                if product.quantity <= 0:
                    product.status = 'sold'
                
                db.session.commit()
                
                return redirect(url_for('main.purchase_success', transaction_id=transaction.id))
                
            except Exception as e:
                db.session.rollback()
                flash('Error processing cash payment. Please try again.', 'error')
                return redirect(url_for('main.select_payment', product_id=product_id))
        
        flash('Invalid payment method selected.', 'error')
        return redirect(url_for('main.select_payment', product_id=product_id))
        
    except ValueError:
        flash('Invalid payment data.', 'error')
        return redirect(url_for('main.select_payment', product_id=product_id))

@main_bp.route('/checkout/process/<int:product_id>', methods=['POST'])
@login_required
def process_checkout(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Get form data
    try:
        quantity = float(request.form.get('quantity', 0))
        total_amount = float(request.form.get('total_amount', 0))
        payment_method = request.form.get('payment_method')
        
        # Validate quantity and amount
        if quantity <= 0 or quantity > product.quantity:
            flash('Invalid quantity selected.', 'error')
            return redirect(url_for('main.checkout', product_id=product_id))
        
        if total_amount <= 0:
            flash('Invalid amount.', 'error')
            return redirect(url_for('main.checkout', product_id=product_id))
            
        # Calculate total with processing fee
        total_with_fee = total_amount * 1.02  # 2% processing fee
        
        # Create pending transaction
        transaction = Transaction(
            buyer_id=current_user.id,
            seller_id=product.seller_id,
            product_id=product.id,
            quantity=quantity,
            amount=total_with_fee,
            payment_method=payment_method,
            transaction_type='product',  # Set transaction type for product purchase
            status='pending'
        )
        db.session.add(transaction)
        db.session.commit()
        
        # Process payment based on method
        if payment_method == 'wallet':
            if current_user.wallet_balance < total_with_fee:
                flash('Insufficient wallet balance.', 'error')
                return redirect(url_for('main.checkout', product_id=product_id))
            
            try:
                # Deduct from buyer's wallet
                current_user.wallet_balance -= total_with_fee
                # Add to seller's wallet (excluding processing fee)
                product.seller.wallet_balance += total_amount
                
                # Update product quantity
                product.quantity -= quantity
                if product.quantity <= 0:
                    product.status = 'sold'
                
                # Mark transaction as completed
                transaction.status = 'completed'
                db.session.commit()
                
                return redirect(url_for('main.purchase_success', transaction_id=transaction.id))
                
            except Exception as e:
                db.session.rollback()
                flash('Error processing wallet payment. Please try again.', 'error')
                return redirect(url_for('main.checkout', product_id=product_id))
                
        elif payment_method == 'upi':
            # Get UPI details
            upi_id = request.form.get('upi_id')
            # if not upi_id:
            #     flash('Please enter a valid UPI ID.', 'error')
            #     return redirect(url_for('main.checkout', product_id=product_id))
            
            try:
                # Initialize UPI payment (integrate with UPI payment gateway)
                # For now, simulate successful payment
                
                # Update product quantity
                product.quantity -= quantity
                if product.quantity <= 0:
                    product.status = 'sold'
                
                # Add amount to seller's wallet (excluding processing fee)
                product.seller.wallet_balance += total_amount
                
                # Mark transaction as completed
                transaction.status = 'completed'
                db.session.commit()
                
                return redirect(url_for('main.purchase_success', transaction_id=transaction.id))
                
            except Exception as e:
                db.session.rollback()
                flash('Error processing UPI payment. Please try again.', 'error')
                return redirect(url_for('main.checkout', product_id=product_id))
                
        elif payment_method == 'bank':
            # Get bank details
            account_number = request.form.get('account_number')
            ifsc_code = request.form.get('ifsc_code')
            account_holder = request.form.get('account_holder')
            
            if not all([account_number, ifsc_code, account_holder]):
                flash('Please enter all bank account details.', 'error')
                return redirect(url_for('main.checkout', product_id=product_id))
            
            try:
                # Initialize bank transfer (integrate with bank payment gateway)
                # For now, simulate successful payment
                
                # Update product quantity
                product.quantity -= quantity
                if product.quantity <= 0:
                    product.status = 'sold'
                
                # Add amount to seller's wallet (excluding processing fee)
                product.seller.wallet_balance += total_amount
                
                # Mark transaction as completed
                transaction.status = 'completed'
                db.session.commit()
                
                return redirect(url_for('main.purchase_success', transaction_id=transaction.id))
                
            except Exception as e:
                db.session.rollback()
                flash('Error processing bank payment. Please try again.', 'error')
                return redirect(url_for('main.checkout', product_id=product_id))
                
        elif payment_method == 'card':
            try:
                # Initialize Stripe payment
                stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
                
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'usd',
                            'product_data': {
                                'name': f'{product.name} ({quantity} {product.unit})',
                                'description': f'Purchase from {product.seller.name}',
                            },
                            'unit_amount': int(total_with_fee * 100),  # Convert to cents
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    success_url=url_for('main.stripe_success', transaction_id=transaction.id, _external=True),
                    cancel_url=url_for('main.stripe_cancel', transaction_id=transaction.id, _external=True),
                )
                
                return redirect(checkout_session.url)
                
            except Exception as e:
                db.session.rollback()
                flash('Error initializing card payment. Please try again.', 'error')
                return redirect(url_for('main.checkout', product_id=product_id))
        
        flash('Invalid payment method selected.', 'error')
        return redirect(url_for('main.checkout', product_id=product_id))
        
    except ValueError:
        flash('Invalid payment data.', 'error')
        return redirect(url_for('main.checkout', product_id=product_id))

@main_bp.route('/checkout/stripe/success/<int:transaction_id>')
@login_required
def stripe_success(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    if transaction.buyer_id != current_user.id:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('main.marketplace'))
    
    try:
        # Update product quantity
        product = transaction.product
        product.quantity -= transaction.quantity
        if product.quantity <= 0:
            product.status = 'sold'
            
        # Add amount to seller's wallet (excluding processing fee)
        product.seller.wallet_balance += (transaction.amount / 1.02)  # Remove processing fee
        
        # Mark transaction as completed
        transaction.status = 'completed'
        db.session.commit()
        
        return redirect(url_for('main.purchase_success', transaction_id=transaction.id))
        
    except Exception as e:
        db.session.rollback()
        flash('Error processing payment. Please contact support.', 'error')
        return redirect(url_for('main.marketplace'))

@main_bp.route('/checkout/stripe/cancel/<int:transaction_id>')
@login_required
def stripe_cancel(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    if transaction.buyer_id != current_user.id:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('main.marketplace'))
    
    transaction.status = 'cancelled'
    db.session.commit()
    
    flash('Payment cancelled.', 'info')
    return redirect(url_for('main.marketplace'))

@main_bp.route('/purchase/success/<int:transaction_id>')
@login_required
def purchase_success(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    if transaction.buyer_id != current_user.id:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('main.marketplace'))
        
    return render_template('main/purchase_success.html', transaction=transaction)

@main_bp.route('/transactions')
@login_required
def transactions():
    # Get status filter
    status = request.args.get('status', 'all')
    
    # Query transactions
    query = Transaction.query.filter_by(buyer_id=current_user.id)
    
    # Apply status filter
    if status != 'all':
        query = query.filter_by(status=status)
    
    # Get transactions ordered by date
    transactions = query.order_by(Transaction.created_at.desc()).all()
    
    return render_template('main/transactions.html',
                         transactions=transactions)

@main_bp.route('/checkout-cart', methods=['GET', 'POST'])
@login_required
def checkout_cart():
    try:
        if request.method == 'GET':
            # Get cart data from session
            cart_items = session.get('cart_items')
            total_amount = session.get('cart_total')
            
            if not cart_items or not total_amount:
                flash('Cart is empty.', 'error')
                return redirect(url_for('main.marketplace'))
            
            return render_template('main/cart_payment.html',
                                 cart_items=cart_items,
                                 total_amount=total_amount)
        
        # POST request handling
        cart_data = request.form.get('cart')
        if not cart_data:
            flash('Cart is empty.', 'error')
            return redirect(url_for('main.marketplace'))
            
        cart_items = json.loads(cart_data)
        if not cart_items:
            flash('Cart is empty.', 'error')
            return redirect(url_for('main.marketplace'))
        
        # Calculate total amount
        total_amount = sum(item['price'] * item['quantity'] for item in cart_items)
        
        # Store cart in session for payment processing
        session['cart_items'] = cart_items
        session['cart_total'] = total_amount
        
        return render_template('main/cart_payment.html',
                             cart_items=cart_items,
                             total_amount=total_amount)
                             
    except Exception as e:
        flash('Error processing cart. Please try again.', 'error')
        return redirect(url_for('main.marketplace'))

@main_bp.route('/process-cart-payment', methods=['POST'])
@login_required
def process_cart_payment():
    try:
        # Get cart data from session
        cart_items = session.get('cart_items')
        total_amount = session.get('cart_total')
        
        if not cart_items or not total_amount:
            flash('Cart data not found. Please try again.', 'error')
            return redirect(url_for('main.marketplace'))
        
        payment_method = request.form.get('payment_method')
        total_with_fee = total_amount * 1.02  # 2% processing fee
        
        # Create transactions for each cart item
        transactions = []
        try:
            for item in cart_items:
                product = Product.query.get(item['id'])
                if not product or product.quantity < item['quantity']:
                    raise ValueError(f'Insufficient quantity for {item["name"]}')
                
                transaction = Transaction(
                    buyer_id=current_user.id,
                    seller_id=product.seller_id,
                    product_id=product.id,
                    quantity=item['quantity'],
                    amount=item['price'] * item['quantity'] * 1.02,  # Including processing fee
                    payment_method=payment_method,
                    transaction_type='product',
                    status='pending'
                )
                transactions.append(transaction)
                db.session.add(transaction)
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash('Error creating transactions. Please try again.', 'error')
            return redirect(url_for('main.marketplace'))
        
        # Process payment based on method
        if payment_method == 'upi':
            try:
                # Process UPI payment for all items
                for transaction in transactions:
                    product = transaction.product
                    
                    # Update product quantity
                    product.quantity -= transaction.quantity
                    if product.quantity <= 0:
                        product.status = 'sold'
                    
                    # Add amount to seller's wallet (excluding processing fee)
                    product.seller.wallet_balance += (transaction.amount / 1.02)
                    
                    # Mark transaction as completed
                    transaction.status = 'completed'
                
                db.session.commit()
                
                # Clear cart from session
                session.pop('cart_items', None)
                session.pop('cart_total', None)
                
                return redirect(url_for('main.purchase_success', transaction_id=transactions[0].id))
                
            except Exception as e:
                db.session.rollback()
                flash('Error processing UPI payment. Please try again.', 'error')
                return redirect(url_for('main.checkout_cart'))
                
        elif payment_method == 'card':
            try:
                # Initialize Stripe payment
                stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
                
                # Store transaction IDs in session for success handling
                session['pending_transaction_ids'] = [t.id for t in transactions]
                
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'usd',
                            'product_data': {
                                'name': 'Cart Payment',
                                'description': f'Payment for {len(cart_items)} items',
                            },
                            'unit_amount': int(total_with_fee * 100),  # Convert to cents
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    success_url=url_for('main.stripe_cart_success', _external=True),
                    cancel_url=url_for('main.stripe_cart_cancel', _external=True),
                )
                
                return redirect(checkout_session.url)
                
            except Exception as e:
                db.session.rollback()
                flash('Error initializing card payment. Please try again.', 'error')
                return redirect(url_for('main.checkout_cart'))
        
        elif payment_method == 'cod':
            try:
                # Process cash on delivery for all items
                for transaction in transactions:
                    product = transaction.product
                    
                    # Update product quantity
                    product.quantity -= transaction.quantity
                    if product.quantity <= 0:
                        product.status = 'sold'
                    
                    # Mark transaction as pending for cash on delivery
                    transaction.status = 'completed'
                
                db.session.commit()
                
                # Clear cart from session
                session.pop('cart_items', None)
                session.pop('cart_total', None)
                
                return redirect(url_for('main.purchase_success', transaction_id=transactions[0].id))
                
            except Exception as e:
                db.session.rollback()
                flash('Error processing cash payment. Please try again.', 'error')
                return redirect(url_for('main.checkout_cart'))
        
        flash('Invalid payment method selected.', 'error')
        return redirect(url_for('main.checkout_cart'))
        
    except Exception as e:
        flash('Error processing payment. Please try again.', 'error')
        return redirect(url_for('main.marketplace'))

@main_bp.route('/stripe-cart-success')
@login_required
def stripe_cart_success():
    try:
        # Get pending transaction IDs from session
        transaction_ids = session.get('pending_transaction_ids', [])
        if not transaction_ids:
            flash('No pending transactions found.', 'error')
            return redirect(url_for('main.marketplace'))
        
        # Complete all transactions
        transactions = Transaction.query.filter(Transaction.id.in_(transaction_ids)).all()
        
        for transaction in transactions:
            if transaction.buyer_id != current_user.id:
                continue
                
            product = transaction.product
            
            # Update product quantity
            product.quantity -= transaction.quantity
            if product.quantity <= 0:
                product.status = 'sold'
                
            # Add amount to seller's wallet (excluding processing fee)
            product.seller.wallet_balance += (transaction.amount / 1.02)
            
            # Mark transaction as completed
            transaction.status = 'completed'
        
        db.session.commit()
        
        # Clear cart and transaction IDs from session
        session.pop('cart_items', None)
        session.pop('cart_total', None)
        session.pop('pending_transaction_ids', None)
        
        return redirect(url_for('main.purchase_success', transaction_id=transactions[0].id))
        
    except Exception as e:
        db.session.rollback()
        flash('Error processing payment. Please contact support.', 'error')
        return redirect(url_for('main.marketplace'))

@main_bp.route('/stripe-cart-cancel')
@login_required
def stripe_cart_cancel():
    try:
        # Get pending transaction IDs from session
        transaction_ids = session.get('pending_transaction_ids', [])
        
        if transaction_ids:
            # Cancel all transactions
            Transaction.query.filter(
                Transaction.id.in_(transaction_ids),
                Transaction.buyer_id == current_user.id
            ).update({Transaction.status: 'cancelled'}, synchronize_session=False)
            
            db.session.commit()
        
        # Clear cart and transaction IDs from session
        session.pop('cart_items', None)
        session.pop('cart_total', None)
        session.pop('pending_transaction_ids', None)
        
        flash('Payment cancelled.', 'info')
        return redirect(url_for('main.marketplace'))
        
    except Exception as e:
        flash('Error cancelling payment.', 'error')
        return redirect(url_for('main.marketplace'))

def generate_invoice_pdf(transaction):
    """Generate a PDF invoice for a transaction."""
    # Create directory for invoices if it doesn't exist
    invoice_dir = os.path.join(current_app.root_path, 'static', 'invoices')
    os.makedirs(invoice_dir, exist_ok=True)
    
    # Generate unique filename
    filename = f'invoice_{transaction.id}_{datetime.now().strftime("%Y%m%d%H%M%S")}.pdf'
    filepath = os.path.join(invoice_dir, filename)
    
    # Create PDF
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter
    
    # Add header
    c.setFont("Helvetica-Bold", 24)
    c.drawString(1*inch, height-1*inch, "Agriverse")
    c.setFont("Helvetica", 12)
    c.drawString(1*inch, height-1.3*inch, "Invoice")
    
    # Add transaction details
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1*inch, height-2*inch, "Transaction Details")
    c.setFont("Helvetica", 10)
    c.drawString(1*inch, height-2.3*inch, f"Transaction ID: {transaction.id}")
    c.drawString(1*inch, height-2.5*inch, f"Date: {transaction.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    c.drawString(1*inch, height-2.7*inch, f"Status: {transaction.status.upper()}")
    
    # Add buyer and seller details
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1*inch, height-3.2*inch, "Buyer Details")
    c.setFont("Helvetica", 10)
    c.drawString(1*inch, height-3.5*inch, f"Name: {transaction.buyer.name}")
    c.drawString(1*inch, height-3.7*inch, f"Email: {transaction.buyer.email}")
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1*inch, height-4.2*inch, "Seller Details")
    c.setFont("Helvetica", 10)
    c.drawString(1*inch, height-4.5*inch, f"Name: {transaction.seller.name}")
    c.drawString(1*inch, height-4.7*inch, f"Email: {transaction.seller.email}")
    
    # Add product details
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1*inch, height-5.2*inch, "Product Details")
    c.setFont("Helvetica", 10)
    c.drawString(1*inch, height-5.5*inch, f"Product: {transaction.product.name}")
    c.drawString(1*inch, height-5.7*inch, f"Quantity: {transaction.quantity} {transaction.product.unit}")
    c.drawString(1*inch, height-5.9*inch, f"Price per unit: ${transaction.product.price:.2f}")
    
    # Add payment details
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1*inch, height-6.4*inch, "Payment Details")
    c.setFont("Helvetica", 10)
    subtotal = transaction.amount / 1.02  # Remove processing fee
    processing_fee = transaction.amount - subtotal
    c.drawString(1*inch, height-6.7*inch, f"Subtotal: ${subtotal:.2f}")
    c.drawString(1*inch, height-6.9*inch, f"Processing Fee (2%): ${processing_fee:.2f}")
    c.drawString(1*inch, height-7.1*inch, f"Total Amount: ${transaction.amount:.2f}")
    c.drawString(1*inch, height-7.3*inch, f"Payment Method: {transaction.payment_method.upper()}")
    
    # Add footer
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(1*inch, 1*inch, "This is a computer-generated invoice and does not require a signature.")
    
    c.save()
    return filename

@main_bp.route('/download-invoice/<int:transaction_id>')
@login_required
def download_invoice(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    
    # Check if user is authorized to download this invoice
    if transaction.buyer_id != current_user.id and transaction.seller_id != current_user.id:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('main.marketplace'))
    
    try:
        # Generate invoice
        filename = generate_invoice_pdf(transaction)
        
        # Send file
        return send_file(
            os.path.join(current_app.root_path, 'static', 'invoices', filename),
            as_attachment=True,
            download_name=f'invoice_{transaction.id}.pdf'
        )
        
    except Exception as e:
        flash('Error generating invoice. Please try again.', 'error')
        return redirect(url_for('main.transactions')) 