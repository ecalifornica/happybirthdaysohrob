import logging
import os

from flask import flash, Flask, Markup, render_template, request, redirect
from flask_login import LoginManager, login_user, current_user
from models import engine, User
from sqlalchemy.orm import sessionmaker, scoped_session
import tweepy

import lib

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

sql_session = scoped_session(sessionmaker(engine))

app = Flask(__name__)
app.config['DEBUG'] = False
app.config['SECRET_KEY'] = os.environ['FLASK_SECRET_KEY']

consumer_key = os.environ['TWITTER_CONSUMER_KEY']
consumer_secret = os.environ['TWITTER_CONSUMER_SECRET']
callback_url = os.environ['TWITTER_OAUTH_CALLBACK_URL']
oauth_dancer = lib.oauth_placeholder(consumer_key,
                                     consumer_secret,
                                     callback_url)

flask_login_manager = LoginManager()
flask_login_manager.init_app(app)


@flask_login_manager.user_loader
def load_user(userid):
    return lib.flask_login_user(userid)


@app.route('/', methods=['GET', 'POST'])
def index():
    logging.info('IP: {}'.format(request.headers.get('X-Forwarded-For')))

    if request.headers.get('X-Forwarded-Proto') == 'http':
        return redirect(lib.http_to_https(request))

    # Flask template variables.
    pledge_amount = 0
    pledge_amount_cents = pledge_amount * 100
    amount_placeholder = str(pledge_amount)
    key = lib.stripe_keys['publishable_key']
    enter_amount = False
    amount_button_text = 'Set Pledge Amount'
    enter_card = False
    change_amount = False
    vote_classes = ['', '', '']
    user_query = sql_session.query(User)
    total_pledges = lib.sum_total_pledges(user_query)

    # For displaying percentage funded.
    percentage_complete = int(100 * (float(total_pledges) / 682.0))

    # If the user is signed in.
    if current_user.is_authenticated():

        # Hide sign in button.
        sign_in = False
        sql_user = sql_session.query(User).filter_by(
            twitter_screen_name=current_user.id).first()

        if sql_user.pledge_amount is not None:
            pledge_amount = sql_user.pledge_amount

        if sql_user.mattress_vote is not None:
            vote_classes[sql_user.mattress_vote - 1] = 'btn-success'

        if request.method == 'POST':

            # Simple form validation.
            try:
                pledge_amount = request.form['charge_amount']
                pledge_amount = int(pledge_amount)
            except:
                pledge_amount = 0

        # If the user has actually entered and saved an amount.
        if pledge_amount is not 0 and pledge_amount is not None:
            # Don't show pledge amount entry box.
            enter_amount = False
            change_amount = True
            # Pledge button text.
            amount_button_text = 'Change Pledge Amount'
            logging.info('PLEDGE_AMOUNT: %s' % pledge_amount)
            sql_user.pledge_amount = pledge_amount
            sql_session.commit()
            # Pledge amount in cents for Stripe
            pledge_amount_cents = pledge_amount * 100
            # Placeholder for form pre-fill.
            amount_placeholder = str(pledge_amount)

            if sql_user.stripe_token is not None:
                enter_card = False
            else:
                enter_card = True
        # If pledge is zero or NaN.
        else:
            enter_amount = True
            amount_button_text = 'Set Pledge Amount'
    # If the user is not authenticated, ask them to sign in.
    else:
        sign_in = True

    # Create the donors list html string.
    user_query = sql_session.query(User)
    donors = Markup(lib.bit_bang_donor_string(user_query))

    return render_template('index.html',
                           key=key,
                           signin=sign_in,
                           enteramount=enter_amount,
                           amount=pledge_amount_cents,
                           amount_placeholder=amount_placeholder,
                           amount_button=amount_button_text,
                           entercard=enter_card,
                           percentage_complete=percentage_complete,
                           vote_one_classes=vote_classes[0],
                           vote_two_classes=vote_classes[1],
                           vote_three_classes=vote_classes[2],
                           pledge_amount='$%s' % str(pledge_amount),
                           change_amount=change_amount,
                           donors=donors)


# Route for mattress choice form submission.
@app.route('/vote/', methods=['POST'])
def vote():
    if current_user.is_authenticated():
        # Is there a better way to make this query?
        sql_user = sql_session.query(User).filter_by(
            twitter_screen_name=current_user.id).first()
        sql_user.mattress_vote = request.form['mattress_vote']
        sql_session.commit()
    return redirect('/')


@app.route('/login/')
def twitter():
    if not request.args.get('oauth_token'):
        oauth_dancer.auth = tweepy.OAuthHandler(
            oauth_dancer.consumer_key,
            oauth_dancer.consumer_secret,
            oauth_dancer.callback_url)
        oauth_dancer.auth.secure = True

        return redirect(oauth_dancer.auth.get_authorization_url())

    user_to_add = User()
    token = oauth_dancer.auth.get_access_token(
        verifier=request.args.get('oauth_verifier'))
    oauth_dancer.auth.set_access_token(token.key, token.secret)
    api = tweepy.API(oauth_dancer.auth)
    oauth_dancer.twitter_screen_name = api.me().screen_name

    logging.debug(api.me().__getstate__())

    if oauth_dancer.twitter_screen_name is not None:

        # Flask-Login
        session_user = lib.flask_login_user(oauth_dancer.twitter_screen_name)
        login_user(session_user)

        # Is this screen name already in the database?
        sql_user = sql_session.query(User).filter_by(
            twitter_screen_name=current_user.id).first()

        # Add this screen name to the database if it is not found.
        if sql_user is None:

            # SQLAlchemy unicode error.
            user_to_add.twitter_screen_name = session_user.id
            user_to_add.twitter_uid = api.me().id

            # Retrieve and store Twitter profile image.
            user_to_add.twitter_photo = lib.twitter_profile_image(api)

            # Insert this new user into the database.
            sql_session.add(user_to_add)
            sql_session.commit()

        logging.info('LOGIN SUCCESSFUL FOR {}'.format(current_user.id))

        return redirect('/')

    # Login declined, redirect to informative page.
    return redirect('/about/')


@app.route('/charge', methods=['POST'])
def charge():
    sql_user = sql_session.query(User).filter_by(
        twitter_screen_name=current_user.id).first()
    amount = lib.stripe_transaction(sql_user, sql_session, request)
    message = Markup('<strong>Thank you</strong> for your pledge of \
            <strong>$%s</strong>. You will receive an email if \
            we reach our goal and your card is charged.' % amount)
    flash(message)
    return redirect('/')


@app.route('/change_amount/')
def change_amount():
    sql_user = sql_session.query(User).filter_by(
        twitter_screen_name=current_user.id).first()
    sql_user.pledge_amount = 0
    sql_session.commit()
    return redirect('/')


@app.route('/about')
def about():
    return render_template('about.html')


if __name__ == '__main__':
    app.run(host='blametommy.com')
