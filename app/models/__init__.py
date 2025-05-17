from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'farmer', 'investor', 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    wallet_balance = db.Column(db.Float, default=0.0)  # User's wallet balance
    
    # Role-specific fields
    # Farmer fields
    farm_name = db.Column(db.String(100))
    farm_location = db.Column(db.String(200))
    farm_size = db.Column(db.Float)  # in acres
    
    # Investor fields
    company_name = db.Column(db.String(100))
    investment_capacity = db.Column(db.Float)
    
    # Relationships
    products = db.relationship('Product', backref='seller', lazy=True)
    investments_made = db.relationship('Investment', 
                                     backref='investor', 
                                     lazy=True,
                                     foreign_keys='Investment.investor_id')
    investments_received = db.relationship('Investment',
                                         backref='farmer',
                                         lazy=True,
                                         foreign_keys='Investment.farmer_id')
    soil_reports = db.relationship('SoilReport', backref='farmer', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)  # kg, tons, etc.
    category = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='available')  # available, sold, reserved

class Investment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    investor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Nullable for initial request
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    duration = db.Column(db.Integer, nullable=False)  # in months
    interest_rate = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='seeking')  # seeking, offered, active, completed, rejected, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)  # When the investment was completed
    description = db.Column(db.Text)
    
    # Status transition validation
    VALID_TRANSITIONS = {
        'seeking': ['offered', 'cancelled'],
        'offered': ['active', 'rejected', 'cancelled'],
        'active': ['completed', 'cancelled'],
        'completed': [],
        'rejected': [],
        'cancelled': []
    }
    
    def can_transition_to(self, new_status):
        """Check if the current status can transition to the new status."""
        return new_status in self.VALID_TRANSITIONS.get(self.status, [])
    
    def transition_to(self, new_status):
        """Attempt to transition to a new status."""
        if self.can_transition_to(new_status):
            self.status = new_status
            if new_status == 'completed':
                self.completed_at = datetime.utcnow()
            return True
        return False
    
    @property
    def expected_return(self):
        """Calculate the expected return amount."""
        return self.amount * (1 + self.interest_rate/100)
    
    @property
    def actual_return(self):
        """Calculate the actual return amount based on status."""
        if self.status == 'completed':
            return self.expected_return
        elif self.status == 'active':
            # Calculate pro-rated return based on time elapsed
            elapsed_months = (datetime.utcnow() - self.created_at).days / 30
            if elapsed_months > self.duration:
                return self.expected_return
            return self.amount * (1 + (self.interest_rate/100) * (elapsed_months / self.duration))
        return 0
    
    @property
    def return_percentage(self):
        """Calculate the return percentage."""
        if self.amount > 0:
            return ((self.actual_return - self.amount) / self.amount) * 100
        return 0
    
    @property
    def time_remaining(self):
        """Calculate time remaining in months for active investments."""
        if self.status == 'active':
            elapsed_months = (datetime.utcnow() - self.created_at).days / 30
            remaining = self.duration - elapsed_months
            return max(0, remaining)
        return 0
    
    @property
    def completion_percentage(self):
        """Calculate the completion percentage for active investments."""
        if self.status == 'active':
            elapsed_months = (datetime.utcnow() - self.created_at).days / 30
            return min(100, (elapsed_months / self.duration) * 100)
        elif self.status == 'completed':
            return 100
        return 0

class SoilReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    report_date = db.Column(db.DateTime, default=datetime.utcnow)
    ph_level = db.Column(db.Float)
    nitrogen_level = db.Column(db.Float)
    phosphorus_level = db.Column(db.Float)
    potassium_level = db.Column(db.Float)
    organic_matter = db.Column(db.Float)
    moisture_content = db.Column(db.Float)
    report_file_url = db.Column(db.String(200))
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    notes = db.Column(db.Text)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    investment_id = db.Column(db.Integer, db.ForeignKey('investment.id'))
    amount = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, nullable=True)  # Added quantity field
    transaction_type = db.Column(db.String(20), nullable=False)  # product, investment
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    payment_method = db.Column(db.String(20))
    payment_id = db.Column(db.String(100))  # Stripe/Razorpay payment ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    buyer = db.relationship('User', foreign_keys=[buyer_id], backref='purchases')
    seller = db.relationship('User', foreign_keys=[seller_id], backref='sales')
    product = db.relationship('Product', backref='transactions')
    investment = db.relationship('Investment', backref='transactions')

class GovScheme(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    eligibility_criteria = db.Column(db.Text)
    benefits = db.Column(db.Text)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='active')  # active, expired, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    applications = db.relationship('SchemeApplication', backref='scheme', lazy=True)

class SchemeApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    scheme_id = db.Column(db.Integer, db.ForeignKey('gov_scheme.id'), nullable=False)
    application_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    documents_url = db.Column(db.String(200))
    notes = db.Column(db.Text)
    
    farmer = db.relationship('User', backref='scheme_applications')

def create_sample_schemes():
    # PM-KISAN Scheme
    pm_kisan = GovScheme(
        name="PM-KISAN Scheme",
        description="Direct income support of Rs. 6,000 per year to eligible farmer families, payable in three equal installments of Rs. 2,000 each.",
        eligibility_criteria="- All landholding farmer families\n- Small and marginal farmers\n- Subject to certain exclusions",
        benefits="- Direct income support of Rs. 6,000 per year\n- Paid in three installments\n- Direct bank transfer\n- No intermediaries",
        start_date=datetime(2023, 4, 1),
        end_date=datetime(2024, 3, 31),
        status='active'
    )

    # Soil Health Card Scheme
    soil_health = GovScheme(
        name="Soil Health Card Scheme",
        description="A scheme to provide farmers with detailed reports on their soil quality and recommended fertilizers.",
        eligibility_criteria="- All farmers with agricultural land\n- Must provide soil samples\n- Must be registered with local agricultural office",
        benefits="- Free soil testing\n- Detailed soil health report\n- Fertilizer recommendations\n- Crop-specific recommendations",
        start_date=datetime(2023, 6, 1),
        end_date=datetime(2024, 5, 31),
        status='active'
    )

    # Pradhan Mantri Fasal Bima Yojana
    crop_insurance = GovScheme(
        name="Pradhan Mantri Fasal Bima Yojana",
        description="A comprehensive crop insurance scheme to protect farmers from crop losses due to natural calamities.",
        eligibility_criteria="- All farmers growing notified crops\n- Both loanee and non-loanee farmers\n- Must apply before crop season",
        benefits="- Low premium rates\n- Full insurance coverage\n- Quick claim settlement\n- Coverage for prevented sowing",
        start_date=datetime(2023, 7, 1),
        end_date=datetime(2024, 6, 30),
        status='active'
    )

    # National Agricultural Market (e-NAM)
    enam_scheme = GovScheme(
        name="National Agricultural Market (e-NAM)",
        description="An online trading platform for agricultural commodities to ensure better price discovery.",
        eligibility_criteria="- Registered farmers\n- Must have produce to sell\n- Must be willing to use digital platform",
        benefits="- Direct market access\n- Better price discovery\n- Reduced intermediaries\n- Online payment system",
        start_date=datetime(2023, 5, 1),
        end_date=datetime(2024, 4, 30),
        status='active'
    )

    return [pm_kisan, soil_health, crop_insurance, enam_scheme] 