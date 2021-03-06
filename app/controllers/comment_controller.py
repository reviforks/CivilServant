import praw
import inspect, os, sys # set the BASE_DIR
import simplejson as json
import datetime
import reddit.connection
import reddit.praw_utils as praw_utils
import reddit.queries
from utils.common import PageType
from utils.retry import retryable
from app.models import Base, SubredditPage, Subreddit, Post, Comment
import app.event_handler
from sqlalchemy import and_
from sqlalchemy import text
import sqlalchemy
import warnings

class CommentController:
    def __init__(self, db_session, r, log):
        self.db_session = db_session
        self.log = log
        self.r = r 
        self.last_subreddit_id = None
        self.last_queried_comments = []

    def archive_missing_post_comments(self, post_id):
        post = self.db_session.query(Post).filter(Post.id == post_id).first()
        query_time = datetime.datetime.utcnow()
        submission = self.r.get_submission(submission_id=post_id)
        self.log.info("Querying Missing Comments for {post_id}. Total comments to archive: {num_comments}".format(
            post_id = post_id,
            num_comments = submission.num_comments
        ))
        submission.replace_more_comments(limit=None, threshold=0)
        comments = []
        
        if(os.environ['CS_ENV'] =='test'):
            flattened_comments = submission.comments # already a JSON dict
        else:
            flattened_comments = [x.json_dict for x in praw.helpers.flatten_tree(submission.comments)]

        for comment in flattened_comments:
            if 'replies' in comment.keys():
                del comment['replies']
            comments.append(comment)

        post.comment_data = json.dumps(comments)
        post.comments_queried_at = query_time
        self.db_session.commit()
        self.log.info("Saved Missing Comments for {post_id}. Total comments: {num_comments}".format(
            post_id = post_id,
            num_comments = len(comments)
        ))


    ## NOTE: THIS METHOD CAN REQUIRE A VERY LARGE NUMBER OF
    ## REDDIT API CALLS, WITH 1 CALL PER 20 COMMENTS
    def archive_all_missing_subreddit_post_comments(self, subreddit_id):
        subreddit_id = subreddit_id.replace("t5_", "")
        posts_without_comments = self.db_session.query(Post).filter(
                and_(
                    Post.comment_data == None,
                    Post.subreddit_id == subreddit_id
                )).all()
        self.log.info("Archiving {count} posts from subreddit: {subreddit}".format(
            count = len(posts_without_comments),
            subreddit = subreddit_id
        ))
        for post in posts_without_comments:
            self.archive_missing_post_comments(post.id)

    @app.event_handler.event_handler
    def archive_last_thousand_comments(self, subreddit_name):
        # fetch the subreddit ID
        subreddit = self.db_session.query(Subreddit).filter(Subreddit.name == subreddit_name).first()
        subreddit_id = subreddit.id
        self.last_subreddit_id = subreddit_id
        self.last_queried_comments = []
        #subreddit_name = subreddit.name

        # fetch the last thousand comment IDs

        # fetch comments from reddit
        comments = []
        total_comments_added = 0
        self.log.info("Fetching up to the last thousand comments in {subreddit_name}.".format(subreddit_name=subreddit.name))
        try:
            limit_found = False
            after_id = None

            iterations = 0
            while(limit_found == False):
                comment_result = self.r.get_comments(subreddit = subreddit_name, params={"after":after_id}, limit=100)

                ## sometimes the above line takes a long time to run
                ## so we expire the session before continuing
                self.db_session.expire_all()
                
                comments_returned = 0
                for comment in comment_result:
                    comments_returned += 1
                    if(os.environ['CS_ENV'] !='test'):
                        comment = comment.json_dict
                    comments.append(comment)
                    after_id = "t1_" + comment['id']
                if(comment_result is None or comments_returned == 0 ):
                    limit_found = True

                db_comments = []
                db_comment_ids = []
                add_comment_page_query = ""
                for comment in comments:
                     db_comments.append({
                        "id": comment['id'],
                        "subreddit_id": subreddit_id,
                        "created_utc": datetime.datetime.utcfromtimestamp(comment['created_utc']),
                        "post_id": comment['link_id'].replace("t3_" ,""),
                        "user_id": comment['author'],
                        "comment_data": json.dumps(comment)
                    })

                self.db_session.insert_retryable(Comment, db_comments)

#                comments_added =0
#                for db_comment in db_comments:
#                    try:
#                        self.db_session.add(db_comment)
#                        self.db_session.commit()
#                        comment_ids.append(db_comment.id)
#                        comments_added += 1
#                    except (sqlalchemy.exc.DBAPIError, sqlalchemy.exc.InvalidRequestError) as e:
#                        self.db_session.rollback()
#                        self.db_session.add(db_comment)
#                        self.db_session.commit()
#                        comment_ids.append(db_comment.id)
#                        comments_added += 1
#                self.log.info("  New page fetched: total comments archived from {1}: {0}".format(
#                    comments_added, subreddit_name
#                ))
                
#                total_comments_added += comments_added

                ## BREAK THE LOOP AFTER 15 iterations
                iterations += 1
                if(iterations==15):
                    self.log.info(" Reached 15 iterations while trying to fetch comments from {0}. Fetched {1}".format(subreddit_name, total_comments_added))
                    limit_found = True

#                    self.log.info("Exception saving {0} comments to database. Successfully saved after rollback: {1}".format(len(db_comments),str(e)))
                    

        except praw.errors.APIException:
            self.log.error("Error querying latest {subreddit_name} comments from reddit API. Immediate attention needed.".format(subreddit_name=subreddit_name))
            sys.exit(1)
        self.last_queried_comments += comments
            
