
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
    
    return render_template("book_page.html", book=book)

@app.route('/author/<int:author_id>')
def author(author_id):
    return render_template("author_page.html")

@app.route('/profile/<int:profile_id>')
def profile(profile_id):
    try:
        row = g.conn.execute(
            text("SELECT profile_id, username, joined_at FROM profile WHERE profile_id = :pid"),
            {"pid": profile_id}
        ).fetchone()
    except Exception as e:
        print("profile db error:", e)
        abort(500)

    if row is None:
        abort(404)

    m = getattr(row, "_mapping", row)
    profile = {
        "profile_id": m.get("profile_id") if hasattr(m, "get") else row[0],
        "username": m.get("username") if hasattr(m, "get") else row[1],
        "joined_at": m.get("joined_at") if hasattr(m, "get") else row[2],
    }
    return render_template('profile.html', profile=profile)

# deletes cookies and redirects to home
@app.route('/logout', methods=['POST'])
def logout():
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
