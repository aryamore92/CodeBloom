"""End-to-end API checks using an isolated temporary database."""
import http.client, json, os, sqlite3, sys, tempfile, threading, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from content import COURSE_MAP

class Client:
    def __init__(self,port): self.port=port;self.cookie='';self.csrf=''
    def request(self,path,body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=10)
        h={'Cookie':self.cookie,'X-CSRF-Token':self.csrf,**(headers or {})}
        if body is not None: h['Content-Type']='application/json'
        conn.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,h)
        r=conn.getresponse();raw=r.read();status=r.status;response_headers=dict(r.getheaders())
        if 'Set-Cookie' in response_headers:self.cookie=response_headers['Set-Cookie'].split(';')[0]
        data=json.loads(raw) if response_headers.get('Content-Type','').startswith('application/json') else raw.decode('utf-8-sig')
        if isinstance(data,dict) and 'csrf' in data:self.csrf=data['csrf']
        conn.close();return status,data,response_headers
    def login(self,role='student'):
        return self.request('/api/login',dict(email=role+'@codebloom.local',password='Teach@123' if role=='teacher' else 'Learn@123'))

class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();server.DB_PATH=Path(self.temp.name)/'test.db';server.init_db()
        self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.student=Client(self.http.server_port);self.teacher=Client(self.http.server_port)
        self.student.login();self.teacher.login('teacher')
    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join();self.temp.cleanup()
    def test_01_static_assets_and_security_headers(self):
        for path in ['/','/app.js','/styles.css','/favicon.svg']:
            status,body,h=self.student.request(path);self.assertEqual(status,200);self.assertTrue(body);self.assertEqual(h['X-Content-Type-Options'],'nosniff')
        self.assertEqual(self.student.request('/../server.py')[0],404)
    def test_02_auth_required_and_student_cannot_access_teacher(self):
        anonymous=Client(self.http.server_port)
        self.assertEqual(anonymous.request('/api/student')[0],401)
        self.assertEqual(self.student.request('/api/teacher')[0],403)
        self.assertEqual(self.teacher.request('/api/student')[0],403)
    def test_03_passwords_hashed_and_cookie_protected(self):
        with server.database() as db:
            row=db.execute('SELECT password FROM users LIMIT 1').fetchone();self.assertNotIn('Teach@123',row['password']);self.assertIn(':',row['password'])
        _,_,headers=self.student.login();self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Strict',headers['Set-Cookie'])
    def test_04_registration_and_duplicate_email(self):
        c=Client(self.http.server_port);payload=dict(name='New Learner',email='new@example.local',password='Newpass123',grade='7',class_code='BLOOM26')
        status,result,_=c.request('/api/register',payload);self.assertEqual(status,200);self.assertEqual(result['user']['role'],'student');self.assertEqual(result['user']['class_code'],'BLOOM26')
        self.assertEqual(c.request('/api/register',payload)[0],409)
    def test_05_registration_validation(self):
        c=Client(self.http.server_port);payload=dict(name='New Student',email='new@example.local',password='12345678',grade='7')
        for patch in [dict(password='short'),dict(grade='3'),dict(class_code='MISSING'),dict(email='wrong'),dict(name='x')]:
            self.assertEqual(c.request('/api/register',{**payload,**patch})[0],400)
    def test_06_csrf_and_cross_origin_checks(self):
        self.assertEqual(self.student.request('/api/complete',{'lesson_id':'f1'},{'X-CSRF-Token':'wrong'})[0],403)
        self.assertEqual(self.student.request('/api/complete',{'lesson_id':'f1'},{'Origin':'https://foreign.example'})[0],403)
    def test_07_lesson_completion_is_idempotent(self):
        for _ in range(2):status,result,_=self.student.request('/api/complete',{'lesson_id':'f1'});self.assertEqual(status,200)
        self.assertEqual(result['progress']['completed'],['f1']);self.assertEqual(result['progress']['xp'],20)
        self.assertEqual(self.student.request('/api/complete',{'lesson_id':'unknown'})[0],404)
    def test_08_answers_hidden_until_submission(self):
        _,result,_=self.student.request('/api/quiz/web')
        self.assertNotIn('answer',result['questions'][0]);self.assertNotIn('explanation',result['questions'][0])
        _,student,_=self.student.request('/api/student');self.assertNotIn('quiz',student['courses'][0])
    def test_09_all_quizzes_score_on_server(self):
        for id,c in COURSE_MAP.items():
            status,r,_=self.student.request('/api/quiz',dict(course_id=id,answers=[q['answer'] for q in c['quiz']],score=999))
            self.assertEqual(status,200);self.assertEqual(r['score'],5);self.assertTrue(all(q['correct'] for q in r['review']))
        self.assertEqual(r['progress']['xp'],200)
    def test_10_retries_award_only_best_score(self):
        answers=[q['answer'] for q in COURSE_MAP['web']['quiz']]
        for _ in range(2):_,r,_=self.student.request('/api/quiz',dict(course_id='web',answers=answers))
        self.assertEqual(r['progress']['xp'],50);self.assertEqual(len(r['progress']['attempts']),2)
    def test_11_quiz_rejects_incomplete_and_invalid_answers(self):
        for answers in [[],[0],[999]*5,[True]*5,['0']*5]:self.assertEqual(self.student.request('/api/quiz',dict(course_id='web',answers=answers))[0],400)
    def test_12_draft_and_progress_survive_new_session(self):
        text='<h1>My saved work</h1>'
        self.assertEqual(self.student.request('/api/draft',{'content':text})[0],200)
        self.student.request('/api/complete',{'lesson_id':'w1'})
        new=Client(self.http.server_port);new.login();_,r,_=new.request('/api/student')
        self.assertEqual(r['draft'],text);self.assertIn('w1',r['progress']['completed'])
    def test_13_project_submission_review_and_feedback(self):
        status,r,_=self.student.request('/api/projects',dict(challenge_id='hello',title='My website',content='<h1>Hello, world!</h1>'));self.assertEqual(status,200)
        _,t,_=self.teacher.request('/api/teacher');self.assertEqual(len(t['projects']),1)
        self.assertEqual(self.teacher.request('/api/teacher/review',dict(project_id=r['id'],status='reviewed',feedback='Great heading. Try adding a list.'))[0],200)
        _,s,_=self.student.request('/api/student');self.assertEqual(s['projects'][0]['status'],'reviewed');self.assertIn('Great heading',s['projects'][0]['feedback'])
    def test_14_teacher_cannot_review_another_classroom(self):
        code=server.create_teacher('Other Teacher','other@example.local','Password123','Other Class')
        other=Client(self.http.server_port);other.request('/api/login',dict(email='other@example.local',password='Password123'))
        _,r,_=self.student.request('/api/projects',dict(challenge_id='hello',title='Private project',content='My school coding project.'))
        self.assertEqual(other.request('/api/teacher/review',dict(project_id=r['id'],status='reviewed',feedback='Not my student'))[0],404)
        self.assertEqual(other.request('/api/teacher')[1]['students'],[])
    def test_15_announcements_scoped_to_classroom(self):
        self.teacher.request('/api/teacher/announcements',dict(title='Friday coding',body='Build your first webpage on Friday.'))
        _,s,_=self.student.request('/api/student');self.assertEqual(s['announcements'][0]['title'],'Friday coding')
        independent=Client(self.http.server_port);independent.request('/api/register',dict(name='Independent',email='ind@example.local',password='Password123',grade='6'))
        self.assertEqual(independent.request('/api/student')[1]['announcements'],[])
    def test_16_csv_export_and_formula_escape(self):
        new=Client(self.http.server_port);new.request('/api/register',dict(name='=SUM(1,2)',email='formula@example.local',password='Password123',grade='6',class_code='BLOOM26'))
        status,csv,h=self.teacher.request('/api/teacher/export');self.assertEqual(status,200);self.assertIn('Lessons completed',csv);self.assertIn("'=SUM",csv)
        self.assertEqual(self.student.request('/api/teacher/export')[0],403)
    def test_17_login_rate_limit_persists(self):
        c=Client(self.http.server_port)
        for _ in range(5):self.assertEqual(c.request('/api/login',dict(email='no@example.local',password='wrongpass'))[0],401)
        self.assertEqual(c.request('/api/login',dict(email='no@example.local',password='wrongpass'))[0],429)
    def test_18_logout_invalidates_session(self):
        self.assertEqual(self.student.request('/api/logout',{})[0],200);self.assertEqual(self.student.request('/api/me')[0],401)
    def test_19_classroom_join_and_validation(self):
        c=Client(self.http.server_port);c.request('/api/register',dict(name='New Learner',email='class@example.local',password='Password123',grade='9'))
        self.assertEqual(c.request('/api/join',{'code':'bad'})[0],404)
        self.assertEqual(c.request('/api/join',{'code':'bloom26'})[0],200)
        self.assertEqual(c.request('/api/me')[1]['user']['class_code'],'BLOOM26')
    def test_20_invalid_project_and_review_status(self):
        self.assertEqual(self.student.request('/api/projects',dict(challenge_id='unknown',title='Test',content='Long enough content'))[0],400)
        self.assertEqual(self.teacher.request('/api/teacher/review',dict(project_id=1,status='invalid',feedback='Feedback'))[0],400)
        self.assertEqual(self.teacher.request('/api/teacher/review',dict(project_id={},status='reviewed',feedback='Feedback'))[0],400)
        self.assertEqual(self.student.request('/api/quiz',dict(course_id=[],answers=[0]*5))[0],400)

if __name__=='__main__':unittest.main(verbosity=2)
