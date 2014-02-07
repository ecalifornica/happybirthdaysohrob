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
