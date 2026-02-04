#!/bin/bash

echo "=========================================="
echo "   DELTA CHAT - NT106 Setup Script"
echo "=========================================="
echo ""

# Check Python version
python_version=$(python3 --version 2>&1)
echo "✓ Python version: $python_version"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# Create .env file if not exists
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file and fill in your credentials!"
else
    echo ""
    echo "✓ .env file already exists"
fi

echo ""
echo "=========================================="
echo "   Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your credentials"
echo "2. Create Gmail App Passwords at: https://myaccount.google.com/apppasswords"
echo "3. Configure AWS S3 bucket"
echo "4. Run: python app.py"
echo ""
echo "To activate virtual environment later:"
echo "  source venv/bin/activate"
echo ""
