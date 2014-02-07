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

stripe_keys = {
        'publishable_key': os.environ['STRIPE_PUBLISHABLE_KEY'],
        'secret_key': os.environ['STRIPE_SECRET_KEY']
        }
stripe.api_key = stripe_keys['secret_key']

# Flask
app = Flask(__name__)
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = os.environ['FLASK_SECRET_KEY']

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# SQLAlchemy
'''
from sqlalchemy import create_engine, Column, Integer, String, Unicode
from sqlalchemy.ext.declarative import declarative_base
engine = create_engine(os.environ['DATABASE_URL'], echo=True)
Base = declarative_base(bind=engine)
'''
# Move this to a separate models file.
from models import *
'''
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    twitter_screen_name = Column(String)
    pledge_amount = Column(Integer)
    stripe_token = Column(String)
    stripe_customer_id = Column(String)
    email = Column(Unicode)
    twitter_token = Column(String)
    twitter_uid = Column(String)
    twitter_photo = Column(Unicode)
    mattress_vote = Column(Integer)
    name = Column(Unicode)
    city = Column(Unicode)
    state = Column(Unicode)
    address = Column(Unicode)
    zip_code = Column(Unicode) #ha
    country = Column(Unicode)

    def __repr__(self):
        return "<User(twitter_screen_name='%s')>" % self.twitter_screen_name
'''


# Cheesy
# Flask-Login user
class flask_login_user():
    def __init__(self, twitter_screen_name):
        self.id = twitter_screen_name
        #self.is_authenticated = None
        #self.is_active = None
        #self.is_anonymous = None

    def is_authenticated(self):
        #return self.authenticated
        return True

    def is_active(self):
        #return self.is_active
        return True

    def is_anonymous(self):
        #return self.is_anonymous
        return False

    def get_id(self):
        return unicode(self.id)

    def __repr__(self):
        return '<User %r>' % (self.id)


# Flask-Login        
@login_manager.user_loader
def load_user(userid):
    return flask_login_user(userid)


# Cheesy
class oauth_placeholder(object):
    def __init__(self):
        self.consumer_key = os.environ['TWITTER_CONSUMER_KEY']
        self.consumer_secret = os.environ['TWITTER_CONSUMER_SECRET']
        self.callback_url = os.environ['TWITTER_OAUTH_CALLBACK_URL']
        self.access_token = None
        self.access_token_secret = None
        #oauth_dancer.auth = tweepy.OAuthHandler(consumer_key, consumer_secret, callback_url)
        #auth = tweepy.OAuthHandler(self.consumer_key, self.consumer_secret, self.callback_url)
        self.twitter_screen_name = None

oauth_dancer = oauth_placeholder()


sql_session = scoped_session(sessionmaker(engine))
# Not sure why it doesn't work as I expect without scoped_session.
#session = sessionmaker(bind=engine)

# Should this be somewhere else?
user_to_add = User()

percentage_complete = 0

mattress_votes = [0,0,0]


# This should be three separate functions.
def create_data_csv(csv_handle, total_goal):
    ''' Query the database, create a csv for D3 from rows. '''
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


mattress_color = ['', '#a16b19;', '#f1716e;', '#a0a132;']
def bit_bang_donor_string():
    donor_html_string = ''
    vote_badge_class = ''
    for row in sql_session.query(User):
        print('ROW.PLEDGE_AMOUNT: %s' % row.pledge_amount)
        if row.pledge_amount is not 0 and row.stripe_token is not None:
            if row.mattress_vote is not None:
                vote_badge_class = mattress_color[int(row.mattress_vote)]
            donor_html_string += '<div class="col-md-3"><p><img width="73px" src="https://s3.amazonaws.com/happybirthdaysohrob/%s" class="img-rounded"></p><p style="margin-top:-5px; margin-bottom:-5px;font-family:Helvetica"><a href="http://www.twitter.com/%s">@%s</a></p><p style="font-weight:700;color:%s">$%s</p></div>' % (row.twitter_photo, row.twitter_screen_name, row.twitter_screen_name, vote_badge_class, row.pledge_amount)
            # Modulus for new rows
    return donor_html_string


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
    # Must be a better way to do this.
    '''
    vote_one_classes = ''
    vote_two_classes = ''
    vote_three_classes = ''
    '''

    # Iterate through the DB rows and create a CSV for D3.
    total_pledges = create_data_csv('/tmp/data.csv', 682)
    
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
        '''
        if sql_user.mattress_vote == 1:
            vote_one_classes = 'btn-success mattress-one'
        if sql_user.mattress_vote == 2:
            vote_two_classes = 'btn-success mattress-two'
        if sql_user.mattress_vote == 3:
            vote_three_classes = 'btn-success mattress-three'
        '''

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
            # This keeps cropping up as a bug.
            # Pledge amount in cents for Stripe
            pledge_amount_cents = pledge_amount * 100
            # Placeholder for form pre-fill.
            amount_placeholder = str(pledge_amount)

            # For the graph.
            # Iterate through the DB rows and create a CSV for D3.
            total_pledges = create_data_csv('/tmp/data.csv', 682)
            
            # For displaying percentage funded.
            percentage_complete = int(100 * (float(total_pledges) / 682.0))
            print('PERCENTAGE_COMPLETE: %s' % percentage_complete)

            #could this be done better with ajax?
            if sql_user.stripe_token is not None:
                # Don't show enter card details button.
                enter_card = False
            else:
                # Do show enter card details button.
                enter_card = True

        # If pledge is zero or NaN.
        else:
            enter_amount = True
            amount_button_text = 'Set Pledge Amount'

    # If the user is not authenticated, ask them to sign in.
    else:
        sign_in = True

    # Create the donors list html string.
    donors = Markup(bit_bang_donor_string())

    print('SIGNIN: %s, ENTERAMOUNT: %s, AMOUNT: %s, AMOUNT_PLACEHOLDER: %s, AMOUNT_BUTTON: %s, ENTERCARD: %s, PERCENTAGE_COMPLETE: %s, PLEDGE_AMOUNT: %s' % (sign_in, enter_amount, pledge_amount_cents, amount_placeholder, amount_button_text, enter_card, percentage_complete, pledge_amount))
    return render_template('index.html', key=key, signin=sign_in, enteramount=enter_amount, amount=pledge_amount_cents, amount_placeholder=amount_placeholder, amount_button=amount_button_text, entercard=enter_card, percentage_complete=percentage_complete, vote_one_classes=vote_classes[0], vote_two_classes=vote_classes[1], vote_three_classes=vote_classes[2], pledge_amount='$%s' % str(pledge_amount), change_amount=change_amount, donors=donors) 


# Route for mattress choice form submission.
@app.route('/vote/', methods=['POST'])
def vote():
    print('FORM VOTE: %s' % request.form['mattress_vote'])

    if current_user.is_authenticated():
        # Is there a better way to make this query?
        sql_user = sql_session.query(User).filter_by(twitter_screen_name=current_user.id).first()
        sql_user.mattress_vote = request.form['mattress_vote']
        print(sql_user)
        sql_session.commit()

    return redirect('/')


@app.route('/twitter-login/')
def login():
    oauth_dancer.auth = tweepy.OAuthHandler(oauth_dancer.consumer_key, oauth_dancer.consumer_secret, oauth_dancer.callback_url)
    print('OAUTH DANCER: %s, %s, %s' % (oauth_dancer.consumer_key, oauth_dancer.consumer_secret, oauth_dancer.callback_url))
    oauth_dancer.auth.secure = True
    print('OAUTH AUTH SECURE: %s' % oauth_dancer.auth.secure)
    return redirect(oauth_dancer.auth.get_authorization_url())


@app.route('/login/')
def twitter():
    print('OAUTH VERIFIER: %s' % request.args.get('oauth_verifier'))
    token = oauth_dancer.auth.get_access_token(verifier=request.args.get('oauth_verifier'))
    oauth_dancer.auth.set_access_token(token.key, token.secret)
    api = tweepy.API(oauth_dancer.auth)
    oauth_dancer.twitter_screen_name = api.me().screen_name
    #print api.me().__getstate__()

    # Cheesey?
    if oauth_dancer.twitter_screen_name is not None:
        print('OAUTH_DANCER.TWITTER_SCREEN_NAME: %s' % oauth_dancer.twitter_screen_name)

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

    total_pledges = create_data_csv('/tmp/data.csv', 682)

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
