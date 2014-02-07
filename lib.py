import os 

mattress_color = ['', '#a16b19;', '#f1716e;', '#a0a132;']

def bit_bang_donor_string(user_query):
    donor_html_string = ''
    vote_badge_class = ''
    #for row in sql_session.query(User):
    for row in user_query:
        print('ROW.PLEDGE_AMOUNT: %s' % row.pledge_amount)
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
