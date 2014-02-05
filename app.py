import os
import math
import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, Unicode
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

from flask import Flask, render_template, request, redirect, url_for, session, flash, Markup
import stripe

import tweepy
# Should I be using Flask-Security instead?
from flask_login import LoginManager, login_user, login_required, logout_user, current_user

# For downloading the Twitter profile image.
import requests

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
engine = create_engine(os.environ['DATABASE_URL'], echo=True)

Base = declarative_base(bind=engine)


# Move this to a separate models file.
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


# cheesy
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

user_to_add = User()

percentage_complete = 0


def create_data_csv(csv_handle, total_goal):
    ''' Query the database, create a csv for D3 from rows. '''
    total_pledges = 0
    #with open('static/data.csv', 'w') as d3csv:
    #with open('/tmp/data.csv', 'w') as d3csv:
    with open(csv_handle, 'w') as d3csv:
        screen_names = []
        pledges = []
        for instance in sql_session.query(User):
            #d3csv.write('%s, %s\n' % (instance.screen_name, instance.pledge_amount))
            screen_names.append('%s $%s' % (instance.twitter_screen_name, instance.pledge_amount))
            pledges.append('%s' % instance.pledge_amount)
            # If it is an int in the db, why doesn't it come out as the same type?
            try:
                total_pledges += int(instance.pledge_amount)
            except:
                pass
        unfunded = total_goal - total_pledges
        # Ugly.
        percentage_complete = int(100 * (float(total_pledges) / float(total_goal)))
        print('TOTAL_PLEDGES: %s' % total_pledges)
        print('PERCENTAGE_COMPLETE: %s' % percentage_complete)
        print('TOTAL PLEDGES / 682: %s' % (total_pledges / 682))
        screen_names.insert(0, 'Unfunded $%s' % unfunded)
        pledges.insert(0, str(unfunded))
        screen_names = ','.join(screen_names)
        screen_names = '%s\n' % screen_names
        pledges = ','.join(pledges)
        d3csv.write(screen_names)
        d3csv.write(pledges)
        return total_pledges


def create_donut_csv(csv_handle, total_goal):
    total_


'''
191     <div class="col-md-3">
192         <p>
193     <img width="66px" src="static/images/profile_images/ecalifornica.jpeg">
194     </p>
195     <p style="margin-top:-5px; margin-bottom:-5px;">
196     <a href="http://www.twitter.com/ecalifornica/">@ecalifornica</a>
197     </p>
198     <p>
199     $100
200     </p>
201 </div>
'''

def bit_bang_donor_string():
    donor_html_string = ''
    for row in sql_session.query(User):
        print('ROW.PLEDGE_AMOUNT: %s' % row.pledge_amount)
        if row.pledge_amount is not 0 and row.stripe_token is not None:
            donor_html_string += '<div class="col-md-3"><p><img width="73px" src="static/images/profile_images/%s.jpeg" class="img-rounded"></p><p style="margin-top:-5px; margin-bottom:-5px;font-family:Helvetica"><a href="http://www.twitter.com/%s">@%s</a></p><p>$%s</p></div>' % (row.twitter_screen_name, row.twitter_screen_name, row.twitter_screen_name, row.pledge_amount)
    return donor_html_string


def calculate_total_pledges():
    total_pledges = 0
    for row in sql_session.query(User):
        try:
            total_pledges += int(row.pledge_amount)
        except:
            print('PASSING ON ROW WITH NO PLEDGE')
            pass
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
    # Must be a better way to do this.
    vote_one_classes = ''
    vote_two_classes = ''
    vote_three_classes = ''
    change_amount = False

    # Iterate through the DB rows and create a CSV for D3.
    total_pledges = create_data_csv('/tmp/data.csv', 682)
    
    # For displaying percentage funded.
    percentage_complete = int(100 * (float(total_pledges) / 682.0))
    print('PERCENTAGE_COMPLETE: %s' % percentage_complete)

    # If the user is signed in.
    if current_user.is_authenticated():
        # Don't show sign in button.
        sign_in = False
        # Is there a better way to make this query?
        sql_user = sql_session.query(User).filter_by(twitter_screen_name=current_user.id).first()
        print('AUTHENTICATED SQL_USER: %s, CURRENT_USER.id: %s' % (sql_user, current_user.id))
        try:
            pledge_amount = sql_user.pledge_amount
        except:
            pass
        if sql_user.mattress_vote == 1:
            vote_one_classes = 'btn-success'
        if sql_user.mattress_vote == 2:
            vote_two_classes = 'btn-success'
        if sql_user.mattress_vote == 3:
            vote_three_classes = 'btn-success'

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
    return render_template('index.html', key=key, signin=sign_in, enteramount=enter_amount, amount=pledge_amount_cents, amount_placeholder=amount_placeholder, amount_button=amount_button_text, entercard=enter_card, percentage_complete=percentage_complete, vote_one_classes=vote_one_classes, vote_two_classes=vote_two_classes, vote_three_classes=vote_three_classes, pledge_amount='$%s' % str(pledge_amount), change_amount=change_amount, donors=donors) 


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
    print('OAUTH AUTH SECURE: %s' % oauth_dancer.auth.secure)
    oauth_dancer.auth.secure = True
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

        # Flask-Login
        session_user = flask_login_user(oauth_dancer.twitter_screen_name)
        login_user(session_user)

        # Is this screen name already in the database?
        sql_user = sql_session.query(User).filter_by(twitter_screen_name=current_user.id).first()

        # Add this screen name to the database if it is not found.
        if sql_user is None:

            # I think that I'm using this class incorrectly.
            user_to_add.twitter_screen_name = session_user.id
            user_to_add.twitter_uid = api.me().id

            # Retrieve Twitter profile image.
            profile_image_url = api.me().profile_image_url
            profile_image_url = profile_image_url.replace('normal', 'bigger')
            r = requests.get(profile_image_url)
            print('PROFILE IMAGE URL: %s' % profile_image_url)
            #filename = 'static/images/profile_images/%s.jpeg' % api.me().screen_name
            try:
                filename = '/tmp/images/profile_images/%s.jpeg' % api.me().screen_name
                with open(filename, 'w') as file_handle:
                    file_handle.write(r.content)
                    print('FILE WRITTEN: %s' % file_handle)
            except:
                '''Will be fixed with S3'''
                pass

            # Insert this new user into the database.
            sql_session.add(user_to_add)
            sql_session.commit()

        print('LOGIN SUCCESSFUL FOR %s' % current_user.id)
        return redirect('/')

    # Login failed, try again. A loop if they decline to authenticate.
    return redirect('/about/')
        

@app.route('/charge', methods=['POST'])
def charge():
    print('/charge POST')
    print('REQUEST.VALUES: %s' % request.values)

    sql_user = sql_session.query(User).filter_by(twitter_screen_name=current_user.id).first()
    # For Stripe display
    amount = sql_user.pledge_amount
    # Round down
    amount = math.trunc(float(amount))
    # Stripe expects cents
    pledge_amount_cents = amount * 100

    # Create the Stripe customer for later charging.  
    # Should only do this if they don't have an id in the database?
    #if sql_user.stripe_customer_id is None:
    stripe_customer = stripe.Customer.create(
            card=request.form['stripeToken'],
            email = request.form['stripeEmail']
            )
    print('STRIPE CUSTOMER ID: %s' % stripe_customer.id)

    # Charge the card
    '''
    charge = stripe.Charge.create(
            customer=customer.id,
            amount=amount,
            currency='usd',
            description='Flask Charge'
            )
    '''

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

    # This should be a function.
    total_pledges = 0
    #with open('static/data.csv', 'w') as d3csv:
    with open('/tmp/data.csv', 'w') as d3csv:
        screen_names = []
        pledges = []
        for instance in sql_session.query(User):
            #d3csv.write('%s, %s\n' % (instance.screen_name, instance.pledge_amount))
            screen_names.append('%s $%s' % (instance.twitter_screen_name, instance.pledge_amount))
            pledges.append('%s' % instance.pledge_amount)
            # If it is an int in the db, why doesn't it come out as the same type?
            try:
                total_pledges += int(instance.pledge_amount)
            except:
                pass
        unfunded = 681 - total_pledges
        percentage_complete = int(100 * (float(total_pledges) / 681.0))
        print('total_pledges: %s' % total_pledges)
        print('percentage complete: %s' % percentage_complete)
        print(total_pledges / 681)
        screen_names.insert(0, 'Unfunded $%s' % unfunded)
        pledges.insert(0, str(unfunded))
        screen_names = ','.join(screen_names)
        screen_names = '%s\n' % screen_names
        pledges = ','.join(pledges)
        d3csv.write(screen_names)
        d3csv.write(pledges)

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


@app.route('/rollback/')
def rollback():
    sql_session.rollback()
    sql_session.commit()


if __name__ == '__main__':
    print('\n\nBEGINNING MAIN')
    # Reset the D3 data.
    #with open('static/data.csv', 'w') as d3csv:
    with open('/tmp/data.csv', 'w') as d3csv:
        pass

    app.run(host='blametommy.com', port=5000)
