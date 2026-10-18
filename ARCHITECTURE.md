# How CodeBloom works

CodeBloom’s purpose is to raise coding awareness among school students and make the first steps practical. It combines introductory content, safe browser practice, assessment, and teacher guidance.

## Technology choices

| Layer | Technology | Purpose |
| --- | --- | --- |
| Interface | HTML, CSS, vanilla JavaScript | Displays pages, handles navigation, collects answers and submits projects. |
| Server | Python standard library | Receives requests, authenticates accounts, enforces permissions and calculates scores. |
| Database | SQLite | Stores accounts, sessions, completed lessons, quiz attempts, submissions and classroom updates. |
| Practice area | Sandboxed iframe | Previews HTML, CSS and JavaScript with network access blocked. |

The project is deliberately lightweight and has no third-party runtime dependencies. SQLite is included in Python, so a separate database server is unnecessary.

## Main request flow

1. The browser opens `index.html` and loads the stylesheet and application script.
2. JavaScript checks the current session using `/api/me`.
3. A signed-in student loads their courses and progress; a teacher loads their classroom records.
4. Forms send JSON requests to the server. The server checks the session, role, input and CSRF token.
5. The server changes the relevant SQLite records and returns a result.
6. The interface displays the updated progress, feedback, score or announcement.

Passwords are salted and hashed before storage. A successful sign-in creates a random session token in an HttpOnly cookie. The CSRF token is separate from that cookie and is required for authenticated changes.

## Database tables

| Table | Stores |
| --- | --- |
| `users` | Student / teacher account details, role, grade and classroom membership. |
| `classrooms` | Classroom name, invitation code and owning teacher. |
| `sessions` | Server-side session tokens, CSRF tokens and expiry times. |
| `completions` | Completed lesson IDs, with one record per student and lesson. |
| `attempts` | Quiz score, total questions and timestamp for each attempt. |
| `projects` | Source code / project notes, review status and teacher feedback. |
| `announcements` | Messages posted to a classroom. |
| `drafts` | One saved playground draft per student. |
| `login_limits` | Failed sign-in counts and temporary lockout times. |

Course content lives in `content.py`; it does not require an external API. Database changes use parameterised SQL queries.

## Scoring and progress

Completing a lesson earns 20 XP. A quiz’s best score earns 10 XP per correct answer. Retaking a quiz can improve that best score, but repeating the same result does not add duplicate XP. The server compares submitted answer choices to its stored answer key; a client-supplied score is ignored.

The four badges reward a first completed lesson, six completed lessons, a perfect quiz score, and a first project submission. Project review is qualitative teacher feedback rather than an automatic code grader.

## Access boundaries

Students can read and change their own progress, drafts and submissions. Joining a classroom lets that teacher see the student’s progress and submitted work. Teachers can post to their own classroom and review projects only from students currently in that classroom. Student registration always creates a student account; teacher creation happens through the trusted local command line.

## Explain the project in a viva

“Our project is CodeBloom, a coding awareness platform for school students. Students learn basic coding through lessons, quizzes and small projects. They can try HTML, CSS and JavaScript in a playground. Teachers can see classroom progress, review projects and post announcements. We built the frontend using HTML, CSS and JavaScript, the backend using Python, and stored the data in SQLite. The server checks login permissions and calculates quiz marks, while the browser displays the results.”
