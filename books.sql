-- Sean Williams <ssw2163@columbia.edu>
-- Jonathan Jiang <jj3489@columbia.edu>

-- Reading Tracker

-- ENTITIES
CREATE TABLE profile (
	profile_id INTEGER PRIMARY KEY,
	username VARCHAR(32) NOT NULL UNIQUE,
	joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE book (
	book_id INTEGER PRIMARY KEY,
	title VARCHAR(256) NOT NULL,
	publication_year INTEGER,
	summary TEXT,
	page_count INTEGER,
	lang VARCHAR(128),
	image_url VARCHAR(2000)
);

CREATE TABLE author (
	author_id INTEGER PRIMARY KEY,
	name VARCHAR(128) NOT NULL,
	birthday DATE,
	nationality VARCHAR(128)
);

CREATE TABLE genre (
	genre_id INTEGER PRIMARY KEY,
	genre_name VARCHAR(128) NOT NULL UNIQUE
);

CREATE TABLE bookshelf (
	bookshelf_id INTEGER PRIMARY KEY,
	profile_id INTEGER NOT NULL,
	shelf_name VARCHAR(128) NOT NULL,
	description TEXT,
	is_public BOOLEAN NOT NULL DEFAULT TRUE,
	created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY (profile_id) REFERENCES profile(profile_id) ON DELETE CASCADE
);

CREATE TABLE challenge (
	challenge_id INTEGER PRIMARY KEY,
	name VARCHAR(256) NOT NULL,
	description TEXT,
	starts_at TIMESTAMP NOT NULL,
	ends_at TIMESTAMP NOT NULL,
	goal_type VARCHAR(16) NOT NULL, -- "books", "pages"
	goal_value INTEGER NOT NULL,
	genre_id INTEGER NULL,
	FOREIGN KEY (genre_id) REFERENCES genre(genre_id)
);


-- RELATIONSHIPS

-- Is Tracking (Profile, Book)
CREATE TABLE is_tracking (
	profile_id INTEGER NOT NULL,
	book_id INTEGER NOT NULL,
	status VARCHAR(16) NOT NULL DEFAULT 'reading', -- "planning", "reading", "on-hold", "finished"
	current_page INTEGER DEFAULT 0,
	start_date DATE DEFAULT CURRENT_DATE,
	finish_date DATE,
	PRIMARY KEY (profile_id, book_id),
	FOREIGN KEY (profile_id) REFERENCES profile(profile_id) ON DELETE CASCADE,
	FOREIGN KEY (book_id) REFERENCES book(book_id) ON DELETE CASCADE
);

-- Reviews (Profile, Book)
CREATE TABLE reviews (
	profile_id INTEGER NOT NULL,
	book_id INTEGER NOT NULL,
	rating DECIMAL(2, 1) CHECK (rating >= 0 AND rating <= 5),
	review_text TEXT,
	reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	likes_count INTEGER NOT NULL DEFAULT 0,
	PRIMARY KEY (profile_id, book_id),
	FOREIGN KEY (profile_id) REFERENCES profile(profile_id) ON DELETE CASCADE,
	FOREIGN KEY (book_id) REFERENCES book(book_id) ON DELETE CASCADE,
	CHECK (rating IS NOT NULL OR review_text IS NOT NULL)
);

-- Contains Book (Bookshelf, Book)
CREATE TABLE contains_book (
	bookshelf_id INTEGER NOT NULL,
	book_id INTEGER NOT NULL,
	added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (bookshelf_id, book_id),
	FOREIGN KEY (bookshelf_id) REFERENCES bookshelf(bookshelf_id) ON DELETE CASCADE,
	FOREIGN KEY (book_id) REFERENCES book(book_id) ON DELETE CASCADE
);

-- Follows (Profile, Profile)
CREATE TABLE follows (
	follower_id INTEGER NOT NULL,
	following_id INTEGER NOT NULL,
	followed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (follower_id, following_id),
	FOREIGN KEY (follower_id) REFERENCES profile(profile_id) ON DELETE CASCADE,
	FOREIGN KEY (following_id) REFERENCES profile(profile_id) ON DELETE CASCADE,
	CHECK (follower_id <> following_id)
);

-- Categorized As (Book, Genre)
CREATE TABLE categorized_as (
	book_id INTEGER NOT NULL,
	genre_id INTEGER NOT NULL,
	PRIMARY KEY (book_id, genre_id),
	FOREIGN KEY (book_id) REFERENCES book(book_id) ON DELETE CASCADE,
	FOREIGN KEY (genre_id) REFERENCES genre(genre_id) ON DELETE CASCADE
);

-- Written By (Book, Author)
CREATE TABLE written_by (
	book_id INTEGER NOT NULL,
	author_id INTEGER NOT NULL,
	PRIMARY KEY (book_id, author_id),
	FOREIGN KEY (book_id) REFERENCES book(book_id) ON DELETE CASCADE,
	FOREIGN KEY (author_id) REFERENCES author(author_id) ON DELETE CASCADE
);

-- Has Favorite (Profile, Author)
CREATE TABLE has_favorite (
	profile_id INTEGER NOT NULL,
	author_id INTEGER NOT NULL,
	PRIMARY KEY (profile_id, author_id),
	FOREIGN KEY (profile_id) REFERENCES profile(profile_id) ON DELETE CASCADE,
	FOREIGN KEY (author_id) REFERENCES author(author_id) ON DELETE CASCADE
);

-- Participates In (Profile, Challenge)
CREATE TABLE participates_in (
	profile_id INTEGER NOT NULL,
	challenge_id INTEGER NOT NULL,
	current_progress INTEGER DEFAULT 0,
	joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	status VARCHAR(16) DEFAULT 'active', -- "active", "dropped", "completed"
	PRIMARY KEY (profile_id, challenge_id),
	FOREIGN KEY (profile_id) REFERENCES profile(profile_id) ON DELETE CASCADE,
	FOREIGN KEY (challenge_id) REFERENCES challenge(challenge_id) ON DELETE CASCADE
);