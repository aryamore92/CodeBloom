/* Template and routing smoke tests in Node, without a browser or external packages.
   API behaviour is tested separately in test_app.py. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const script='import json; from content import COURSES, CHALLENGES; print(json.dumps({"courses":[{k:v for k,v in c.items() if k!="quiz"} for c in COURSES], "challenges": CHALLENGES}))';
let fixture;
for(const python of [process.env.PYTHON,'python3','python'].filter(Boolean)){
  try{fixture=JSON.parse(execFileSync(python,['-c',script],{cwd:root,encoding:'utf8'}));break;}catch{}
}
assert.ok(fixture,'Python is needed to load learning content.');
fixture.progress={completed:[],attempts:[],best:{},xp:0};fixture.projects=[];fixture.announcements=[];fixture.draft='';
const student={id:2,name:'Demo Student',email:'student@codebloom.local',role:'student',grade:'8',class_id:1,class_name:'Coding Explorers',class_code:'BLOOM26'};
const teacher={...student,id:1,name:'Ms. Meera Shah',role:'teacher',email:'teacher@codebloom.local'};
const teacherFixture={students:[{id:2,name:'Demo Student',email:student.email,grade:'8',lessons:0,xp:0,quiz_average:null}],projects:[],announcements:[]};
const elements={
 '#app':{innerHTML:''},'#modal':{innerHTML:'',open:false,addEventListener(){},showModal(){this.open=true;},close(){this.open=false;}},
 '#toast':{textContent:'',className:''},'#editor':{value:'<h1>Example</h1>'},'#preview':{srcdoc:''},'#save-state':{textContent:''}
};
const context=vm.createContext({
 document:{querySelector:s=>elements[s]||null,addEventListener(){},title:''},
 location:{hash:'#/overview'},window:{addEventListener(){},scrollTo(){}},
 navigator:{clipboard:{async writeText(){}}},setTimeout:()=>0,clearTimeout(){},console,
 async fetch(url){let value;if(url==='/api/me')value={user:student,csrf:'test-token'};else if(url==='/api/student')value=fixture;else if(url.startsWith('/api/quiz/'))value={course:url.split('/').pop(),title:'Quiz',questions:[{prompt:'A sample question?',options:['One','Two','Three','Four']}]};else value=teacherFixture;return {ok:true,status:200,async json(){return value;}};}
});
vm.runInContext(fs.readFileSync(path.join(root,'static/app.js'),'utf8'),context);
const evaluate=expression=>vm.runInContext(expression,context);
(async()=>{
 await new Promise(resolve=>setImmediate(resolve));
 let checks=0;
 for(const route of ['overview','courses','projects','playground','progress','resources','profile']){
   context.location.hash='#/'+route;await evaluate('render()');const html=elements['#app'].innerHTML;
   assert.ok(html.includes('id="main"'),route+' renders its main landmark');
   assert.ok(!html.includes('undefined'),route+' has no undefined values');
   assert.ok(html.includes('class="sidebar"'),route+' renders navigation');checks++;
 }
 for(const course of fixture.courses)for(const lesson of course.lessons){
   context.location.hash=`#/course/${course.id}/${lesson.id}`;await evaluate('render()');
   assert.ok(elements['#app'].innerHTML.includes(lesson.title));assert.ok(elements['#app'].innerHTML.includes('Mark as complete'));checks++;
 }
 for(const course of fixture.courses){context.location.hash='#/quiz/'+course.id;await evaluate('render()');assert.ok(elements['#app'].innerHTML.includes('id="quiz-form"'));checks++;}
 evaluate('user=null; data=null;');await evaluate('render()');assert.ok(elements['#app'].innerHTML.includes('Small steps.'));checks++;
 await evaluate('auth("login")');assert.ok(elements['#modal'].innerHTML.includes('type="password"'));checks++;
 await evaluate('auth("register")');assert.ok(elements['#modal'].innerHTML.includes('name="grade"'));checks++;
 context.teacher=teacher;context.teacherFixture=teacherFixture;
 evaluate('user=teacher; data=teacherFixture;');
 for(const route of ['overview','students','reviews','announcements','profile']){
   context.location.hash='#/'+route;await evaluate('render()');assert.ok(elements['#app'].innerHTML.includes('id="main"'));assert.ok(!elements['#app'].innerHTML.includes('undefined'));checks++;
 }
 context.student=student;context.fixture=fixture;
 evaluate('user=student; data=fixture;');
 fixture.projects=[{id:1,title:'<script>alert(1)</script>',content:'</code><img src=x onerror=alert(1)>',status:'submitted',feedback:'<b>Text only</b>',created_at:1}];
 await evaluate('viewProject(1)');assert.ok(!elements['#modal'].innerHTML.includes('<img src=x'));assert.ok(elements['#modal'].innerHTML.includes('&lt;img'));checks++;
 evaluate('runCode()');assert.ok(elements['#preview'].srcdoc.includes("connect-src 'none'"));assert.ok(elements['#preview'].srcdoc.includes('<h1>Example</h1>'));checks++;
 assert.equal(evaluate('esc("<>&\\\"\\\'")'),'&lt;&gt;&amp;&quot;&#39;');checks++;
 console.log(`${checks} interface template and routing checks passed.`);
})().catch(error=>{console.error(error);process.exitCode=1;});
