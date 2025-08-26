#!/bin/bash

# Start backend in background
cd backend
if [ ! -d "venv" ]; then
    python -m venv venv
fi
source venv/bin/activate
pip install -r ../requirements.txt
# Load environment variables and start Flask
python -c "
from dotenv import load_dotenv
load_dotenv('../.env')
from brilliance.api.v1 import app
app.run(host='0.0.0.0', port=8000, debug=False)
" &

# Start frontend
cd ../frontend
npm install
npm start
