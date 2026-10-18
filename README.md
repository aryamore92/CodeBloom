# CodeBloom — Coding Awareness Platform for School Students

A complete local web application for school students in Classes 6–12. CodeBloom introduces coding through short lessons, quizzes, creative projects, a web playground, and teacher support.

## Start in VS Code on Windows

1. Extract the entire ZIP. Do not run files from inside the ZIP.
2. Open **VS Code → File → Open Folder** and select the extracted **codebloom** folder. You should see `server.py` directly inside this folder.
3. Make sure **Python 3.10 or newer** is installed. During installation, select **Add Python to PATH**. Restart VS Code after installing Python.
4. Select **Terminal → New Terminal**.
5. Run:

   ```powershell
   py -3 server.py
   ```

   If `py` is not recognised, use:

   ```powershell
   python server.py
   ```

6. Open **http://127.0.0.1:8000** in Chrome, Edge, or Firefox.
7. Click **Explore the platform** or **Sign in**. You can use the demo accounts below or register a student account.

**No pip installation, Node.js, virtual environment, database installation, API key, or internet connection is needed to run the app.**

Alternatively, double-click **START_WINDOWS.bat** after installing Python. Keep the terminal window open while using the app. Stop it with **Ctrl+C**. Start it with the same command next time; your saved work remains available.

On macOS / Linux, open a terminal in this folder and run `python3 server.py`.

## Demo accounts

| Role | Email | Password |
| --- | --- | --- |
| Student | student@codebloom.local | Learn@123 |
| Teacher | teacher@codebloom.local | Teach@123 |

**Demo classroom code: `BLOOM26`**

The demo emails identify local application accounts. They do not send or receive email. Demo activity is saved in the same local database as other activity. Use a separate account when demonstrating personal progress. These credentials are deliberately public for local project demonstrations.

## What is included

### Student workspace

- Student account registration and sign-in.
- Independent learning or classroom membership through an invitation code.
- Four paths: **Think like a coder**, **Build your first website**, **Meet Python**, and **Be a smart digital citizen**.
- Twelve original lessons with examples and practice prompts.
- Four five-question quizzes, scored by the server, with answer explanations.
- Persistent lesson completion, quiz history, XP, and four milestone badges.
- HTML/CSS/JavaScript playground with a restricted preview, saved drafts, and HTML downloads.
- Four project challenges with source-code / notes submissions.
- Teacher announcements and project feedback.
- Digital awareness hub covering privacy, AI awareness, careers, and learning habits.

### Teacher workspace

- Classroom roster and progress overview.
- Lesson counts, quiz averages, and student XP.
- Project review and written feedback, with a revision status.
- Classroom announcements.
- Downloadable CSV progress report.
- Separate classroom codes and access restricted to the teacher’s classroom.

### Interface

- Responsive layouts for desktop, tablet, and mobile.
- Keyboard-accessible navigation and dialogs, readable labels, visible focus states, and reduced-motion support.
- No external fonts, images, trackers, or required web services.

## Demonstrate the complete project

1. Sign in as the **student**.
2. Open **Learning paths → Think like a coder**. Read a lesson and mark it complete.
3. Take a quiz. Show the score, explanations, and saved progress.
4. Open **Playground**, edit the heading, press **Run code**, then **Save draft**.
5. Open **Projects & challenges** and submit a small website or algorithm.
6. Sign out, then sign in as the **teacher**.
7. Open **My classroom** to see the student’s progress.
8. Open **Project reviews**, review the submission, and save feedback.
9. Post an announcement and export a CSV report.
10. Sign in as the student again to show the feedback and announcement.

New accounts begin with zero progress; the app does not invent student achievements.

## Create a real teacher account

Teachers cannot promote themselves through the student registration form. The trusted person managing this local project can create a teacher using:

```powershell
py -3 create_teacher.py
```

Enter the teacher’s name, email, classroom name, and password when prompted. The password is hidden while typing. The command prints a new classroom code. Share that code with the students who should join that teacher’s classroom.

To start a fresh database without demonstration accounts, run:

```powershell
py -3 server.py --no-demo
```

`--no-demo` prevents initial demo seeding; it does not remove accounts already in an existing database. Create a teacher using `create_teacher.py`, then continue starting with `--no-demo` if you want to keep demo accounts absent.

## Project structure

```text
codebloom/
  server.py                Python HTTP server, sessions, API and SQLite storage
  content.py               Courses, lessons, quiz definitions and challenges
  create_teacher.py        Trusted local teacher-account creation
  START_WINDOWS.bat        Windows launch shortcut
  requirements.txt         Documents that there are no external dependencies
  README.md                Setup and project guide
  ARCHITECTURE.md          How the application works
  TEST_RESULTS.md          Verification scope and results
  static/
    index.html             Application entry point
    styles.css             Responsive visual design
    app.js                 Student and teacher interface and interactions
    favicon.svg            CodeBloom icon
  tests/
    test_app.py            Isolated API integration tests
    test_ui.js             Interface template and routing smoke tests
  .vscode/
    launch.json            Optional VS Code debugger configuration
    settings.json          Workspace editor settings
  data/                    Created automatically when the app first starts
    codebloom.db           Persistent application database
```

The optional F5 debugger requires the Python / Python Debugger extensions in VS Code. Running from the terminal does not require these extensions.

## Data, privacy, and operating scope

All application records are stored in `data/codebloom.db` on the computer running the server. Restarting VS Code does not reset the database. Stop the server before copying the database for a backup. Keep this file private; it contains account information, progress, and submitted work.

Passwords are stored as salted PBKDF2 hashes. Sessions use HttpOnly, SameSite cookies and expire after eight hours. Authenticated changes require a CSRF token. Quiz answers are withheld until submission, and teachers cannot review students outside their classroom. Submitted source code is displayed as text rather than executed in the teacher workspace.

The playground supports browser languages only. Run Python lesson examples as separate `.py` files in VS Code. Its preview is sandboxed and blocks network requests; it is intended for small learning examples and does not provide execution time limits.

This release is designed for **local school-project demonstrations on localhost**. It uses Python’s development HTTP server and plain local HTTP. Public deployment needs a production server, HTTPS, secure cookies, account recovery and administration, monitoring, and an appropriate school data policy. The current release does not include email delivery, password reset, file uploads, or a remote hosting service.

By default the app only listens on `127.0.0.1`. Using the same browser address on another computer does not connect to this server. To use it on a friend’s laptop, copy the extracted project and follow the same setup there; that laptop will have its own database unless you intentionally transfer the database.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `py` is not recognised | Try `python server.py`. If Python is also missing, install Python and restart VS Code. |
| `server.py` cannot be found | Open the inner `codebloom` folder and start the terminal there. |
| Port 8000 is already used | Run `py -3 server.py --port 8001`, then open http://127.0.0.1:8001. |
| The browser cannot connect | Keep the terminal running and check the printed address. |
| Session expired / action fails | Refresh the page and sign in again. |
| Too many sign-in attempts | Wait five minutes before trying that email again. |
| Classroom code not found | Ask the teacher for the exact code. The demo code is `BLOOM26`. |
| HTML preview has not changed | Press **Run code** or **Ctrl+Enter**. Saving does not automatically rerun the preview. |
| Python does not run in the playground | Save Python code to a `.py` file and run it with Python in the VS Code terminal. |

## Run the included checks

Backend checks (Python only):

```powershell
py -3 -m unittest discover -s tests -v
```

Optional interface template checks (requires Node.js, which the app itself does not need):

```powershell
node tests/test_ui.js
```

Tests use temporary databases and do not modify your real classroom database. See `TEST_RESULTS.md` for the scope of verification.
