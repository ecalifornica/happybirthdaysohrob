import os 
# For downloading the Twitter profile image.
import requests
# For storing Twitter profile images in S3.
import boto
from boto.s3.connection import S3Connection
from boto.s3.key import Key

S3_BUCKET = os.environ['S3_BUCKET']

import stripe
import math
stripe_keys = {
        'publishable_key': os.environ['STRIPE_PUBLISHABLE_KEY'],
        'secret_key': os.environ['STRIPE_SECRET_KEY']
        }
stripe.api_key = stripe_keys['secret_key']


mattress_color = ['', '#a16b19;', '#f1716e;', '#a0a132;']

def bit_bang_donor_string(user_query):
    donor_html_string = ''
    vote_badge_class = ''
    #for row in sql_session.query(User):
    for row in user_query:
        #print('ROW.PLEDGE_AMOUNT: %s' % row.pledge_amount)
        if row.pledge_amount is not 0 and row.stripe_token is not None:
            if row.mattress_vote is not None:
                vote_badge_class = mattress_color[int(row.mattress_vote)]
            donor_html_string += '<div class="col-md-3"><p><img width="73px" src="https://s3.amazonaws.com/happybirthdaysohrob/%s" class="img-rounded"></p><p style="margin-top:-5px; margin-bottom:-5px;font-family:Helvetica"><a href="http://www.twitter.com/%s">@%s</a></p><p style="font-weight:700;color:%s">$%s</p></div>' % (row.twitter_photo, row.twitter_screen_name, row.twitter_screen_name, vote_badge_class, row.pledge_amount)
            # Modulus for new rows
    return donor_html_string

class oauth_placeholder(object):
    def __init__(self, consumer_key, consumer_secret, callback_url):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.callback_url = callback_url
        self.access_token = None
        self.access_token_secret = None
        self.twitter_screen_name = None

#Cheesy
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

def sum_total_pledges(user_query):
    total_pledges = 0
    for row in user_query:
        if row.stripe_token is not None and row.pledge_amount is not None:
            total_pledges += int(row.pledge_amount)
    return total_pledges 

def tally_mattress_votes(user_query):
    mattress_votes = [0,0,0]
    for row in user_query:
        if row.mattress_vote is not None:
            mattress_votes[int(row.mattress_vote) - 1] += 1
    return mattress_votes

def http_to_https(request):
    '''
    ssl_state = request.headers.get('X-Forwarded-Proto')
    for i in request.headers:
        print(i)
    if ssl_state == 'http':
        url = request.url
        url = url.replace('http://', 'https://')
        return url
    '''
    url = request.url
    url = url.replace('http', 'https')
    return url
   
def twitter_profile_image(api):
    profile_image_url = api.me().profile_image_url
    profile_image_url = profile_image_url.replace('_normal', '')
    r = requests.get(profile_image_url)
    
    filetype = profile_image_url.split('.')[-1]
    filename = '%s.%s' % (api.me().screen_name, filetype)
    filepath = '/tmp/%s' % filename
    with open(filepath, 'w') as file_handle:
        file_handle.write(r.content)

    # S3
    conn = S3Connection()
    bucket = conn.get_bucket(S3_BUCKET)
    k = Key(bucket)
    k.key = filename
    k.set_contents_from_filename(filepath)
    k.set_acl('public-read')
    return filename

# Round down user's pledge amount.
def format_pledge_amount(sql_user):
    amount = sql_user.pledge_amount
    amount = math.trunc(float(amount))
    return amount

# Create Stripe customer for charging later.
def create_stripe_customer(request, amount):
    stripe_customer = stripe.Customer.create(
            card = request.form['stripeToken'],
            email = request.form['stripeEmail'],
            description = 'Pledge amount: %s' % amount
            )
    return stripe_customer

# Save this user's data to the users table.
def save_stripe_user_data(sql_user, sql_session, stripe_customer, request):
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

def stripe_transaction(sql_user, sql_session, request):
    amount = format_pledge_aount(sql_user)
    stripe_customer = create_stripe_customer(request, amount)
    save_stripe_user_data(sql_user, sql_session, stripe_customer, request)
