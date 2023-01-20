import datetime

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import asc
from werkzeug.utils import secure_filename
import time
import os
from datetime import datetime, date, timedelta, timezone
import enum

# Solve problem with images on edit_rooms
# Create stats and send it to email
# think about deployment
try:
    import ntplib

    client = ntplib.NTPClient()
    response = client.request('pool.ntp.org')
    print(f"NTP: {(datetime.fromtimestamp(response.tx_time, timezone.utc)).strftime( '%Y-%m-%d')}")
except Exception as err:
    print(err)
    print(datetime.now().strftime("%Y-%m-%d"))


class Providers(db.Model):
    __tablename__ = "providers"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100))
    photo = db.Column(db.String(300), nullable=True)
    room = db.relationship('Rooms', back_populates="provider")

    def __init__(self, full_name, photo=None):
        if photo is None:
            photo = '/static/person.png'
        self.full_name = full_name
        self.photo = photo


class MA(db.Model):
    __tablename__ = "MA"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100))
    photo = db.Column(db.String(300), nullable=True)
    # room = db.relationship('Rooms', back_populates="ma")

    def __init__(self, full_name, photo=None):
        if photo is None:
            photo = '/static/person.png'
        self.full_name = full_name
        self.photo = photo


class Rooms(db.Model):
    __tablename__ = "rooms"

    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(100))
    id_provider = db.Column(db.Integer, db.ForeignKey('providers.id'), nullable=True)
    provider = db.relationship('Providers', back_populates="room")
    id_ma = db.Column(db.Integer, db.ForeignKey(MA.id), nullable=True)
    id_ma_helper = db.Column(db.Integer, db.ForeignKey(MA.id), nullable=True)
    ma = db.relationship('MA', backref="room", uselist=False, foreign_keys=[id_ma])
    ma_helper = db.relationship('MA', backref="room2", uselist=False, foreign_keys=[id_ma_helper])

    # Refferer.
    schedule = db.relationship('Schedule', uselist=False , backref='rooms')

    def __init__(self, room_number, id_provider, id_ma, id_ma_helper):
        self.room_number = room_number
        self.id_provider = id_provider
        self.id_ma = id_ma
        self.id_ma_helper = id_ma_helper


class WorkingTime(enum.Enum):
    am = 'AM'
    pm = 'PM'
    evening = 'evening'


class Schedule(db.Model):
    __tablename__ = "schedule"
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), primary_key=True)
    sc_date = db.Column(db.Text)
    working_time = db.Column(db.Enum(WorkingTime), nullable=False)


@application.route('/')
def index():
    flag_generate = False
    date = request.args.get('date')
    if date is None:
        date = (datetime.now()).strftime("%Y-%m-%d")
    room_data = Rooms.query.join(Schedule).filter(Schedule.room_id == Rooms.id).filter(Schedule.sc_date == date).filter(Schedule.working_time == WorkingTime.am).all()
    room_data_pm = Rooms.query.join(Schedule).filter(Schedule.room_id == Rooms.id).filter(Schedule.sc_date == date).filter(Schedule.working_time == WorkingTime.pm).all()
    room_data_ev = Rooms.query.join(Schedule).filter(Schedule.room_id == Rooms.id).filter(Schedule.sc_date == date).filter(Schedule.working_time == WorkingTime.evening).all()

    if not room_data and not room_data_pm and not room_data_ev:
        generate_rooms(40, date)
        room_data = Rooms.query.join(Schedule).filter(Schedule.room_id == Rooms.id).filter(
            Schedule.sc_date == date).filter(Schedule.working_time == WorkingTime.am).all()
        room_data_pm = Rooms.query.join(Schedule).filter(Schedule.room_id == Rooms.id).filter(
            Schedule.sc_date == date).filter(Schedule.working_time == WorkingTime.pm).all()
        room_data_ev = Rooms.query.join(Schedule).filter(Schedule.room_id == Rooms.id).filter(Schedule.sc_date == date).filter(Schedule.working_time == WorkingTime.evening).all()

    provider_data = Providers.query.order_by(asc(Providers.id))
    ma_data = MA.query.order_by(asc(MA.id))
    return render_template("index.html",
                           room_data=room_data,
                           provider_data=provider_data,
                           ma_data=ma_data,
                           date=date,
                           flag=flag_generate,
                           room_data_pm=room_data_pm,
                           room_data_ev=room_data_ev)


@application.route('/generate_rooms/<date>')
def generate_rooms(amount, date):
    week_ago_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(weeks=1)).strftime("%Y-%m-%d")
    print(week_ago_date)
    room_data_old = Rooms.query.join(Schedule).filter(Schedule.room_id == Rooms.id).filter(Schedule.sc_date == week_ago_date).all()
    print(room_data_old)
    if room_data_old:
        for row in room_data_old:
            room = Rooms(row.room_number, row.id_provider, row.id_ma, row.id_ma_helper)
            db.session.add(room)
            db.session.commit()
            schedule = Schedule(room_id=room.id, sc_date=str(date), working_time=row.schedule.working_time)
            db.session.add(schedule)
            db.session.commit()

    else:
        name_dict = {29: 'COLPO', 30: 'UROGYN', 33: 'COLPO', 38: 'Centering', 39: 'GPU', 40: 'PPU'}
        if date is not None and amount is not None:
            for flag in [WorkingTime.am, WorkingTime.pm, WorkingTime.evening]:
                for i in range(1, amount + 1):
                    if i in name_dict:
                        room_number = str(i) + ' ' + name_dict[i]
                    else:
                        room_number = str(i)
                    id_provider = 1
                    id_ma = 1
                    id_ma_helper = 1
                    room = Rooms(room_number, id_provider, id_ma, id_ma_helper)
                    db.session.add(room)
                    db.session.commit()

                    schedule = Schedule(room_id=room.id, sc_date=str(date), working_time=flag)
                    db.session.add(schedule)
                    db.session.commit()
    return True


@application.route('/show')
def show():
    date = (datetime.now()).strftime("%Y-%m-%d")
    room_data = Rooms.query.join(Schedule).filter(Schedule.room_id == Rooms.id).filter(Schedule.sc_date == date).filter(
        Schedule.working_time == WorkingTime.am).all()
    room_data_unique = Rooms.query.join(Schedule).filter(Schedule.room_id == Rooms.id).filter(Schedule.sc_date == date).filter(
        Schedule.working_time ==  WorkingTime.am).group_by(Rooms.id_provider).order_by(Rooms.id)
    room_data_pm = Rooms.query.join(Schedule).filter(Schedule.room_id == Rooms.id).filter(
        Schedule.sc_date == date).filter(Schedule.working_time == WorkingTime.pm).all()
    room_data_unique_pm  = Rooms.query.join(Schedule).filter(Schedule.room_id == Rooms.id).filter(
        Schedule.sc_date == date).filter(Schedule.working_time == WorkingTime.pm).group_by(Rooms.id_provider).order_by(Rooms.id)
    if not room_data and not room_data_pm:
        generate_rooms(37, date)
        room_data = Rooms.query.join(Schedule).filter(Schedule.room_id == Rooms.id).filter(
            Schedule.sc_date == date).filter(Schedule.working_time == WorkingTime.am).all()
        room_data_pm = Rooms.query.join(Schedule).filter(Schedule.room_id == Rooms.id).filter(
            Schedule.sc_date == date).filter(Schedule.working_time == WorkingTime.pm).all()

    return render_template("show_page.html",
                           room_data=room_data,
                           room_data_unique=room_data_unique,
                           room_data_unique_pm=room_data_unique_pm,
                           date=date,
                           room_data_pm=room_data_pm)


@application.route('/providers')
def provider():
    all_data = Providers.query.order_by(asc(Providers.id))
    return render_template("providers.html", all_data=all_data)


@application.route('/ma')
def ma():
    all_data = MA.query.order_by(asc(MA.id))
    return render_template("ma.html", all_data=all_data)


@application.route('/insert_provider', methods=['POST'])
def insert_provider():
    if request.method == 'POST':
        name = request.form['name']
        photo = request.files['photo']
        photo_path = os.path.join(application.config['UPLOAD_FOLDER'], secure_filename(photo.filename))
        photo.save(photo_path.split('/', 1)[1])

        my_data = Providers(name, photo_path)
        db.session.add(my_data)
        db.session.commit()

        flash("Employee Inserted Successfully")
        return redirect(url_for('provider'))


@application.route('/insert_ma', methods=['POST'])
def insert_ma():
    if request.method == 'POST':
        name = request.form['name']
        photo = request.files['photo']
        photo_path = os.path.join(application.config['UPLOAD_FOLDER'], secure_filename(photo.filename))
        photo.save(photo_path.split('/', 1)[1])

        my_data = MA(name, photo_path)
        db.session.add(my_data)
        db.session.commit()

        flash("Employee Inserted Successfully")
        return redirect(url_for('ma'))


@application.route('/update_provider', methods=['POST'])
def update_provider():
    if request.method == "POST":
        my_date = Providers.query.get(request.form.get('id'))
        my_date.full_name = request.form['name']
        photo = request.files['photo']
        if photo.filename != '':
            os.remove(my_date.photo)
            photo_path = os.path.join(application.config['UPLOAD_FOLDER'], secure_filename(photo.filename))
            photo.save(photo_path.split('/', 1)[1])
            my_date.photo = photo_path

        db.session.commit()
        flash("Employee Updated Successfully")
        return redirect(url_for('provider'))


@application.route('/update_ma', methods=['POST'])
def update_ma():
    if request.method == "POST":
        my_date = MA.query.get(request.form.get('id'))
        my_date.full_name = request.form['name']
        photo = request.files['photo']
        print(photo)
        if photo.filename != '':
            os.remove(my_date.photo)
            photo_path = os.path.join(application.config['UPLOAD_FOLDER'], secure_filename(photo.filename))
            photo.save(photo_path.split('/', 1)[1])
            my_date.photo = photo_path

        db.session.commit()
        flash("Employee Updated Successfully")
        return redirect(url_for('ma'))


@application.route('/delete_provider/<id>/')
def delete_provider(id):
    if id != '1':
        my_data = Providers.query.get(id)
        try:
            os.remove(my_data.photo)
        except Exception:
            pass
        db.session.delete(my_data)
        db.session.commit()

        flash("Employee Data Deleted Successfully")
    return redirect(url_for('provider'))

@application.route('/delete_ma/<id>/')
def delete_ma(id):
    print(id)
    if id != '1':
        my_data = MA.query.get(id)
        try:
            os.remove(my_data.photo)
        except Exception:
            pass
        db.session.delete(my_data)
        db.session.commit()
        flash("Employee Data Deleted Successfully")
    else:
        print("Yeah")
    return redirect(url_for('ma'))


# @application.route('/create_room/<date>', methods=['POST'])
# def create_room(date):
#     if request.method == "POST":
#         room_number = request.form['room_number']
#         id_provider = request.form['provider']
#         id_ma = request.form['ma']
#         id_ma_helper = request.form['ma_helper']
#         working_time = request.form['working_time']
#
#         my_data = Rooms(room_number, id_provider, id_ma, id_ma_helper)
#         db.session.add(my_data)
#         db.session.commit()
#
#         schedule = Schedule(room_id=my_data.id, sc_date=str(date), working_time=working_time)
#         db.session.add(schedule)
#         db.session.commit()
#         flash("Room Created Successfully")
#         return redirect(request.referrer)


@application.route('/edit_rooms/<date>')
def edit_rooms(date):
    room_data = Rooms.query.join(Schedule).filter(Schedule.room_id == Rooms.id).filter(Schedule.sc_date == date).filter(Schedule.working_time == WorkingTime.am).all()
    room_data_pm = Rooms.query.join(Schedule).filter(Schedule.room_id == Rooms.id).filter(Schedule.sc_date == date).filter(Schedule.working_time == WorkingTime.pm).all()
    room_data_ev = Rooms.query.join(Schedule).filter(Schedule.room_id == Rooms.id).filter(Schedule.sc_date == date).filter(Schedule.working_time == WorkingTime.evening).all()
    provider_data = Providers.query.order_by(asc(Providers.id))
    ma_data = MA.query.order_by(asc(MA.id))

    return render_template("edit_rooms.html", 
                           room_data=room_data,
                           room_data_pm=room_data_pm,
                           room_data_ev=room_data_ev,
                           provider_data=provider_data,
                           ma_data=ma_data,
                           date=date)


@application.route('/edited_rooms/<date>', methods=["POST"])
def update_rooms(date):
    if request.method == 'POST':
        r = RequestEditedRoom(request)
        for el in range(len(r.id)):
            my_date = Rooms.query.get(r.id[el])
            my_date.id_provider = r.p[el]
            my_date.id_ma = r.ma[el]
            my_date.id_ma_helper = r.ma_helper[el]
            sc = Schedule.query.get(r.id[el])
            sc.sc_date = date
            db.session.commit()

        flash("Rooms Updated Successfully")
        return redirect(url_for('index'))


@application.route('/delete_room/<id>/')
def delete_room(id):
    my_data = Rooms.query.get(id)
    sc = Schedule.query.get(id)
    db.session.delete(sc)

    db.session.delete(my_data)
    db.session.commit()

    flash("Room Deleted Successfully")
    return redirect(request.referrer)


class RequestEditedRoom:
    def __init__(self, r):
        self.id = []
        self.p = []
        self.ma = []
        self.ma_helper = []

        self.id += r.form.getlist("id")
        self.p += r.form.getlist("provider")
        self.ma += r.form.getlist("ma")
        self.ma_helper += r.form.getlist("ma_helper")

def createNoneUsers(model):
    if model.query.get(1) is None:
        m = model('None')
        db.session.add(m)
        db.session.commit()
        return
    else:
        return
    
def create_app():
    global application = Flask(__name__)
    application.secret_key = "BRUH"

    path = os.path.abspath(os.path.dirname(__file__))
    application.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///" + os.path.join(path, 'database.sqlite')
    application.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Why?
    application.config['UPLOAD_FOLDER'] = "/static/images"

    global db = SQLAlchemy(application)
    if not os.path.isfile('database.sqlite'):
        db.create_all()
    createNoneUsers(Providers)
    createNoneUsers(MA)
    application.run(debug=True)
