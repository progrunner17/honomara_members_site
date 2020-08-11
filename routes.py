from itertools import groupby
import itertools
import datetime
from flask import render_template, request, abort, redirect, url_for, flash
from honomara_members_site import app, db
from honomara_members_site.login import login_check
from honomara_members_site.model import *
from sqlalchemy import func
from sqlalchemy.sql import text
from honomara_members_site.form import *
from flask_login import login_required, login_user, logout_user
from honomara_members_site.util import current_school_year


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login/', methods=["GET", "POST"])
def login():
    if(request.method == "POST"):
        username = request.form["username"]
        password = request.form["password"]
        if login_check(username, password):
            return redirect(url_for('index'))
        else:
            return abort(401)
    else:
        return render_template("login.html")


@app.route('/logout/')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/member/')
@login_required
def member():
    members = Member.query.order_by(Member.year.desc(), Member.family_kana)
    return render_template('member.html', members=members, groupby=groupby, key=(lambda x: x.year))


@app.route('/member/<int:member_id>')
@login_required
def member_individual(member_id):
    m = Member.query.get(member_id)
    if m is None:
        return abort(404)

    m.results.sort(key=lambda x: x.race.date, reverse=False)
    raw_results = list(
        filter(lambda x: x.race_type.show_name == 'フルマラソン', m.results))

    results = []
    races = []
    for r in raw_results:
        results += [{'x': "{:%Y/%m/%d}".format(r.race.date), 'y': r.result}]
        races += [r.race.race_name]

    return render_template('member_individual.html', member=m, races=str(races), results=str(results))


@app.route('/member/edit', methods=['GET', 'POST'])
@login_required
def member_edit():
    form = MemberForm(formdata=request.form)
    form.visible.data = request.form.get('visible') != 'False'

    if form.validate_on_submit():
        return redirect(url_for('member_confirm'), code=307)

    if request.args.get('method') == 'PUT':
        id = int(request.args.get('id'))
        member = Member.query.get(id)
        form = MemberForm(obj=member)
        form.method.data = 'PUT'
    else:
        form.method.data = 'POST'
    return render_template('member_edit.html', form=form)


@app.route('/member/confirm', methods=['POST'])
@login_required
def member_confirm():
    form = MemberForm(formdata=request.form)
    form.visible.data = request.form.get('visible') != 'False'

    if request.form.get('submit') == 'キャンセル':
        return redirect(url_for('user'))

    if form.validate_on_submit() and request.form.get('confirmed'):
        if request.form.get('method') == 'DELETE':
            member = Member.query.get(form.id.data)
            db.session.delete(member)
            db.session.commit()
            flash('メンバー："{} {}"の削除が完了しました'.format(
                member.family_name, member.first_name), 'danger')
        elif request.form.get('method') == 'PUT':
            member = Member.query.get(form.id.data)
            form.populate_obj(member)
            db.session.commit()
            flash('メンバー："{} {}"の更新が完了しました'.format(
                member.family_name, member.first_name), 'warning')
        elif request.form.get('method') == 'POST':
            member = Member()
            form.populate_obj(member)
            member.id = None
            db.session.add(member)
            db.session.commit()
            flash('メンバー："{} {}"の更新が完了しました'.format(
                member.family_name, member.first_name), 'info')

        return redirect(url_for('member'))
    else:
        if request.form.get('method') == 'DELETE':
            member = Member.query.get(form.id.data)
            form = MemberForm(obj=member)
        return render_template('member_confirm.html', form=form)


@app.route('/training/')
def training():
    per_page = 20
    page = request.args.get('page') or 1
    page = max([1, int(page)])
    trainings = Training.query
    keywords = request.args.get('keyword')
    day_from = request.args.get('from')
    day_until = request.args.get('until')
    if keywords is not None:
        for keyword in keywords.split(','):
            keyword = keyword.replace(' ', '')
            keyword = keyword.replace('　', '')
            trainings = trainings.filter(Training.comment.contains(keyword))
    if day_from is not None and day_from != "":
        day_from = datetime.datetime.strptime(day_from, '%Y-%m-%d')
        trainings = trainings.filter(Training.date >= day_from)
    if day_until is not None and day_until != "":
        day_until = datetime.datetime.strptime(day_until, '%Y-%m-%d')
        trainings = trainings.filter(Training.date <= day_until)
    if request.args.get('submit') == "検索":
        count = trainings.count()
        if count > 0:
            flash('{}件ヒットしました'.format(count), 'info')
        else:
            flash('ヒットしませんでした', 'danger')
    trainings = trainings.order_by(
        Training.date.desc()).paginate(page, per_page)
    return render_template('training.html', pagination=trainings)


@app.route('/training/edit', methods=['GET', 'POST'])
@login_required
def training_edit():
    form = TrainingForm(formdata=request.form)

    if form.validate_on_submit():
        return redirect(url_for('training_confirm'), code=307)

    if request.args.get('method') == 'PUT':
        id = int(request.args.get('id'))
        training = Training.query.get(id)
        form = TrainingForm(obj=training)
        form.method.data = 'PUT'
        form.participants1.data = [m.id for m in training.participants]
        form.participants2.data = [m.id for m in training.participants]
        form.participants3.data = [m.id for m in training.participants]
        form.participants4.data = [m.id for m in training.participants]
        form.participants.data = [m.id for m in training.participants]
    else:
        form.method.data = 'POST'

    return render_template('training_edit.html', form=form)


@app.route('/training/confirm', methods=['POST'])
@login_required
def training_confirm():
    app.logger.info(request.form)
    form = TrainingForm(formdata=request.form)
    app.logger.info(form.participants.data)

    if request.form.get('submit') == 'キャンセル':
        return redirect(url_for('training'))

    form.participants.data = form.participants1.data +\
        form.participants2.data +\
        form.participants3.data +\
        form.participants4.data +\
        form.participants.data

    if form.participants.data:
        form.participants.data = [Member.query.get(
            int(member_id)) for member_id in form.participants.data]

    if form.validate_on_submit() or request.form.get('confirmed'):
        if request.form.get('method') == 'DELETE':
            training = Training.query.get(form.id.data)
            db.session.delete(training)
            db.session.commit()
            flash('練習録: "{}" の削除が完了しました'.format(training.title), 'danger')
        elif request.form.get('method') == 'PUT':
            training = Training.query.get(form.id.data)
            training.title = training.title.encode(
                'euc-jp', errors='xmlcharrefreplace').decode('euc-jp')
            training.comment = training.comment.encode(
                'euc-jp', errors='xmlcharrefreplace').decode('euc-jp')
            form.populate_obj(training)
            db.session.commit()
            flash('練習録: "{}" の更新が完了しました'.format(training.title), 'warning')
        elif request.form.get('method') == 'POST':
            training = Training()
            form.populate_obj(training)
            training.title = training.title.encode(
                'euc-jp', errors='xmlcharrefreplace').decode('euc-jp')
            training.comment = training.comment.encode(
                'euc-jp', errors='xmlcharrefreplace').decode('euc-jp')
            training.id = None
            db.session.add(training)
            db.session.commit()
            flash('練習録: "{}" の登録が完了しました'.format(training.title), 'info')
        return redirect(url_for('training'))
    else:
        if request.form.get('method') == 'DELETE':
            training = Training.query.get(form.id.data)
            form = TrainingForm(obj=training)
            form.participants.data = training.participants
        app.logger.info(form.participants.data)

        return render_template('training_confirm.html', form=form)


@app.route('/after/')
def after():
    per_page = 40
    page = request.args.get('page') or 1
    page = max([1, int(page)])
    afters = After.query
    stage = request.args.get('stage')
    keywords = request.args.get('keyword')
    day_from = request.args.get('from')
    day_until = request.args.get('until')
    if stage is not None and stage != "":
        afters = afters.filter(After.after_stage == int(stage))
    if keywords is not None:
        for keyword in keywords.split(','):
            keyword = keyword.replace(' ', '')
            keyword = keyword.replace('　', '')
            afters = afters.filter(After.comment.contains(keyword))
    if day_from is not None and day_from != "":
        day_from = datetime.datetime.strptime(day_from, '%Y-%m-%d')
        afters = afters.filter(After.date >= day_from)
    if day_until is not None and day_until != "":
        day_until = datetime.datetime.strptime(day_until, '%Y-%m-%d')
        afters = afters.filter(After.date <= day_until)
    if request.args.get('submit') == "検索":
        count = afters.count()
        if count > 0:
            flash('{}件ヒットしました'.format(count), 'info')
        else:
            flash('ヒットしませんでした', 'danger')
    afters = afters.order_by(After.date.desc()).paginate(page, per_page)
    return render_template('after.html', pagination=afters)


@app.route('/after/edit', methods=['GET', 'POST'])
@login_required
def after_edit():
    form = AfterForm(formdata=request.form)
    keyword = request.args.get('keyword')

    if form.validate_on_submit():
        return redirect(url_for('after_confirm'), code=307)

    if request.args.get('method') == 'PUT':
        id = int(request.args.get('id'))
        after = After.query.get(id)
        form = AfterForm(obj=after)
        form.participants1.data = [m.id for m in after.participants]
        form.participants2.data = [m.id for m in after.participants]
        form.participants3.data = [m.id for m in after.participants]
        form.participants4.data = [m.id for m in after.participants]
        form.participants.data = [m.id for m in after.participants]
        form.restaurant.data = after.restaurant.id
        form.method.data = 'PUT'
    else:
        if keyword is not None:
            form.restaurant.choices = [(r.id, "{}({})".format(
                r.name, r.place)) for r in Restaurant.query.filter(Restaurant.name.contains(keyword)).order_by(Restaurant.score.desc()).all()]
        form.method.data = 'POST'

    return render_template('after_edit.html', form=form)


@app.route('/after/confirm', methods=['POST'])
@login_required
def after_confirm():
    form = AfterForm(formdata=request.form)
    app.logger.info(request.form)
    if request.form.get('submit') == 'キャンセル':
        return redirect(url_for('after'))

    form.participants.data = form.participants1.data +\
        form.participants2.data +\
        form.participants3.data +\
        form.participants4.data +\
        form.participants.data

    if form.participants.data:
        form.participants.data = [Member.query.get(
            int(member_id)) for member_id in form.participants.data]

    if form.restaurant.data:
        form.restaurant.data = Restaurant.query.get(int(form.restaurant.data))

    app.logger.info(form.restaurant.data)
    if form.validate_on_submit() or request.form.get('confirmed'):
        if request.form.get('method') == 'DELETE':
            after = After.query.get(form.id.data)
            db.session.delete(after)
            db.session.commit()
            flash('アフター録: "{}" の削除が完了しました'.format(after.title), 'danger')

        elif request.form.get('method') == 'PUT':
            after = After.query.get(form.id.data)
            after.title = after.title.encode(
                'euc-jp', errors='xmlcharrefreplace').decode('euc-jp')
            after.comment = after.comment.encode(
                'euc-jp', errors='xmlcharrefreplace').decode('euc-jp')
            form.populate_obj(after)
            db.session.commit()
            flash('アフター録: "{}" の更新が完了しました'.format(after.title), 'warning')

        elif request.form.get('method') == 'POST':
            after = After()
            form.populate_obj(after)
            after.title = after.title.encode(
                'euc-jp', errors='xmlcharrefreplace').decode('euc-jp')
            after.comment = after.comment.encode(
                'euc-jp', errors='xmlcharrefreplace').decode('euc-jp')
            after.id = None
            db.session.add(after)
            db.session.commit()
            flash('アフター録: "{}" の登録が完了しました'.format(after.title), 'info')

        return redirect(url_for('after'))
    else:
        if request.form.get('method') == 'DELETE':
            after = After.query.get(form.id.data)
            form = AfterForm(obj=after)
            form.participants1.data = after.participants
            form.participants2.data = after.participants
            form.participants3.data = after.participants
            form.participants4.data = after.participants
            form.participants.data = after.participants
            form.restaurant.data = after.restaurant
        return render_template('after_confirm.html', form=form)


@app.route('/result/')
def result():
    per_page = 40
    page = request.args.get('page') or 1
    page = max([1, int(page)])
    results = Race.query.join(Course).order_by(
        Race.date.desc(), text("course.competition_id")).paginate(page, per_page)
    return render_template('result.html', pagination=results, groupby=groupby, key=(lambda x: x.race_type.show_name))


@app.route('/competition/')
def competition():
    competitions = Competition.query.order_by(
        Competition.place)
    return render_template('competition.html', competitions=competitions)


@app.route('/competition/<int:competition_id>')
@login_required
def competition_individual(competition_id):
    c = Competition.query.get(competition_id)
    if c is None:
        return abort(404)

    return render_template('competition_individual.html', competition=c)


@app.route('/competition/edit', methods=['GET', 'POST'])
@login_required
def competition_edit():
    form = CompetitionForm(formdata=request.form)
#     form.visible.data = request.form.get('visible') != 'False'

    if form.validate_on_submit():
        return redirect(url_for('competition_confirm'), code=307)

    if request.args.get('method') == 'PUT':
        id = int(request.args.get('id'))
        competition = Competition.query.get(id)
        form = CompetitionForm(obj=competition)
        form.method.data = 'PUT'
    else:
        form.method.data = 'POST'
    return render_template('competition_edit.html', form=form)


@app.route('/competition/confirm', methods=['POST'])
@login_required
def competition_confirm():
    form = CompetitionForm(formdata=request.form)
#     form.visible.data = request.form.get('visible') != 'False'

    if request.form.get('submit') == 'キャンセル':
        return redirect(url_for('competition'))

    if form.validate_on_submit() and request.form.get('confirmed'):
        if request.form.get('method') == 'DELETE':
            competition = Competition.query.get(form.id.data)
            db.session.delete(competition)
            db.session.commit()
            flash('大会："{}"の削除が完了しました'.format(competition.name), 'danger')
        elif request.form.get('method') == 'PUT':
            competition = Competition.query.get(form.id.data)
            form.populate_obj(competition)
            db.session.commit()
            flash('大会："{}"の更新が完了しました'.format(competition.name), 'warning')
        elif request.form.get('method') == 'POST':
            competition = Competition()
            form.populate_obj(competition)
            competition.id = None
            db.session.add(competition)
            db.session.commit()
            flash('大会："{}"の登録が完了しました'.format(competition.name), 'warning')

        return redirect(url_for('competition'))
    else:
        if request.form.get('method') == 'DELETE':
            competition = Competition.query.get(form.id.data)
            form = CompetitionForm(obj=competition)
        return render_template('competition_confirm.html', form=form)


@app.route('/course/edit', methods=["GET", "POST"])
def course_edit():
    form = CourseForm(formdata=request.form)
    if form.validate_on_submit():
        return redirect(url_for('course_confirm'), code=307)

    competition_id = request.args.get("competition_id", default=-1, type=int)

    if competition_id == -1:
        return render_template('template_message.html', message='大会指定が無効です<br>先に大会を作成してください')
    #
    form.competition = Competition.query.get(competition_id)

    if form.validate_on_submit():
        return redirect(url_for('course_confirm'), code=307)

    if request.args.get('method') == 'PUT':
        return abort(401)
#         id = int(request.args.get('id'))
#         course = course.query.get(id)
#         form = courseForm(obj=course)
#         form.method.data = 'PUT'
    else:
        form.method.data = 'POST'
    return render_template('course_edit.html', form=form)


@app.route('/course/confirm', methods=["POST"])
def course_confirm():
    form = CourseForm(formdata=request.form)
#     form.visible.data = request.form.get('visible') != 'False'

    if request.form.get('submit') == 'キャンセル':
        return redirect(url_for('competition'))

    if form.validate_on_submit() and request.form.get('confirmed'):
        if request.form.get('method') == 'DELETE':
            #             competition = Competition.query.get(form.id.data)
            #             db.session.delete(competition)
            #             db.session.commit()
            #             flash('大会："{}"の削除が完了しました'.format(competition.name), 'danger')
            return abort(401)
        elif request.form.get('method') == 'PUT':
            #             competition = Competition.query.get(form.id.data)
            #             form.populate_obj(competition)
            #             db.session.commit()
            #             flash('大会："{}"の更新が完了しました'.format(competition.name), 'warning')
            return abort(401)
        elif request.form.get('method') == 'POST':
            course = Course()
            form.populate_obj(course)
            course.id = None
            db.session.add(course)
            db.session.commit()
            flash('コース："{}"の登録が完了しました'.format(competition.name), 'warning')

        return redirect(url_for('competition'))
    else:
        #         if request.form.get('method') == 'DELETE':
        #             competition = Competition.query.get(form.id.data)
        #             form = CompetitionForm(obj=competition)
        #         return render_template('competition_confirm.html', form=form)
        return render_template('')


@app.route('/race/')
def race():
    return redirect(url_for('result'))


@app.route('/race/edit', methods=['GET', 'POST'])
@login_required
def race_edit():
    app.logger.info(request.form)
    #     Race.competition.choices = [
    #         (r.race_name, r.race_name) for r in RaceBase.query.all()]
    form = RaceForm(formdata=request.form)

#     if form.validate_on_submit():
#         return redirect(url_for('race_confirm'), code=307)
#     form.race_name.choices = [
#         (r.race_name, r.race_name) for r in RaceBase.query.all()]
    if request.method == "GET":
        course_id = request.args.get('course_id')
        competition_id = request.args.get('competition_id')
        if course_id is not None:
            course = Course.query.get(course_id)
            form.course = course
        elif competition_id is not None:
            competition = Competition.query.get(competition_id)
            form.course.choices = [
                (c.id, "{} {}km".format(competition.name, c.distance)) for c in competition.courses
            ]

    elif request.args.get('method') == 'PUT':
        id = int(request.args.get('id'))
        race = Race.query.get(id)
        form = RaceForm(obj=race)
        form.method.data = 'PUT'
    else:
        form.method.data = 'POST'

    return render_template('race_edit.html', form=form)


@app.route('/race/confirm', methods=['POST'])
@login_required
def race_confirm():
    form = RaceForm(formdata=request.form)
    app.logger.info(request.form)

    if request.form.get('submit') == 'キャンセル':
        return redirect(url_for('user'))

    if form.validate_on_submit() and request.form.get('confirmed'):
        if request.form.get('method') in ['PUT', 'POST'] and len(form.race_name_option.data) > 3:
            rb = RaceBase.query.get(form.race_name_option.data)
            if rb is None:
                rb = RaceBase()
                rb.race_name = form.race_name_option.data
                db.session.add(rb)
                db.session.commit()
                app.logger.info('register race_base {}'.format(rb))
            form.race_name.data = rb.race_name

        if request.form.get('method') == 'DELETE':
            race = Race.query.get(form.id.data)
            db.session.delete(race)
            db.session.commit()
            flash('大会: "{}({})" の削除が完了しました'.format(
                race.race_name, race.date), 'danger')

        elif request.form.get('method') == 'PUT':
            race = Race.query.get(form.id.data)
            form.populate_obj(race)
            db.session.commit()
            flash('大会: "{}({})" の更新が完了しました'.format(
                race.race_name, race.date), 'warning')

        elif request.form.get('method') == 'POST':
            race = Race()
            form.populate_obj(race)
            race.id = None
            db.session.add(race)
            db.session.commit()
            flash('大会: "{}({})" の登録が完了しました'.format(
                race.race_name, race.date), 'info')

        return redirect(url_for('race'))
    else:
        if request.form.get('method') == 'DELETE':
            race = Race.query.get(form.id.data)
            form = RaceForm(obj=race)
        return render_template('race_confirm.html', form=form)


@app.route('/result/edit', methods=['GET', 'POST'])
@login_required
def result_edit():
    #     form = ResultForm(formdata=request.form)
    form = ResultAllForm(formdata=request.form)
    form.time.data = form.time_h.data * 3600 + \
        form.time_m.data * 60 + form.time_s.data

    form.time.data = form.time.data * 1000 + form.time_ms.data

    form.competition.choices = [(c.id, c.name) for c in Competition.query.order_by(
        Competition.name.desc()).all()]
    app.logger.info("request.form")
#     app.logger.info(form)
    app.logger.info(form.data)
#     app.logger.info(form.meta)
#     app.logger.info("is_submitted %d" % form.is_submitted())

    if request.method == 'GET' or form.competition.data is None:
        form.method.data = 'POST'
        return render_template('result_edit_competition.html', form=form)

    # competition is set
    form.competition = Competition.query.get(form.competition.data)
    form.course.choices = [(c.id, c.distance) for c in Course.query.filter(Course.competition == form.competition).order_by(
        Course.distance.desc()).all()]

    if form.method.data == "POST":
        if form.course.data is None:
            form.method.data = 'POST'
            return render_template('result_edit_course.html', form=form)

        # course is set
        course_id = int(form.course.data)
        form.course = Course.query.get(course_id)

        app.logger.info("(form.race.data, form.date.data)")
        app.logger.info((form.race.data, form.date.data))

        if (form.race.data is None) and (form.date.data is None):
            form.method.data = 'POST'
            app.logger.info('hello')
            return render_template('result_edit_race.html', form=form)

        else:
            app.logger.info('world')
            d = form.validate()
            if not d:
                app.logger.info(form.errors)

            if form.validate_on_submit():
                return redirect(url_for('result_confirm'), code=307)
            else:
                return render_template('result_edit.html', form=form)
#
#     elif request.args.get('method') == 'PUT':
#         race_id = int(request.args.get('race_id'))
#         race_type_id = int(request.args.get('race_type_id'))
#         member_id = int(request.args.get('member_id'))
#         result = Result.query.get(
#             {"race_id": race_id, "race_type_id": race_type_id, "member_id": member_id})
#         form = ResultForm(obj=result)
#         form.race = Race.query.get(race_type_id)
#         form.result_h.data = int(result.result)//3600
#         form.result_m.data = (int(result.result) % 3600)//60
#         form.result_s.data = int(result.result) % 60
#         form.method.data = 'PUT'
#
    else:
        app.logger.info('method is not POST')
#         race_id = int(request.args.get('race_id'))
#         result = Result()
#         result.race_id = race_id
#         form = ResultForm(obj=result)
#         form.race = Race.query.get(race_id)
#         form.method.data = 'POST'
#
    return render_template('result_edit_race.html', form=form)
#
#


@app.route('/result/confirm', methods=['POST'])
@login_required
def result_confirm():
    form = ResultAllForm(formdata=request.form)
    form.time.data = form.time_h.data * 3600 + \
        form.time_m.data * 60 + form.time_s.data

    if request.form.get('submit') == 'キャンセル':
        return redirect(url_for('user'))

#     competition = form.competition.data
#     course = form.course.data
#     race = form.race.data or -1
#     participants = form.participants.data
#     app.logger.info(competition)
#     app.logger.info(participants)

    form.competition.choices = [(c.id, c.name) for c in Competition.query.order_by(
        Competition.name.desc()).all()]

    app.logger.info("[DEBUG]")
#     app.logger.info(form.competition)
    app.logger.info(form.competition.data)
    form.course.choices = [(c.id, c.distance) for c in Course.query.join(Competition).filter(
        Competition.id == form.competition.data).order_by(Course.distance.desc()).all()]

    app.logger.info(form.data)
    app.logger.info(form.confirmed.data)
    if form.validate_on_submit() and request.form.get('confirmed') == 'True':
        pass
        if request.form.get('method') == 'DELETE':
            pass
        #             result = Result.query.get(
        #                 {"race_id": race.id, "race_type_id": race_type_id, "member_id": member_id})
        #             db.session.delete(result)
        #             db.session.commit()
        #             flash('{}さんの{}の結果の削除が完了しました'.format(
        #                 result.member.show_name, result.race.race_name), 'danger')
        #
        elif request.form.get('method') == 'PUT':
            pass
        #             result = Result.query.get(
        #                 {"race_id": race_id, "race_type_id": race_type_id, "member_id": member_id})
        #             form.populate_obj(result)
        #             db.session.commit()
        #             flash('{}さんの{}の結果の更新が完了しました'.format(
        #                 result.member.show_name, result.race.race_name), 'warning')

        elif request.form.get('method') == 'POST':
            pass
            # create race if not exists
            #             result = Result()
            #             form.populate_obj(result)
            #             db.session.add(result)
            #             db.session.commit()
            #             flash('{}さんの{}の結果の登録が完了しました'.format(
            #                 result.member.show_name, result.race.race_name), 'info')
            flash('記録登録完了（未実装）', 'info')

        return redirect(url_for('result'))
    else:  # not confirmed
        #         if request.form.get('method') == 'DELETE':
        #             result = Result.query.get(
        #                 {"race_id": race_id, "race_type_id": race_type_id, "member_id": member_id})
        #             form = ResultForm(obj=result)
        #         form.member = Member.query.get(int(form.member_id.data))
        app.logger.info(form.errors)
        form.competition = Competition.query.get(form.competition.data)
        form.course = Course.query.get(form.course.data)
        form.participants = [Member.query.get(mid)
                             for mid in form.participants.data]
        return render_template('result_confirm.html', form=form)


@ app.route('/ranking')
def ranking():
    q1 = db.session.query(Member.show_name, func.count(TrainingParticipant.training_id).label('cnt'), Member.sex).join(
        TrainingParticipant, TrainingParticipant.member_id == Member.id).group_by(TrainingParticipant.member_id)
    year_list = request.args.getlist('year_list')
    app.logger.info(year_list)
    if year_list:
        q2 = q1.filter(Member.year.in_(year_list))
    else:
        q2 = q1

    items = [{'rank': i + 1, 'show_name': d[0], 't_cnt': d[1], 'sex': d[2]}
             for i, d in enumerate(q2.order_by(db.text('cnt DESC')).all())
             ]

    return render_template('ranking.html', items=items, years=range(current_school_year, 1990, -1))


@ app.route('/search/')
def search():
    return render_template('search.html')


# @app.route('/race-type/')
# @login_required
# def race_type():
#     race_types = RaceType.query.order_by(RaceType.race_type, RaceType.duration)
#     return render_template('race_type.html', race_types=race_types)
#
#
@ app.route('/restaurant/')
@ login_required
def restaurant():
    afters = list(set(list(itertools.chain.from_iterable(
        db.session.query(After.restaurant_id).all()))))
    per_page = 40
    page = request.args.get('page') or 1
    page = max([1, int(page)])
    restaurants = Restaurant.query.order_by(
        Restaurant.score.desc()).paginate(page, per_page)
    return render_template('restaurant.html', pagination=restaurants, afters=afters)


@ app.route('/restaurant/edit', methods=['GET', 'POST'])
@ login_required
def restaurant_edit():
    form = RestaurantForm(formdata=request.form)

    if form.validate_on_submit():
        return redirect(url_for('restaurant_confirm'), code=307)

    if request.args.get('method') == 'PUT':
        id = int(request.args.get('id'))
        restaurant = Restaurant.query.get(id)
        form = RestaurantForm(obj=restaurant)
        form.name.data = restaurant.name
        form.place.data = restaurant.place
        form.score.data = restaurant.score
        form.comment.data = restaurant.comment
        form.method.data = 'PUT'
    else:
        form.method.data = 'POST'

    return render_template('restaurant_edit.html', form=form)


@ app.route('/restaurant/confirm', methods=['POST'])
@ login_required
def restaurant_confirm():
    form = RestaurantForm(formdata=request.form)

    if request.form.get('submit') == 'キャンセル':
        return redirect(url_for('restaurant'))

    if form.validate_on_submit() and request.form.get('confirmed'):
        if request.form.get('method') == 'DELETE':
            restaurant = Restaurant.query.get(form.id.data)
            db.session.delete(restaurant)
            db.session.commit()
            flash('レストラン: "{}" の削除が完了しました'.format(restaurant.name), 'danger')

        elif request.form.get('method') == 'PUT':
            restaurant = Restaurant.query.get(form.id.data)
            restaurant.name = restaurant.name.encode(
                'euc-jp', errors='xmlcharrefreplace').decode('euc-jp')
            restaurant.comment = restaurant.comment.encode(
                'euc-jp', errors='xmlcharrefreplace').decode('euc-jp')
            form.populate_obj(restaurant)
            db.session.commit()
            flash('レストラン: "{}" の更新が完了しました'.format(restaurant.name), 'warning')

        elif request.form.get('method') == 'POST':
            restaurant = Restaurant()
            form.populate_obj(restaurant)
            restaurant.name = restaurant.name.encode(
                'euc-jp', errors='xmlcharrefreplace').decode('euc-jp')
            restaurant.comment = restaurant.comment.encode(
                'euc-jp', errors='xmlcharrefreplace').decode('euc-jp')
            restaurant.id = None
            db.session.add(restaurant)
            db.session.commit()
            flash('レストラン: "{}" の登録が完了しました'.format(restaurant.name), 'info')

        return redirect(url_for('restaurant'))

    else:
        if request.form.get('method') == 'DELETE':
            restaurant = Restaurant.query.get(form.id.data)
            form = RestaurantForm(obj=restaurant)
        return render_template('restaurant_confirm.html', form=form)
