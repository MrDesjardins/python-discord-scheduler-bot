#! /bin/bash
git pull origin main
source .venv/bin/activate
python3 -m pip install -r requirements.txt
sudo systemctl restart gametimescheduler.service
sudo systemctl status gametimescheduler.service