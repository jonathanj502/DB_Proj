
"""
Columbia's COMS W4111.001 Introduction to Databases
Example Webserver
To run locally:
    python server.py
Go to http://localhost:8111 in your browser.
A debugger such as "pdb" may be helpful for debugging.
Read about it online.
"""
import os
# accessible as a variable in index.html:
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, abort, url_for, make_response

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)


#
# The following is a dummy URI that does not connect to a valid database. You will need to modify it to connect to your Part 2 database in order to use the data.
#
# XXX: The URI should be in the format of:
#
#     postgresql://USER:PASSWORD@34.139.8.30/proj1part2
#
# For example, if you had username ab1234 and password 123123, then the following line would be:
#
#     DATABASEURI = "postgresql://ab1234:123123@34.139.8.30/proj1part2"
#
# Modify these with your own credentials you received from TA!
DATABASE_USERNAME = "ssw2163"
DATABASE_PASSWRD = "goodreads"
DATABASE_HOST = "34.139.8.30"
DATABASEURI = f"postgresql://{DATABASE_USERNAME}:{DATABASE_PASSWRD}@{DATABASE_HOST}/proj1part2"


#
# This line creates a database engine that knows how to connect to the URI above.
#
engine = create_engine(DATABASEURI)

#
# Example of running queries in your database
# Note that this will probably not work if you already have a table named 'test' in your database, containing meaningful data. This is only an example showing you how to run queries in your database using SQLAlchemy.
#
with engine.connect() as conn:
    create_table_command = """
    CREATE TABLE IF NOT EXISTS test (
            id serial,
            name text
    )
    """
    res = conn.execute(text(create_table_command))
    insert_table_command = """INSERT INTO test(name) VALUES ('grace hopper'), ('alan turing'), ('ada lovelace')"""
    res = conn.execute(text(insert_table_command))
    # you need to commit for create, insert, update queries to reflect
    conn.commit()


@app.before_request
def before_request():
    """
    This function is run at the beginning of every web request
    (every time you enter an address in the web browser).
    We use it to setup a database connection that can be used throughout the request.

    The variable g is globally accessible.
    """
    try:
        g.conn = engine.connect()
    except:
        print("uh oh, problem connecting to database")
        import traceback; traceback.print_exc()
        g.conn = None

@app.teardown_request
def teardown_request(exception):
    """
    At the end of the web request, this makes sure to close the database connection.
    If you don't, the database could run out of memory!
    """
    try:
        g.conn.close()
    except Exception as e:
        pass

@app.route('/')
def index():
    """
    request is a special object that Flask provides to access web request information:

    request.method:   "GET" or "POST"
    request.form:     if the browser submitted a form, this contains the data in the form
    request.args:     dictionary of URL arguments, e.g., {a:1, b:2} for http://localhost?a=1&b=2

    See its API: https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data
    """

    # DEBUG: this is debugging code to see what request looks like
    print(request.args)

    return render_template("index.html")

@app.route('/search', methods=['GET'])
def search():
    print("SEARCH ABC")
    print(request.args)

    q = (request.args.get('q') or "").strip()
    mode = request.args.get('mode', 'title')

    results = []

    if not q:
        return render_template("index.html", results=[], query=q, mode=mode)

    if mode == "title":
        # Search books by title
        sql = text('''
            SELECT
                b.book_id AS id,
                b.title AS title,
                b.publication_year AS published_year,
                b.image_url AS image_url,
                COALESCE(string_agg(a.name, ', '), '') AS authors
            FROM book b
            LEFT JOIN written_by wb ON b.book_id = wb.book_id
            LEFT JOIN author a ON wb.author_id = a.author_id
            WHERE b.title ILIKE :p
            GROUP BY b.book_id, b.title, b.publication_year, b.image_url
            ORDER BY b.publication_year DESC NULLS LAST
            LIMIT 50
        ''')
        cursor = g.conn.execute(sql, {"p": f"%{q}%"})
        for row in cursor:
            results.append({
                "id": row.id,
                "title": row.title,
                "authors": row.authors,
                "published_year": row.published_year,
                "image_url": row.image_url,
                "type": "book"
            })
        cursor.close()

    elif mode == "author":
        # Search authors
        sql = text('''
            SELECT author_id AS id, name, birthday, nationality
            FROM author
            WHERE name ILIKE :p
            ORDER BY name
            LIMIT 50
        ''')
        cursor = g.conn.execute(sql, {"p": f"%{q}%"})
        for row in cursor:
            results.append({
                "id": row.id,
                "title": row.name,
                "authors": None,
                "published_year": row.birthday,
                "image_url": None,
                "extra": row.nationality,
                "type": "author"
            })
        cursor.close()

    elif mode == "profile":
        # Search user profiles
        sql = text('''
            SELECT profile_id AS id, username, joined_at
            FROM profile
            WHERE username ILIKE :p
            ORDER BY joined_at DESC
            LIMIT 50
        ''')
        cursor = g.conn.execute(sql, {"p": f"%{q}%"})
        for row in cursor:
            results.append({
                "id": row.id,
                "title": row.username,
                "authors": None,
                "published_year": row.joined_at,
                "image_url": url_for('static', filename='img/default-avatar.png'),
                "type": "profile"
            })
        cursor.close()

    elif mode == "bookshelf":
        # Search bookshelves
        sql = text('''
            SELECT bs.bookshelf_id AS id, bs.shelf_name, bs.description, p.username
            FROM bookshelf bs
            JOIN profile p ON bs.profile_id = p.profile_id
            WHERE bs.shelf_name ILIKE :p OR bs.description ILIKE :p
            ORDER BY bs.created_at DESC
            LIMIT 50
        ''')
        cursor = g.conn.execute(sql, {"p": f"%{q}%"})
        for row in cursor:
            results.append({
                "id": row.id,
                "title": row.shelf_name,
                "authors": row.username,   # owner
                "published_year": None,
                "image_url": None,
                "extra": row.description,
                "type": "bookshelf"
            })
        cursor.close()

    return render_template("index.html", results=results, query=q, mode=mode)

@app.route('/book/<int:book_id>')
def book(book_id):
    print("BOOK PAGE")
    # Get book info by book_id
    book_sql = text('''
        SELECT
        	b.book_id, b.title, b.publication_year, b.image_url, b.summary, b.page_count, b.lang
			FROM book b
            WHERE b.book_id = :book_id
    ''')
    
    # Get author by book_id
    authors_sql = text('''
		SELECT a.author_id, a.name
		FROM author a
		JOIN written_by wb ON a.author_id = wb.author_id
		WHERE wb.book_id = :book_id
    ''')
                    
    
    cursor = g.conn.execute(book_sql, {"book_id": book_id})
    row = cursor.fetchone()
    if row is None:
        abort(404)
    m = getattr(row, "_mapping", row)
    book = {
        "id": m.get("book_id") or m.get("id"),
        "title": m.get("title"),
        "published_year": m.get("publication_year"),
        "image_url": (m.get("image_url") or "").strip().strip("'\""),
        "summary": m.get("summary"),
        "page_count": m.get("page_count"),
        "language": m.get("lang"),
    }
    
    # load authors as list of dicts
    cursor = g.conn.execute(authors_sql, {"book_id": book_id})
    authors = []
    for r in cursor:
        rm = getattr(r, "_mapping", r)
        authors.append({"id": rm.get("author_id"), "name": rm.get("name")})
    cursor.close()
    book["authors"] = authors
    
    # load reviews for this book (pass to template)
    try:
        rev_cur = g.conn.execute(
            text("""
                SELECT r.profile_id, r.rating, r.review_text, r.reviewed_at, r.likes_count, p.username
                FROM reviews r
                LEFT JOIN profile p ON r.profile_id = p.profile_id
                WHERE r.book_id = :book_id
                ORDER BY r.reviewed_at DESC
            """),
            {"book_id": book_id}
        )
        reviews = []
        for rr in rev_cur:
            rm = getattr(rr, "_mapping", rr)
            reviews.append({
                "profile_id": (rm.get("profile_id") if hasattr(rm, "get") else rr[0]),
                "rating": (rm.get("rating") if hasattr(rm, "get") else rr[1]),
                "review_text": (rm.get("review_text") if hasattr(rm, "get") else rr[2]),
                "reviewed_at": (rm.get("reviewed_at") if hasattr(rm, "get") else rr[3]),
                "likes_count": (rm.get("likes_count") if hasattr(rm, "get") else rr[4]) or 0,
                "username": (rm.get("username") if hasattr(rm, "get") else rr[5]),
            })
        rev_cur.close()
    except Exception as e:
        print("book reviews db error:", e)
        reviews = []

    # --- Tracking: check if current viewer is tracking this book ---
    tracking = None
    viewer = request.cookies.get('profile_id')
    if viewer:
        try:
            tr = g.conn.execute(
                text("""
                    SELECT profile_id, status, current_page, start_date, finish_date
                    FROM is_tracking
                    WHERE profile_id = :pid AND book_id = :bid
                """),
                {"pid": int(viewer), "bid": book_id}
            ).fetchone()
            if tr:
                tm = getattr(tr, "_mapping", tr)
                tracking = {
                    "profile_id": tm.get("profile_id") if hasattr(tm, "get") else tr[0],
                    "status": tm.get("status") if hasattr(tm, "get") else tr[1],
                    "current_page": tm.get("current_page") if hasattr(tm, "get") else tr[2],
                    "start_date": tm.get("start_date") if hasattr(tm, "get") else tr[3],
                    "finish_date": tm.get("finish_date") if hasattr(tm, "get") else tr[4],
                }
        except Exception as e:
            print("tracking lookup error:", e)
            tracking = None

    return render_template("book_page.html", book=book, reviews=reviews, tracking=tracking)

@app.route('/book/<int:book_id>/track', methods=['POST'])
def track_book(book_id):
    pid_cookie = request.cookies.get('profile_id')
    if not pid_cookie:
        return redirect(url_for('login'))
    try:
        pid = int(pid_cookie)
    except Exception:
        return redirect(url_for('login'))

    status = (request.form.get('status') or 'reading').strip()
    current_page_raw = request.form.get('current_page', '').strip()
    current_page = None
    if current_page_raw != '':
        try:
            current_page = int(current_page_raw)
            if current_page < 0:
                current_page = 0
        except Exception:
            current_page = None

    start_date = request.form.get('start_date') or None
    finish_date = request.form.get('finish_date') or None

    try:
        g.conn.execute(
            text("""
                INSERT INTO is_tracking (profile_id, book_id, status, current_page, start_date, finish_date)
                VALUES (:pid, :bid, :status, :current_page, :start_date, :finish_date)
                ON CONFLICT (profile_id, book_id)
                DO UPDATE SET status = EXCLUDED.status,
                              current_page = EXCLUDED.current_page,
                              start_date = EXCLUDED.start_date,
                              finish_date = EXCLUDED.finish_date
            """),
            {
                "pid": pid,
                "bid": book_id,
                "status": status,
                "current_page": current_page,
                "start_date": start_date,
                "finish_date": finish_date
            }
        )
        try:
            g.conn.commit()
        except Exception:
            pass
    except Exception as e:
        print("track_book db error:", e)
        try:
            g.conn.rollback()
        except Exception:
            pass

    return redirect(url_for('book', book_id=book_id))


@app.route('/book/<int:book_id>/untrack', methods=['POST'])
def untrack_book(book_id):
    pid_cookie = request.cookies.get('profile_id')
    if not pid_cookie:
        return redirect(url_for('login'))
    try:
        pid = int(pid_cookie)
    except Exception:
        return redirect(url_for('login'))

    try:
        g.conn.execute(
            text("DELETE FROM is_tracking WHERE profile_id = :pid AND book_id = :bid"),
            {"pid": pid, "bid": book_id}
        )
        try:
            g.conn.commit()
        except Exception:
            pass
    except Exception as e:
        print("untrack db error:", e)
        try:
            g.conn.rollback()
        except Exception:
            pass

    return redirect(url_for('book', book_id=book_id))

@app.route('/book/<int:book_id>/review', methods=['POST'])
def post_review(book_id):
    # must be logged in via cookie
    pid = request.cookies.get('profile_id')
    if not pid:
        return redirect(url_for('login'))

    review_text = request.form.get('review_text', '').strip()
    rating_raw = request.form.get('rating', '').strip()

    rating = None
    if rating_raw != '':
        try:
            rating = round(float(rating_raw), 1)
            if rating < 0 or rating > 5:
                return render_template('book_page.html', book={}, reviews=[], error="Rating must be between 0 and 5.")
        except Exception:
            return render_template('book_page.html', book={}, reviews=[], error="Invalid rating value.")

    if rating is None and not review_text:
        return render_template('book_page.html', book={}, reviews=[], error="Either rating or review text required.")

    try:
        g.conn.execute(
            text("""
                INSERT INTO reviews (profile_id, book_id, rating, review_text, reviewed_at)
                VALUES (:pid, :bid, :rating, :text, CURRENT_TIMESTAMP)
                ON CONFLICT (profile_id, book_id)
                DO UPDATE SET rating = EXCLUDED.rating, review_text = EXCLUDED.review_text, reviewed_at = CURRENT_TIMESTAMP
            """),
            {"pid": int(pid), "bid": book_id, "rating": rating, "text": review_text}
        )
        try:
            g.conn.commit()
        except Exception:
            pass
    except Exception as e:
        print("post_review db error:", e)
        try:
            g.conn.rollback()
        except Exception:
            pass
        return render_template('book_page.html', book={}, reviews=[], error="Could not post review.")

    return redirect(url_for('book', book_id=book_id))


@app.route('/book/<int:book_id>/review/<int:profile_id>/like', methods=['POST'])
def like_review(book_id, profile_id):
    try:
        g.conn.execute(
            text("UPDATE reviews SET likes_count = COALESCE(likes_count,0) + 1 WHERE book_id = :bid AND profile_id = :pid"),
            {"bid": book_id, "pid": profile_id}
        )
        try:
            g.conn.commit()
        except Exception:
            pass
    except Exception as e:
        print("like_review db error:", e)
        try:
            g.conn.rollback()
        except Exception:
            pass
    return redirect(url_for('book', book_id=book_id))


@app.route('/book/<int:book_id>/review/delete', methods=['POST'])
def delete_review(book_id):
    pid = request.cookies.get('profile_id')
    if not pid:
        return redirect(url_for('login'))

    try:
        g.conn.execute(
            text("DELETE FROM reviews WHERE book_id = :bid AND profile_id = :pid"),
            {"bid": book_id, "pid": int(pid)}
        )
        try:
            g.conn.commit()
        except Exception:
            pass
    except Exception as e:
        print("delete_review db error:", e)
        try:
            g.conn.rollback()
        except Exception:
            pass

    return redirect(url_for('book', book_id=book_id))

@app.route('/author/<int:author_id>', methods=['GET', 'POST'])
def author(author_id):
    current_user_id = request.cookies.get('profile_id')
    if current_user_id:
        current_user_id = int(current_user_id)

    # Handle add/remove favorite
    if request.method == 'POST' and current_user_id:
        action = request.form.get('action')
        with g.conn.begin():
            if action == 'favorite':
                g.conn.execute(
                    text("""
                        INSERT INTO has_favorite (profile_id, author_id)
                        VALUES (:pid, :aid)
                        ON CONFLICT DO NOTHING
                    """),
                    {"pid": current_user_id, "aid": author_id}
                )
            elif action == 'unfavorite':
                g.conn.execute(
                    text("""
                        DELETE FROM has_favorite
                        WHERE profile_id = :pid AND author_id = :aid
                    """),
                    {"pid": current_user_id, "aid": author_id}
                )
        return redirect(url_for('author', author_id=author_id))

    # Fetch author row
    try:
        row = g.conn.execute(
            text("SELECT author_id, name, birthday, nationality FROM author WHERE author_id = :aid"),
            {"aid": author_id}
        ).fetchone()
    except Exception as e:
        print("author db error:", e)
        abort(500)

    if row is None:
        abort(404)

    m = getattr(row, "_mapping", row)
    author = {
        "author_id": m.get("author_id") if hasattr(m, "get") else row[0],
        "name": m.get("name") if hasattr(m, "get") else row[1],
        "birthday": m.get("birthday") if hasattr(m, "get") else row[2],
        "nationality": m.get("nationality") if hasattr(m, "get") else row[3],
    }

    # Fetch books by this author (with image_url and year for bookshelf-style cards)
    try:
        books_cursor = g.conn.execute(
            text("""
                SELECT b.book_id AS id,
                       b.title AS title,
                       b.publication_year AS published_year,
                       b.image_url AS image_url
                FROM book b
                JOIN written_by wb ON b.book_id = wb.book_id
                WHERE wb.author_id = :aid
                ORDER BY b.publication_year DESC NULLS LAST
            """),
            {"aid": author_id}
        )
        books = []
        for brow in books_cursor:
            bm = getattr(brow, "_mapping", brow)
            books.append({
                "id": bm.get("id") if hasattr(bm, "get") else brow[0],
                "title": bm.get("title") if hasattr(bm, "get") else brow[1],
                "published_year": bm.get("published_year") if hasattr(bm, "get") else brow[2],
                "image_url": bm.get("image_url") if hasattr(bm, "get") else brow[3],
            })
        books_cursor.close()
    except Exception as e:
        print("author books db error:", e)
        books = []

    # Check if current user has favorited this author
    is_favorite = False
    if current_user_id:
        is_favorite = g.conn.execute(
            text("SELECT 1 FROM has_favorite WHERE profile_id=:pid AND author_id=:aid"),
            {"pid": current_user_id, "aid": author_id}
        ).fetchone() is not None

    return render_template(
        "author_page.html",
        author=author,
        books=books,
        current_user_id=current_user_id,
        is_favorite=is_favorite
    )

@app.route('/profile/<int:profile_id>', methods=['GET', 'POST'])
def profile(profile_id):
    current_user_id = request.cookies.get('profile_id')
    if current_user_id:
        current_user_id = int(current_user_id)
    print(f"[DEBUG] Visiting profile {profile_id}, current_user_id={current_user_id}, method={request.method}")

    # Handle follow/unfollow
    if request.method == 'POST' and current_user_id:
        action = request.form.get('action')
        with g.conn.begin():
            if action == 'follow':
                g.conn.execute(
                    text("""
                        INSERT INTO follows (follower_id, following_id)
                        VALUES (:f, :t)
                        ON CONFLICT DO NOTHING
                    """),
                    {"f": current_user_id, "t": profile_id}
                )
            elif action == 'unfollow':
                g.conn.execute(
                    text("""
                        DELETE FROM follows
                        WHERE follower_id = :f AND following_id = :t
                    """),
                    {"f": current_user_id, "t": profile_id}
                )
        return redirect(url_for('profile', profile_id=profile_id))

    # Fetch profile
    row = g.conn.execute(
        text("SELECT profile_id, username, joined_at FROM profile WHERE profile_id = :pid"),
        {"pid": profile_id}
    ).fetchone()
    if row is None:
        abort(404)

    m = getattr(row, "_mapping", row)
    profile = {
        "profile_id": m.get("profile_id") if hasattr(m, "get") else row[0],
        "username": m.get("username") if hasattr(m, "get") else row[1],
        "joined_at": m.get("joined_at") if hasattr(m, "get") else row[2],
    }

    # Counts
    followers_count = g.conn.execute(
        text("SELECT COUNT(*) FROM follows WHERE following_id = :pid"),
        {"pid": profile_id}
    ).scalar()
    following_count = g.conn.execute(
        text("SELECT COUNT(*) FROM follows WHERE follower_id = :pid"),
        {"pid": profile_id}
    ).scalar()

    # Follow status
    is_following = False
    if current_user_id:
        is_following = g.conn.execute(
            text("SELECT 1 FROM follows WHERE follower_id = :f AND following_id = :t"),
            {"f": current_user_id, "t": profile_id}
        ).fetchone() is not None

    # Followers list
    followers = g.conn.execute(
        text("""
            SELECT p.profile_id AS id, p.username
            FROM follows f
            JOIN profile p ON f.follower_id = p.profile_id
            WHERE f.following_id = :pid
        """),
        {"pid": profile_id}
    ).fetchall()

    # Following list
    following = g.conn.execute(
        text("""
            SELECT p.profile_id AS id, p.username
            FROM follows f
            JOIN profile p ON f.following_id = p.profile_id
            WHERE f.follower_id = :pid
        """),
        {"pid": profile_id}
    ).fetchall()

    # Favorite authors
    favorite_authors = g.conn.execute(
        text("""
            SELECT a.author_id AS id, a.name
            FROM has_favorite hf
            JOIN author a ON hf.author_id = a.author_id
            WHERE hf.profile_id = :pid
        """),
        {"pid": profile_id}
    ).fetchall()

    # Tracked books
    tracked_books = g.conn.execute(
        text("""
            SELECT b.book_id AS id, b.title, it.status
            FROM is_tracking it
            JOIN book b ON it.book_id = b.book_id
            WHERE it.profile_id = :pid
        """),
        {"pid": profile_id}
    ).fetchall()

    # Reviews
    reviews = g.conn.execute(
        text("""
            SELECT r.book_id AS id, b.title, r.rating, r.review_text
            FROM reviews r
            JOIN book b ON r.book_id = b.book_id
            WHERE r.profile_id = :pid
        """),
        {"pid": profile_id}
    ).fetchall()

    # show private bookshelves only to the profile owner (based on cookie)
    viewer = request.cookies.get('profile_id')
    try:
        is_owner = (int(viewer) == profile_id)
    except Exception:
        is_owner = False

    try:
        if is_owner:
            bs_cur = g.conn.execute(
                text("""
                    SELECT bookshelf_id, shelf_name, description, is_public, created_at
                    FROM bookshelf
                    WHERE profile_id = :pid
                    ORDER BY created_at DESC
                """),
                {"pid": profile_id}
            )
        else:
            bs_cur = g.conn.execute(
                text("""
                    SELECT bookshelf_id, shelf_name, description, is_public, created_at
                    FROM bookshelf
                    WHERE profile_id = :pid AND is_public = TRUE
                    ORDER BY created_at DESC
                """),
                {"pid": profile_id}
            )

        bookshelves = []
        for b in bs_cur:
            bm = getattr(b, "_mapping", b)
            bookshelves.append({
                "id": bm.get("bookshelf_id") if hasattr(bm, "get") else b[0],
                "name": bm.get("shelf_name") if hasattr(bm, "get") else b[1],
                "description": bm.get("description") if hasattr(bm, "get") else b[2],
                "is_public": bm.get("is_public") if hasattr(bm, "get") else b[3],
                "created_at": bm.get("created_at") if hasattr(bm, "get") else b[4],
            })
        bs_cur.close()
    except Exception as e:
        print("bookshelves db error:", e)
        bookshelves = []

    has_view_bookshelf = 'view_bookshelf' in app.view_functions

    return render_template(
        'profile.html',
        profile=profile,
        followers_count=followers_count,
        following_count=following_count,
        is_following=is_following,
        current_user_id=current_user_id,
        followers=followers,
        following=following,
        favorite_authors=favorite_authors,
        bookshelves=bookshelves,
        is_owner=is_owner,
        has_view_bookshelf=has_view_bookshelf,
        tracked_books=tracked_books,
        reviews=reviews
    )

@app.route('/bookshelf/<int:bookshelf_id>')
def view_bookshelf(bookshelf_id):
    try:
        row = g.conn.execute(
            text("""
                SELECT bs.bookshelf_id, bs.profile_id, bs.shelf_name, bs.description,
                       bs.is_public, bs.created_at, p.username AS owner_username
                FROM bookshelf bs
                LEFT JOIN profile p ON bs.profile_id = p.profile_id
                WHERE bs.bookshelf_id = :bsid
            """),
            {"bsid": bookshelf_id}
        ).fetchone()
    except Exception as e:
        print("bookshelf db error:", e)
        abort(500)

    if row is None:
        abort(404)

    m = getattr(row, "_mapping", row)
    shelf = {
        "id": m.get("bookshelf_id") if hasattr(m, "get") else row[0],
        "profile_id": m.get("profile_id") if hasattr(m, "get") else row[1],
        "name": m.get("shelf_name") if hasattr(m, "get") else row[2],
        "description": m.get("description") if hasattr(m, "get") else row[3],
        "is_public": bool(m.get("is_public")) if hasattr(m, "get") else bool(row[4]),
        "created_at": m.get("created_at") if hasattr(m, "get") else row[5],
        "owner_username": m.get("owner_username") if hasattr(m, "get") else row[6],
    }

    # viewer = cookie (same pattern used elsewhere)
    viewer = request.cookies.get('profile_id')
    try:
        is_owner = (int(viewer) == shelf["profile_id"])
    except Exception:
        is_owner = False

    # enforce visibility: if private and not owner -> 403
    if not shelf["is_public"] and not is_owner:
        abort(403)

    # load books in the bookshelf (most recent added first)
    try:
        cur = g.conn.execute(
            text("""
                SELECT b.book_id AS id, b.title AS title, b.publication_year AS published_year, b.image_url
                FROM contains_book cb
                JOIN book b ON cb.book_id = b.book_id
                WHERE cb.bookshelf_id = :bsid
                ORDER BY cb.added_at DESC
            """),
            {"bsid": bookshelf_id}
        )
        books = []
        for r in cur:
            rm = getattr(r, "_mapping", r)
            books.append({
                "id": rm.get("id") if hasattr(rm, "get") else r[0],
                "title": rm.get("title") if hasattr(rm, "get") else r[1],
                "published_year": rm.get("published_year") if hasattr(rm, "get") else r[2],
                "image_url": rm.get("image_url") if hasattr(rm, "get") else r[3],
            })
        cur.close()
    except Exception as e:
        print("books in bookshelf db error:", e)
        books = []

    return render_template("view_bookshelf.html", shelf=shelf, books=books, is_owner=is_owner)

@app.route('/bookshelf/<int:bookshelf_id>/delete', methods=['POST'])
def delete_bookshelf(bookshelf_id):
    # require logged in user
    pid_cookie = request.cookies.get('profile_id')
    if not pid_cookie:
        return redirect(url_for('login'))
    try:
        pid = int(pid_cookie)
    except Exception:
        return redirect(url_for('login'))

    try:
        res = g.conn.execute(
            text("DELETE FROM bookshelf WHERE bookshelf_id = :bsid AND profile_id = :pid"),
            {"bsid": bookshelf_id, "pid": pid}
        )
        try:
            g.conn.commit()
        except Exception:
            pass

        # if no row deleted, either not owner or shelf doesn't exist
        if getattr(res, "rowcount", None) == 0:
            abort(403)
    except Exception as e:
        print("delete_bookshelf db error:", e)
        try:
            g.conn.rollback()
        except Exception:
            pass
        abort(500)

    # redirect back to owner's profile page
    return redirect(url_for('profile', profile_id=pid))

@app.route('/bookshelf/create', methods=['POST'])
def create_bookshelf():
    pid_cookie = request.cookies.get('profile_id')
    if not pid_cookie:
        return redirect(url_for('login'))
    try:
        pid = int(pid_cookie)
    except Exception:
        return redirect(url_for('login'))

    name = request.form.get('shelf_name', '').strip()
    description = request.form.get('description', '').strip() or None
    is_public = bool(request.form.get('is_public'))

    if not name:
        return redirect(url_for('profile', profile_id=pid))

    try:
        # generate an integer id if the table doesn't auto-increment
        maxrow = g.conn.execute(text("SELECT COALESCE(MAX(bookshelf_id), 0) AS maxid FROM bookshelf")).fetchone()
        maxid = (maxrow[0] if maxrow else 0) or 0
        new_id = maxid + 1

        g.conn.execute(
            text("""
                INSERT INTO bookshelf (bookshelf_id, profile_id, shelf_name, description, is_public)
                VALUES (:id, :pid, :name, :description, :is_public)
            """),
            {"id": new_id, "pid": pid, "name": name, "description": description, "is_public": is_public}
        )
        try:
            g.conn.commit()
        except Exception:
            pass
    except Exception as e:
        print("create bookshelf db error:", e)
        try:
            g.conn.rollback()
        except Exception:
            pass

    return redirect(url_for('profile', profile_id=pid))

@app.route('/bookshelf/<int:bookshelf_id>/add', methods=['POST'])
def add_book_to_shelf(bookshelf_id):
    # require logged in user
    pid_cookie = request.cookies.get('profile_id')
    if not pid_cookie:
        return redirect(url_for('login'))
    try:
        pid = int(pid_cookie)
    except Exception:
        return redirect(url_for('login'))

    # verify bookshelf exists and owner
    try:
        row = g.conn.execute(
            text("SELECT profile_id FROM bookshelf WHERE bookshelf_id = :bsid"),
            {"bsid": bookshelf_id}
        ).fetchone()
    except Exception as e:
        print("bookshelf lookup error:", e)
        abort(500)

    if row is None:
        abort(404)

    owner = getattr(row, "_mapping", row).get("profile_id") if hasattr(getattr(row, "_mapping", row), "get") else row[0]
    try:
        if int(owner) != pid:
            abort(403)
    except Exception:
        abort(403)

    # parse book_id from form
    book_id_raw = (request.form.get('book_id') or "").strip()
    try:
        book_id = int(book_id_raw)
    except Exception:
        return redirect(url_for('view_bookshelf', bookshelf_id=bookshelf_id))

    # check book exists
    try:
        exists = g.conn.execute(text("SELECT 1 FROM book WHERE book_id = :bid"), {"bid": book_id}).fetchone()
    except Exception as e:
        print("book lookup error:", e)
        return redirect(url_for('view_bookshelf', bookshelf_id=bookshelf_id))

    if not exists:
        return redirect(url_for('view_bookshelf', bookshelf_id=bookshelf_id))

    # insert into contains_book (ignore if already present)
    try:
        g.conn.execute(
            text("""
                INSERT INTO contains_book (bookshelf_id, book_id)
                VALUES (:bsid, :bid)
                ON CONFLICT (bookshelf_id, book_id) DO NOTHING
            """),
            {"bsid": bookshelf_id, "bid": book_id}
        )
        try:
            g.conn.commit()
        except Exception:
            pass
    except Exception as e:
        print("add to bookshelf db error:", e)
        try:
            g.conn.rollback()
        except Exception:
            pass

    return redirect(url_for('view_bookshelf', bookshelf_id=bookshelf_id))

@app.route('/bookshelf/<int:bookshelf_id>/remove/<int:book_id>', methods=['POST'])
def remove_book_from_shelf(bookshelf_id, book_id):
    # require logged in user
    pid_cookie = request.cookies.get('profile_id')
    if not pid_cookie:
        return redirect(url_for('login'))
    try:
        pid = int(pid_cookie)
    except Exception:
        return redirect(url_for('login'))

    # verify bookshelf exists and owner
    try:
        row = g.conn.execute(
            text("SELECT profile_id FROM bookshelf WHERE bookshelf_id = :bsid"),
            {"bsid": bookshelf_id}
        ).fetchone()
    except Exception as e:
        print("bookshelf lookup error:", e)
        abort(500)

    if row is None:
        abort(404)

    owner = getattr(row, "_mapping", row).get("profile_id") if hasattr(getattr(row, "_mapping", row), "get") else row[0]
    try:
        if int(owner) != pid:
            abort(403)
    except Exception:
        abort(403)

    # delete mapping row
    try:
        res = g.conn.execute(
            text("DELETE FROM contains_book WHERE bookshelf_id = :bsid AND book_id = :bid"),
            {"bsid": bookshelf_id, "bid": book_id}
        )
        try:
            g.conn.commit()
        except Exception:
            pass
    except Exception as e:
        print("remove from bookshelf db error:", e)
        try:
            g.conn.rollback()
        except Exception:
            pass

    return redirect(url_for('view_bookshelf', bookshelf_id=bookshelf_id))

@app.route('/logout', methods=['POST'])
def logout():
    # deletes cookies and redirects to home
    resp = make_response(redirect(url_for('index')))
    resp.delete_cookie('profile_id')
    resp.delete_cookie('username')
    return resp

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        if not username:
            return render_template('login.html', error="Username required.")

        try:
            row = g.conn.execute(
                text("SELECT profile_id FROM profile WHERE username = :u"),
                {"u": username}
            ).fetchone()
        except Exception as e:
            print("login db error:", e)
            return render_template('login.html', error="Server error, please try again.")

        if row is None:
            return render_template('login.html', error="Unknown username.")

        # set cookie to indicate who is logged in (no session handling)
        m = getattr(row, "_mapping", row)
        profile_id = m.get("profile_id") if hasattr(m, "get") else row[0]
        resp = make_response(redirect(url_for('index')))
        resp.set_cookie('profile_id', str(profile_id), httponly=True)
        resp.set_cookie('username', username)
        return resp

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()

        # basic validation
        if not username:
            return render_template('signup.html', error="All fields are required.")
        
        # check if username already exists
        try:
            existing = g.conn.execute(
                text("SELECT profile_id FROM profile WHERE username = :u"),
                {"u": username}
            ).fetchone()
        except Exception:
            existing = None
       
        if existing:
            return render_template('signup.html', error="Username already taken.")

        # insert new user into database (manual profile_id since column is plain INTEGER PK)
        try:
            maxrow = g.conn.execute(text("SELECT COALESCE(MAX(profile_id), 0) AS maxid FROM profile")).fetchone()
            maxid = (maxrow[0] if maxrow else 0) or 0
            new_id = maxid + 1

            g.conn.execute(
                text("INSERT INTO profile (profile_id, username, joined_at) "
                     "VALUES (:id, :u, CURRENT_TIMESTAMP)"),
                {"id": new_id, "u": username}
            )
            g.conn.commit()
        except Exception as e:
            try:
                g.conn.rollback()
            except Exception:
                pass
            print("signup insert error:", e)
            return render_template('signup.html', error="Could not create account.")

        return redirect(url_for('login'))

    return render_template('signup.html')


if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8111, type=int)
    def run(debug, threaded, host, port):
        """
        This function handles command line parameters.
        Run the server using:

                python server.py

        Show the help text using:

                python server.py --help

        """

        HOST, PORT = host, port
        print("running on %s:%d" % (HOST, PORT))
        app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)

run()
