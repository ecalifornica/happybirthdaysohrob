import os
import math
import sqlalchemy
#from sqlalchemy import create_engine, Column, Integer, String, Unicode
#from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from flask import Flask, render_template, request, redirect, url_for, session, flash, Markup
import stripe
import tweepy
# Should I be using Flask-Security instead?
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
# For downloading the Twitter profile image.
import requests
# For storing Twitter profile images in S3. 
import boto
from boto.s3.connection import S3Connection
from boto.s3.key import Key
# SQLAlchemy
from models import *
from lib import *
#uh oh

stripe_keys = {
        'publishable_key': os.environ['STRIPE_PUBLISHABLE_KEY'],
        'secret_key': os.environ['STRIPE_SECRET_KEY']
        }
stripe.api_key = stripe_keys['secret_key']

# Flask
app = Flask(__name__)
app.config['DEBUG'] = False
app.config['SECRET_KEY'] = os.environ['FLASK_SECRET_KEY']

# Twitter OAuth
consumer_key = os.environ['TWITTER_CONSUMER_KEY']
consumer_secret = os.environ['TWITTER_CONSUMER_SECRET']
callback_url = os.environ['TWITTER_OAUTH_CALLBACK_URL']

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# Cheesy
# Flask-Login user
class flask_login_user():
    def __init__(self, twitter_screen_name):
        self.id = twitter_screen_name
    def is_authenticated(self):
        return True
    def is_active(self):
        return True
    def is_anonymous(self):
        return False
    def get_id(self):
        return unicode(self.id)
    def __repr__(self):
        return '<User %r>' % (self.id)

# Flask-Login        
@login_manager.user_loader
def load_user(userid):
    return flask_login_user(userid)

class oauth_placeholder(object):
    def __init__(self, consumer_key, consumer_secret, callback_url):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.callback_url = callback_url
        self.access_token = None
        self.access_token_secret = None
        self.twitter_screen_name = None

sql_session = scoped_session(sessionmaker(engine))

percentage_complete = 0
"""
def total_pledges(user_query):
    total_pledges = 0
    for row in user_query:
        if row.stripe_token is not None and row.pledge_amount is not None:
            total_pledges += int(row.pledge_amount)
    return total_pledges 

def mattress_votes(user_query):
    mattress_votes = [0,0,0]
    for row in user_query:
        if row.mattress_vote is not None:
            mattress_votes[int(row.mattress_vote) - 1] += 1
    return mattress_votes
"""

# This should be three separate functions.
def create_data_csv(csv_handle, total_goal):
    mattress_votes = [0,0,0]
    total_pledges = 0
    with open(csv_handle, 'w') as d3csv:
        screen_names = []
        pledges = []
        for instance in sql_session.query(User):
            screen_names.append('%s $%s' % (instance.twitter_screen_name, instance.pledge_amount))
            pledges.append('%s' % instance.pledge_amount)
            # If it is an int in the db, why doesn't it come out as the same type?
            if instance.stripe_token is not None and instance.pledge_amount is not None:
                total_pledges += int(instance.pledge_amount)
            if instance.mattress_vote is not None:
                mattress_votes[int(instance.mattress_vote)-1] += 1
        unfunded = total_goal - total_pledges
        # Ugly.
        percentage_complete = int(100 * (float(total_pledges) / float(total_goal)))
        print('TOTAL_PLEDGES: %s' % total_pledges)
        print('PERCENTAGE_COMPLETE: %s' % percentage_complete)
        screen_names.insert(0, 'Unfunded $%s' % unfunded)
        pledges.insert(0, str(unfunded))
        screen_names = ','.join(screen_names)
        screen_names = '%s\n' % screen_names
        pledges = ','.join(pledges)
        d3csv.write(screen_names)
        d3csv.write(pledges)
        return total_pledges

@app.route('/', methods=['GET', 'POST'])
def index():
    
    # Flask template variables.
    pledge_amount = 0
    pledge_amount_cents = pledge_amount * 100
    amount_placeholder = str(pledge_amount)
    key=stripe_keys['publishable_key']
    enter_amount = False
    amount_button_text = 'Set Pledge Amount'
    enter_card = False
    change_amount = False
    vote_classes = ['', '', '']

    user_query  = sql_session.query(User)
    total_pledges = total_pledges(user_query)
    
    # For displaying percentage funded.
    percentage_complete = int(100 * (float(total_pledges) / 682.0))
    print('PERCENTAGE_COMPLETE: %s' % percentage_complete)

    # If the user is signed in.
    if current_user.is_authenticated():
        # Hide sign in button.
        sign_in = False
        # Is there a better way to make this query?
        sql_user = sql_session.query(User).filter_by(twitter_screen_name=current_user.id).first()
        print('AUTHENTICATED SQL_USER: %s, CURRENT_USER.id: %s' % (sql_user, current_user.id))
        if sql_user.pledge_amount is not None:
            pledge_amount = sql_user.pledge_amount

        if sql_user.mattress_vote is not None:
            vote_classes[sql_user.mattress_vote - 1] = 'btn-success'

        # Should I be POSTing to /?
        if request.method == 'POST':
            try:
                pledge_amount = request.form['charge_amount']
                pledge_amount = int(pledge_amount)
                print("CHARGE AMOUNT: %s" % pledge_amount)
            except:
                pledge_amount = 0

        # If the user has actually entered and saved an amount.
        if pledge_amount is not 0 and pledge_amount is not None:
            # Don't show pledge amount entry box.
            enter_amount = False
            change_amount = True
            # Pledge button text.
            amount_button_text = 'Change Pledge Amount'
            print('PLEDGE_AMOUNT: %s, PLEDGE_AMOUNT TYPE: %s' % (pledge_amount, type(pledge_amount)))
            sql_user.pledge_amount = pledge_amount
            print('SQL_USER.PLEDGE_AMOUNT: %s' % sql_user.pledge_amount)
            sql_session.commit()
            # Pledge amount in cents for Stripe
            pledge_amount_cents = pledge_amount * 100
            # Placeholder for form pre-fill.
            amount_placeholder = str(pledge_amount)

            # For the graph.
            # Iterate through the DB rows and create a CSV for D3.
            #total_pledges = create_data_csv('/tmp/data.csv', 682)
            
            # For displaying percentage funded.
            #percentage_complete = int(100 * (float(total_pledges) / 682.0))
            #print('PERCENTAGE_COMPLETE: %s' % percentage_complete)

            # This be done better with ajax?
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
    donors = Markup(bit_bang_donor_string(user_query))

    return render_template('index.html', key=key, signin=sign_in, enteramount=enter_amount, amount=pledge_amount_cents, amount_placeholder=amount_placeholder, amount_button=amount_button_text, entercard=enter_card, percentage_complete=percentage_complete, vote_one_classes=vote_classes[0], vote_two_classes=vote_classes[1], vote_three_classes=vote_classes[2], pledge_amount='$%s' % str(pledge_amount), change_amount=change_amount, donors=donors) 

# Route for mattress choice form submission.
@app.route('/vote/', methods=['POST'])
def vote():
    if current_user.is_authenticated():
        # Is there a better way to make this query?
        sql_user = sql_session.query(User).filter_by(twitter_screen_name=current_user.id).first()
        sql_user.mattress_vote = request.form['mattress_vote']
        sql_session.commit()
    return redirect('/')

oauth_dancer = oauth_placeholder(consumer_key, consumer_secret, callback_url)
@app.route('/twitter-login/')
def login():
    oauth_dancer.auth = tweepy.OAuthHandler(oauth_dancer.consumer_key, oauth_dancer.consumer_secret, oauth_dancer.callback_url)
    oauth_dancer.auth.secure = True
    return redirect(oauth_dancer.auth.get_authorization_url())

@app.route('/login/')
def twitter():
    user_to_add = User()
    token = oauth_dancer.auth.get_access_token(verifier=request.args.get('oauth_verifier'))
    oauth_dancer.auth.set_access_token(token.key, token.secret)
    api = tweepy.API(oauth_dancer.auth)
    oauth_dancer.twitter_screen_name = api.me().screen_name
    #print api.me().__getstate__()

    # Cheesey?
    if oauth_dancer.twitter_screen_name is not None:

        # Flask-Login
        session_user = flask_login_user(oauth_dancer.twitter_screen_name)
        login_user(session_user)

        # Is this screen name already in the database?
        sql_user = sql_session.query(User).filter_by(twitter_screen_name=current_user.id).first()
        print('CURRENT_USER.ID: %s' % current_user.id)

        # Add this screen name to the database if it is not found.
        if sql_user is None:

            # I think that I'm using this class incorrectly.
            print('SESSION_USER.ID: %s' % session_user.id)
            user_to_add.twitter_screen_name = session_user.id
            user_to_add.twitter_uid = api.me().id

            # Retrieve Twitter profile image.
            profile_image_url = api.me().profile_image_url
            profile_image_url = profile_image_url.replace('_normal', '')
            r = requests.get(profile_image_url)

            # Must be a more elegant way to do this, but I'm tired.
            filetype = profile_image_url.split('.')[-1]
            filename = '%s.%s' % (api.me().screen_name, filetype)
            filepath = '/tmp/%s' % filename
            with open(filepath, 'w') as file_handle:
                file_handle.write(r.content)
                print('FILE WRITTEN: %s' % file_handle)

            # S3
            conn = S3Connection()
            #k = connection.Key(conn.get_bucket('happybirthdaysohrob', validate=False))
            bucket = conn.get_bucket('happybirthdaysohrob')
            k = Key(bucket)
            k.key = '%s' % filename
            k.set_contents_from_filename(filepath)
            k.set_acl('public-read')
            user_to_add.twitter_photo = filename

            # Insert this new user into the database.
            sql_session.add(user_to_add)
            sql_session.commit()

        print('LOGIN SUCCESSFUL FOR %s' % current_user.id)
        return redirect('/')

    # Login declined, redirect to informative page.
    return redirect('/about/')

@app.route('/charge', methods=['POST'])
def charge():

    sql_user = sql_session.query(User).filter_by(twitter_screen_name=current_user.id).first()
    # For Stripe display
    amount = sql_user.pledge_amount
    # Round down
    amount = math.trunc(float(amount))
    # Stripe expects cents
    pledge_amount_cents = amount * 100

    # Create the Stripe customer for later charging.  
    stripe_customer = stripe.Customer.create(
            card=request.form['stripeToken'],
            email = request.form['stripeEmail'],
            description = 'Pledge amount: %s' % amount
            )
    #print('STRIPE CUSTOMER ID: %s' % stripe_customer.id)
    # Save this user's data to the users table
    sql_user.stripe_token = request.form['stripeToken']
    sql_user.stripe_customer_id = stripe_customer.id
    sql_user.email = request.form['stripeEmail']
    sql_user.name = request.form['stripeBillingName']
    sql_user.city = request.form['stripeBillingAddressCity']
    sql_user.state = request.form['stripeBillingAddressState']
    sql_user.address = request.form['stripeBillingAddressLine1']
    sql_user.zip_code = request.form['stripeBillingAddressZip']
    sql_user.country = request.form['stripeBillingAddressCountry']
    sql_session.commit()

    user_query  = sql_session.query(User)
    total_pledges = total_pledges(user_query)

    message = Markup('<strong>Thank you</strong> for your pledge of <strong>$%s</strong>. You will receive an email if we reach our goal and your card is charged.' % amount)
    flash(message)
    return redirect('/')

@app.route('/change_amount/')
def change_amount():
    sql_user = sql_session.query(User).filter_by(twitter_screen_name=current_user.id).first()
    sql_user.pledge_amount = 0
    sql_session.commit()
    return redirect('/')

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(host='blametommy.com')
