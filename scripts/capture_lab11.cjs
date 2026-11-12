const fs=require('node:fs'),path=require('node:path');
let playwright;try{playwright=require('playwright')}catch{playwright=require('/Applications/ChatGPT.app/Contents/Resources/cua_node/lib/node_modules/playwright-core')}
const root=path.resolve(__dirname,'..'), base=process.env.CLINIC_BASE_URL || 'http://127.0.0.1:8011';
(async()=>{
 const credentials=Object.fromEntries(fs.readFileSync(path.join(root,'.local-backups/demo-credentials.txt'),'utf8').split('\n').filter(x=>x.startsWith('demo_')).map(x=>x.split(': ')));
 const dest=path.join(root,'evidence/screenshots');fs.mkdirSync(dest,{recursive:true});
 const browser=await playwright.chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 const context=await browser.newContext({viewport:{width:1440,height:1050}}),page=await context.newPage();
 await page.setExtraHTTPHeaders({'Cache-Control':'no-cache'});
 const errors=[],results=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/login/');await page.locator('[name=username]').fill('demo_admin');await page.locator('[name=password]').fill(credentials.demo_admin);
 await Promise.all([page.waitForURL(base+'/'),page.locator('form button').first().click()]);
 await page.goto(base+'/lab11/');await page.screenshot({path:path.join(dest,'01-overview.png')});
 for(const [url,name]of[['slow','02-slow'],['optimized','03-optimized'],['cached','04-cache-miss'],['cached','05-cache-hit'],['cached','05-cache-hit'],['cached','05-cache-hit']]){
  const response=await page.goto(base+'/lab11/'+url+'/');await page.waitForLoadState('networkidle');
  if(response.status()!==200)throw Error(url+': '+response.status());
  results.push({page:url,status:response.status(),sql:response.headers()['x-sql-count']});
  await page.screenshot({path:path.join(dest,name+'.png')});
  if(url==='slow'||url==='optimized'){
   const sql=page.locator('a').filter({hasText:/SQL/});
   if(await sql.count()){
    await sql.first().click();await page.locator('#sqlMain_1').waitFor({state:'visible',timeout:15000});await page.locator('.djDebugSql').evaluateAll(nodes=>nodes.forEach(n=>{if(n.textContent.includes('django_session'))n.textContent='SELECT ... FROM django_session WHERE session_key = <redacted> (session credential hidden)';}));await page.screenshot({path:path.join(dest,name+'-sql.png')});
   }
  }
 }
 await context.close();
 const patient=await browser.newContext({viewport:{width:1440,height:1050}}),p=await patient.newPage();
 await p.goto(base+'/login/');await p.locator('[name=username]').fill('demo_patient');await p.locator('[name=password]').fill(credentials.demo_patient);
 await Promise.all([p.waitForURL(base+'/'),p.locator('form button').first().click()]);
 await p.goto(base+'/lab11/cached/');await p.waitForLoadState('networkidle');
 await p.screenshot({path:path.join(dest,'06-patient-isolation.png')});
 await browser.close();if(results.at(-1).sql!=='2')errors.push('Warm request must have only 2 auth SQL');
 fs.writeFileSync(path.join(root,'evidence/browser-checks.json'),JSON.stringify({results,errors},null,2));
 console.log(JSON.stringify({screenshots:fs.readdirSync(dest).length,results,errors}));if(errors.length)process.exitCode=1;
})().catch(e=>{console.error(e.message);process.exit(1);});
