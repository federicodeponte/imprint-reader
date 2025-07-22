#!/bin/bash

# Modal Deployment Script for Imprint Reader
echo "🚀 Deploying Imprint Reader to Modal..."

# Check if Modal CLI is installed
if ! command -v modal &> /dev/null; then
    echo "❌ Modal CLI not found. Installing..."
    pip install modal
fi

# Set environment variables
export GEMINI_API_KEY="AIzaSyCcV31i8YA-YKLPHC0gx5zdD50gBcjTxq4"

# Login to Modal (if not already logged in)
echo "🔐 Checking Modal authentication..."
modal token set --token-id $MODAL_TOKEN_ID --token-secret $MODAL_TOKEN_SECRET 2>/dev/null || echo "Please run 'modal token new' to authenticate"

# Deploy the app
echo "📦 Deploying to Modal..."
modal deploy modal_app.py

echo "✅ Deployment complete!"
echo ""
echo "🌐 Your API endpoint is now live at:"
echo "https://federicodeponte--imprint-reader-api-extract-imprints.modal.run"
echo ""
echo "📚 Usage example:"
echo 'curl -X POST https://federicodeponte--imprint-reader-api-extract-imprints.modal.run \\'
echo '  -H "Content-Type: application/json" \\'
echo '  -d '"'"'{"urls": ["https://example.com", "https://example2.com"]}'"'"
echo ""
echo "💾 Results are in CSV-compatible JSON format for Supabase!" 