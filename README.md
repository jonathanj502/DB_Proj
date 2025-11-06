jj3489, ssw2163

**PostgreSQL account:**

**Web Application URL:**

**Original Proposal Comparison**

We implemented most of our core proposal features. Book/author/profile pages, search, reviews (post/edit via upsert), reading tracking (is_tracking) with UI and endpoints (track/untrack), genres display (categorized_as → genre), bookshelves/reading lists with create/view/delete and contains_book add/remove endpoints and owner-only controls, challenges (list, detail, join/leave/update progress), and the expected many-to-many joins (written_by, categorized_as, contains_book) were all implemented. Additionally, visibility and ownership checks are enforced where appropriate.

We didn’t implement the recommendation algorithm and an advanced reading statistics ui because we felt that they were out of scope for the class. For the advanced reading statistics ui, we decided to instead display the user statistics under a simple dropdown.

**Two pages I find most interesting:**

1. Book page (/book/<book_id>)
What it’s for: show full book details (authors, genres, page count, summary), display reviews, let a signed-in user post/edit a review, like reviews, and start/stop tracking the book.
DB interactions: several joined SELECTs (book + authors via written_by, genres via categorized_as→genre, reviews with profile join), upsert for reviews (INSERT ... ON CONFLICT to create or update a review), UPDATE for likes_count, and INSERT/DELETE/UPSERT for is_tracking rows. Many reads + conditional writes depend on the viewer cookie.
Why interesting: it mixes read-heavy multi-table joins and aggregated/normalized data with write-side “idempotent” operations (ON CONFLICT upserts). It also shows authorization logic (only the cookie owner can modify their tracking) and requires keeping referential integrity across several FK relationships.

2. Challenges pages (/challenges and /challenge/<id>)
What it’s for: list challenges, view detail (goal type/value, optional genre), join/leave a challenge, and update progress toward the goal.
DB interactions: listing uses a LEFT JOIN to bring genre info; the user join uses an INSERT with ON CONFLICT to idempotently create/activate participation; updating progress reads participates_in joined to challenge to decide goal and then updates participates_in (and flips status to completed when threshold reached). Participant lists are SELECTs with JOIN to profile to show usernames.
Why interesting: these routes combine transactional writes (join/progress updates) with business logic that depends on other rows (goal type/value) and temporal scope (starts_at/ends_at). The pattern of upserting participation, computing new progress, and conditionally transitioning status (active → completed) is a compact example of stateful DB-driven workflow tied to application logic.
