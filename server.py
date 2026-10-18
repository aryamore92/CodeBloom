#!/usr/bin/env python3
"""CodeBloom: local school learning application, Python standard library only."""
import argparse, csv, hashlib, hmac, io, json, os, re, secrets, sqlite3, time
from contextlib import contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from content import COURSES, COURSE_MAP, CHALLENGES

ROOT=Path(__file__).resolve().parent
DB_PATH=Path(os.environ.get('CODEBLOOM_DB', str(ROOT/'data'/'codebloom.db')))
SESSION_SECONDS=8*60*60
MAX_BODY=256*1024

class AppError(Exception):
    def __init__(self,status,message): self.status,self.message=status,message

@contextmanager
def database():
    db=sqlite3.connect(DB_PATH,timeout=20)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback(); raise
    finally: db.close()

def password_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    result=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),200000).hex()
    return salt+':'+result

def password_matches(password,stored):
    return hmac.compare_digest(password_hash(password,stored.split(':')[0]),stored)

def now(): return int(time.time())

def init_db(seed_demo=True):
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    with database() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS classrooms(id INTEGER PRIMARY KEY,name TEXT NOT NULL,code TEXT UNIQUE NOT NULL,teacher_id INTEGER);
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('student','teacher')),grade TEXT NOT NULL DEFAULT '',class_id INTEGER REFERENCES classrooms(id),created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,csrf TEXT NOT NULL,expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS completions(user_id INTEGER REFERENCES users(id),lesson_id TEXT,completed_at INTEGER NOT NULL,PRIMARY KEY(user_id,lesson_id));
        CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,user_id INTEGER REFERENCES users(id),course_id TEXT NOT NULL,score INTEGER NOT NULL,total INTEGER NOT NULL,created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY,user_id INTEGER REFERENCES users(id),challenge_id TEXT NOT NULL,title TEXT NOT NULL,content TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'submitted',feedback TEXT NOT NULL DEFAULT '',created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS announcements(id INTEGER PRIMARY KEY,class_id INTEGER REFERENCES classrooms(id),teacher_id INTEGER REFERENCES users(id),title TEXT NOT NULL,body TEXT NOT NULL,created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS drafts(user_id INTEGER PRIMARY KEY REFERENCES users(id),content TEXT NOT NULL,updated_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS login_limits(key TEXT PRIMARY KEY,failures INTEGER NOT NULL,blocked_until INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS users_class ON users(class_id);
        CREATE INDEX IF NOT EXISTS attempts_user ON attempts(user_id);
        ''')
        if seed_demo and not db.execute('SELECT id FROM users WHERE email=?',('teacher@codebloom.local',)).fetchone():
            teacher=db.execute('INSERT INTO users(name,email,password,role,created_at) VALUES(?,?,?,?,?)',('Ms. Meera Shah','teacher@codebloom.local',password_hash('Teach@123'),'teacher',now())).lastrowid
            class_id=db.execute('INSERT INTO classrooms(name,code,teacher_id) VALUES(?,?,?)',('Coding Explorers','BLOOM26',teacher)).lastrowid
            db.execute('UPDATE users SET class_id=? WHERE id=?',(class_id,teacher))
            db.execute('INSERT INTO users(name,email,password,role,grade,class_id,created_at) VALUES(?,?,?,?,?,?,?)',('Demo Student','student@codebloom.local',password_hash('Learn@123'),'student','8',class_id,now()))
            db.execute('INSERT INTO announcements(class_id,teacher_id,title,body,created_at) VALUES(?,?,?,?,?)',(class_id,teacher,'Welcome, coding explorers!','Start with Think like a coder, then build your first page. You can submit a project whenever you feel ready.',now()))

def public_user(db,user):
    u=dict(user); u.pop('password',None)
    c=db.execute('SELECT name,code FROM classrooms WHERE id=?',(u['class_id'],)).fetchone()
    u['class_name']=c['name'] if c else None
    u['class_code']=c['code'] if c else None
    return u

def summary(db,user_id):
    completed=[r['lesson_id'] for r in db.execute('SELECT lesson_id FROM completions WHERE user_id=?',(user_id,))]
    attempts=[dict(r) for r in db.execute('SELECT id,course_id,score,total,created_at FROM attempts WHERE user_id=? ORDER BY id DESC',(user_id,))]
    best={}
    for a in attempts: best[a['course_id']]=max(best.get(a['course_id'],0),a['score'])
    xp=len(completed)*20+sum(score*10 for score in best.values())
    return dict(completed=completed,attempts=attempts,best=best,xp=xp)

class Handler(BaseHTTPRequestHandler):
    server_version='CodeBloom/1.0'
    def log_message(self,format,*args):
        # Do not write student content, email addresses, cookies, or query strings to logs.
        pass
    def send(self,status,data=None,content_type='application/json; charset=utf-8',headers=None):
        payload=json.dumps(data,ensure_ascii=False).encode() if content_type.startswith('application/json') else data
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(payload)))
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Cache-Control','no-store' if content_type.startswith('application/json') else 'no-cache')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(payload)
    def body(self):
        try: size=int(self.headers.get('Content-Length','0'))
        except ValueError: raise AppError(400,'Invalid request size.')
        if not 0<size<=MAX_BODY: raise AppError(413,'Request is empty or too large.')
        try:
            data=json.loads(self.rfile.read(size))
            if not isinstance(data,dict): raise ValueError
            return data
        except (ValueError,UnicodeError): raise AppError(400,'Send a valid JSON object.')
    def origin_check(self):
        origin=self.headers.get('Origin')
        if origin and origin not in ('http://'+self.headers.get('Host',''),'https://'+self.headers.get('Host','')):
            raise AppError(403,'This request must come from the application.')
    def user(self,db,role=None,mutation=False):
        cookie=self.headers.get('Cookie','')
        token=next((p.strip()[3:] for p in cookie.split(';') if p.strip().startswith('cb=')), '')
        session=db.execute('SELECT * FROM sessions WHERE token=? AND expires>?',(token,now())).fetchone()
        if not session: raise AppError(401,'Please sign in to continue.')
        u=db.execute('SELECT * FROM users WHERE id=?',(session['user_id'],)).fetchone()
        if role and u['role']!=role: raise AppError(403,'This action is not available for your account.')
        if mutation and not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),session['csrf']):
            raise AppError(403,'Your session needs refreshing. Reload the page and try again.')
        return u,session
    def do_GET(self): self.dispatch('GET')
    def do_POST(self): self.dispatch('POST')
    def dispatch(self,method):
        try:
            path=urlsplit(self.path).path
            if path.startswith('/api/'):
                if method=='POST': self.origin_check()
                with database() as db:
                    result=self.api(db,method,path)
                if result is not None: self.send(200,result)
            elif method=='GET':
                static={'/':'index.html','/app.js':'app.js','/styles.css':'styles.css','/favicon.svg':'favicon.svg'}
                if path not in static: raise AppError(404,'Page not found.')
                file=ROOT/'static'/static[path]
                types={'.html':'text/html; charset=utf-8','.js':'application/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml'}
                self.send(200,file.read_bytes(),types[file.suffix])
            else: raise AppError(405,'Method not allowed.')
        except AppError as e: self.send(e.status,dict(error=e.message))
        except sqlite3.IntegrityError: self.send(409,dict(error='This record already exists. Please check your details.'))
        except (BrokenPipeError,ConnectionResetError): pass
        except Exception:
            self.send(500,dict(error='Something went wrong. Please try again.'))
    def api(self,db,method,path):
        if method=='GET' and path=='/api/health': return dict(ok=True)
        if method=='POST' and path in ('/api/login','/api/register'):
            data=self.body()
            email=str(data.get('email','')).strip().lower()
            password=str(data.get('password',''))
            if not re.fullmatch(r'[^\s@]{1,64}@[^\s@]{1,180}\.[^\s@]{1,30}',email): raise AppError(400,'Enter a valid email address.')
            if len(password)>128: raise AppError(400,'Password must be at most 128 characters.')
            if path=='/api/register':
                name=str(data.get('name','')).strip()
                if not 2<=len(name)<=60: raise AppError(400,'Your name must have 2–60 characters.')
                if len(password)<8: raise AppError(400,'Use a password with at least 8 characters.')
                if db.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone(): raise AppError(409,'An account with this email already exists.')
                grade=str(data.get('grade',''))
                if grade not in [str(x) for x in range(6,13)]: raise AppError(400,'Choose your class from 6 to 12.')
                code=str(data.get('class_code','')).strip().upper()
                classroom=db.execute('SELECT id FROM classrooms WHERE code=?',(code,)).fetchone() if code else None
                if code and not classroom: raise AppError(400,'That class code was not found. Ask your teacher to check it.')
                uid=db.execute('INSERT INTO users(name,email,password,role,grade,class_id,created_at) VALUES(?,?,?,?,?,?,?)',(name,email,password_hash(password),'student',grade,classroom['id'] if classroom else None,now())).lastrowid
                user=db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
            else:
                key=self.client_address[0]+':'+email
                limit=db.execute('SELECT * FROM login_limits WHERE key=?',(key,)).fetchone()
                if limit and limit['blocked_until']>now(): raise AppError(429,'Too many attempts. Please wait 5 minutes before trying again.')
                user=db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
                if not user or not password_matches(password,user['password']):
                    failures=(limit['failures'] if limit else 0)+1
                    if limit and limit['blocked_until'] and limit['blocked_until']<=now(): failures=1
                    db.execute('INSERT OR REPLACE INTO login_limits VALUES(?,?,?)',(key,failures,now()+300 if failures>=5 else 0))
                    db.commit() # Failed attempts persist even though the request returns an error.
                    raise AppError(401,'Email or password is incorrect.')
                db.execute('DELETE FROM login_limits WHERE key=?',(key,))
            db.execute('DELETE FROM sessions WHERE expires<=?',(now(),))
            token,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(24)
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(token,user['id'],csrf,now()+SESSION_SECONDS))
            db.commit()
            self.send(200,dict(user=public_user(db,user),csrf=csrf),headers={'Set-Cookie':f'cb={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_SECONDS}'})
            return None
        user,session=self.user(db,mutation=method=='POST')
        if method=='GET' and path=='/api/me': return dict(user=public_user(db,user),csrf=session['csrf'])
        if method=='POST' and path=='/api/logout':
            db.execute('DELETE FROM sessions WHERE token=?',(session['token'],));db.commit()
            self.send(200,dict(ok=True),headers={'Set-Cookie':'cb=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'});return None
        if method=='GET' and path=='/api/student':
            if user['role']!='student': raise AppError(403,'Student account required.')
            s=summary(db,user['id'])
            courses=[]
            for c in COURSES:
                safe={k:v for k,v in c.items() if k!='quiz'}
                safe['questions']=len(c['quiz']); courses.append(safe)
            return dict(courses=courses,challenges=CHALLENGES,progress=s,projects=[dict(r) for r in db.execute('SELECT * FROM projects WHERE user_id=? ORDER BY id DESC',(user['id'],))],announcements=[dict(r) for r in db.execute('SELECT a.*,u.name AS teacher FROM announcements a JOIN users u ON u.id=a.teacher_id WHERE a.class_id=? ORDER BY a.id DESC LIMIT 30',(user['class_id'],))],draft=(db.execute('SELECT content FROM drafts WHERE user_id=?',(user['id'],)).fetchone() or {'content':''})['content'])
        if method=='POST' and path=='/api/join':
            self.require_student(user); data=self.body(); code=str(data.get('code','')).strip().upper()
            c=db.execute('SELECT id FROM classrooms WHERE code=?',(code,)).fetchone()
            if not c: raise AppError(404,'Class code not found.')
            db.execute('UPDATE users SET class_id=? WHERE id=?',(c['id'],user['id']))
            return dict(ok=True)
        if method=='POST' and path=='/api/complete':
            self.require_student(user); lid=self.body().get('lesson_id')
            if lid not in [l['id'] for c in COURSES for l in c['lessons']]: raise AppError(404,'Lesson not found.')
            db.execute('INSERT OR IGNORE INTO completions VALUES(?,?,?)',(user['id'],lid,now()))
            return dict(progress=summary(db,user['id']))
        if method=='GET' and path.startswith('/api/quiz/'):
            self.require_student(user); c=COURSE_MAP.get(path.rsplit('/',1)[1])
            if not c: raise AppError(404,'Quiz not found.')
            return dict(course=c['id'],title=c['title'],questions=[dict(prompt=q['prompt'],options=q['options']) for q in c['quiz']])
        if method=='POST' and path=='/api/quiz':
            self.require_student(user);data=self.body();course_id=data.get('course_id');answers=data.get('answers')
            if not isinstance(course_id,str): raise AppError(400,'Choose a valid learning path.')
            c=COURSE_MAP.get(course_id)
            if not c: raise AppError(404,'Quiz not found.')
            if not isinstance(answers,list) or len(answers)!=len(c['quiz']) or any(type(a)!=int or a<0 or a>=len(q['options']) for a,q in zip(answers,c['quiz'])): raise AppError(400,'Answer every question before submitting.')
            score=sum(a==q['answer'] for a,q in zip(answers,c['quiz']))
            db.execute('INSERT INTO attempts(user_id,course_id,score,total,created_at) VALUES(?,?,?,?,?)',(user['id'],c['id'],score,len(answers),now()))
            return dict(score=score,total=len(answers),review=[dict(**q,chosen=a,correct=a==q['answer']) for a,q in zip(answers,c['quiz'])],progress=summary(db,user['id']))
        if method=='POST' and path=='/api/draft':
            self.require_student(user);data=self.body();content=self.text(data,'content',0,40000)
            db.execute('INSERT OR REPLACE INTO drafts VALUES(?,?,?)',(user['id'],content,now()));return dict(ok=True)
        if method=='POST' and path=='/api/projects':
            self.require_student(user);data=self.body();challenge=data.get('challenge_id')
            if challenge not in [c['id'] for c in CHALLENGES]: raise AppError(400,'Choose a valid challenge.')
            title=self.text(data,'title',3,100);content=self.text(data,'content',10,40000)
            pid=db.execute('INSERT INTO projects(user_id,challenge_id,title,content,created_at,updated_at) VALUES(?,?,?,?,?,?)',(user['id'],challenge,title,content,now(),now())).lastrowid
            return dict(ok=True,id=pid)
        if path.startswith('/api/teacher'):
            if user['role']!='teacher': raise AppError(403,'Teacher account required.')
            if method=='GET' and path=='/api/teacher':
                students=[]
                for r in db.execute("SELECT * FROM users WHERE class_id=? AND role='student' ORDER BY name",(user['class_id'],)):
                    s=summary(db,r['id']);students.append(dict(id=r['id'],name=r['name'],email=r['email'],grade=r['grade'],lessons=len(s['completed']),xp=s['xp'],quiz_average=round(sum(100*a['score']/a['total'] for a in s['attempts'])/len(s['attempts'])) if s['attempts'] else None))
                projects=[dict(r) for r in db.execute('SELECT p.*,u.name AS student FROM projects p JOIN users u ON u.id=p.user_id WHERE u.class_id=? ORDER BY p.id DESC',(user['class_id'],))]
                announcements=[dict(r) for r in db.execute('SELECT * FROM announcements WHERE class_id=? ORDER BY id DESC',(user['class_id'],))]
                return dict(students=students,projects=projects,announcements=announcements)
            if method=='POST' and path=='/api/teacher/announcements':
                data=self.body();title=self.text(data,'title',3,100);body=self.text(data,'body',5,2000)
                db.execute('INSERT INTO announcements(class_id,teacher_id,title,body,created_at) VALUES(?,?,?,?,?)',(user['class_id'],user['id'],title,body,now()));return dict(ok=True)
            if method=='POST' and path=='/api/teacher/review':
                data=self.body();pid=data.get('project_id');status=data.get('status');feedback=self.text(data,'feedback',1,2000)
                if type(pid)!=int or pid<1: raise AppError(400,'Choose a valid project.')
                if status not in ('reviewed','revise'): raise AppError(400,'Choose a valid review status.')
                p=db.execute('SELECT p.id FROM projects p JOIN users u ON u.id=p.user_id WHERE p.id=? AND u.class_id=?',(pid,user['class_id'])).fetchone()
                if not p: raise AppError(404,'Project not found in your classroom.')
                db.execute('UPDATE projects SET status=?,feedback=?,updated_at=? WHERE id=?',(status,feedback,now(),pid));return dict(ok=True)
            if method=='GET' and path=='/api/teacher/export':
                rows=db.execute("SELECT id,name,email,grade FROM users WHERE class_id=? AND role='student' ORDER BY name",(user['class_id'],)).fetchall()
                output=io.StringIO();writer=csv.writer(output);writer.writerow(['Student','Email','Class','Lessons completed','XP','Best quiz scores'])
                def cell(v):
                    value=str(v)
                    return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value
                for r in rows:
                    s=summary(db,r['id']);writer.writerow([cell(r['name']),cell(r['email']),r['grade'],len(s['completed']),s['xp'], '; '.join(k+': '+str(v)+'/5' for k,v in s['best'].items())])
                self.send(200,output.getvalue().encode('utf-8-sig'),'text/csv; charset=utf-8',{'Content-Disposition':'attachment; filename="codebloom-class-report.csv"'});return None
        raise AppError(404,'Endpoint not found.')
    @staticmethod
    def require_student(user):
        if user['role']!='student': raise AppError(403,'Student account required.')
    @staticmethod
    def text(data,key,minimum,maximum):
        value=data.get(key)
        if not isinstance(value,str) or not minimum<=len(value.strip())<=maximum: raise AppError(400,f'{key.capitalize()} must have {minimum}–{maximum} characters.')
        return value.strip()

def create_teacher(name,email,password,class_name):
    if len(password)<8: raise ValueError('Use at least 8 characters in the password.')
    if not 2<=len(name.strip())<=60 or not 2<=len(class_name.strip())<=80: raise ValueError('Teacher and classroom names are required (2–60 / 2–80 characters).')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): raise ValueError('Enter a valid email address.')
    code=secrets.token_hex(4).upper()
    with database() as db:
        uid=db.execute('INSERT INTO users(name,email,password,role,created_at) VALUES(?,?,?,?,?)',(name.strip(),email.strip().lower(),password_hash(password),'teacher',now())).lastrowid
        cid=db.execute('INSERT INTO classrooms(name,code,teacher_id) VALUES(?,?,?)',(class_name.strip(),code,uid)).lastrowid
        db.execute('UPDATE users SET class_id=? WHERE id=?',(cid,uid))
    return code

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='CodeBloom local school coding platform')
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--no-demo',action='store_true',help='Do not seed demonstration accounts')
    args=parser.parse_args();init_db(not args.no_demo)
    try:
        with ThreadingHTTPServer((args.host,args.port),Handler) as server:
            print(f'\nCodeBloom is ready: http://{args.host}:{args.port}\nPress Ctrl+C to stop.\n',flush=True)
            server.serve_forever()
    except KeyboardInterrupt: print('\nCodeBloom stopped. Your work is saved.\n')
    except OSError as exc: print(f'Could not start: {exc}\nTry a different port: python server.py --port 8001');raise SystemExit(1)
