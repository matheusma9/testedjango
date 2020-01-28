No Ubuntu:

sudo apt install python3-pip
sudo pip install virtualenv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
