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
