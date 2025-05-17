# Agriverse - Agricultural Management Platform

Agriverse is a comprehensive agricultural management platform connecting farmers, investors, and administrators. The platform facilitates product sales, investments, and agricultural resource management.

## Features

### Farmer Dashboard
- Sell Products
- Seek Investment
- View Performance Analytics
- Upload Soil Reports
- AI Crop & Market Predictor
- Buy/Exchange Materials
- Payment Processing
- Government Scheme Applications

### Investor Dashboard
- View & Purchase Products
- Invest in Farms
- Performance Analytics
- Farmer Profile Access
- Secure Payment Processing

### Admin Dashboard
- Transport Record Management
- Sales Monitoring
- Investment Tracking
- Platform Analytics
- AI Chatbot Monitoring
- User Management
- Goods Traceability

## Setup Instructions

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the root directory with the following variables:
   ```
   FLASK_APP=app
   FLASK_ENV=development
   SECRET_KEY=your-super-secret-key-change-this
   DATABASE_URL=sqlite:///agriverse.db

   # Email Configuration
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=True
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-app-specific-password

   # Stripe Configuration
   STRIPE_SECRET_KEY=your-stripe-secret-key
   STRIPE_PUBLISHABLE_KEY=your-stripe-publishable-key
   ```

5. Initialize the database:
   ```bash
   flask db init
   flask db migrate
   flask db upgrade
   ```

6. Run the application:
   ```bash
   flask run
   ```

## Project Structure

```
agriverse/
├── app/
│   ├── __init__.py
│   ├── models/
│   ├── routes/
│   ├── static/
│   └── templates/
├── migrations/
├── instance/
├── .env
├── .gitignore
├── config.py
├── requirements.txt
└── run.py
```

## Database Schema

The application uses SQLite for development and can be configured to use PlanetScale (MySQL) for production. The main tables include:
- Users (with role-based authentication)
- Products
- Investments
- Soil Reports
- Transactions
- Government Schemes

## Authentication

The platform implements role-based authentication with three user types:
- Farmer
- Investor
- Admin

Each role has specific access permissions and dedicated dashboards.

## API Endpoints

Documentation for the main API endpoints will be available at `/api/docs` when running the application.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 