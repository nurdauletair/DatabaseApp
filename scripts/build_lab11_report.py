"""Build the Kazakh lab report from measured evidence; no invented timings."""
from pathlib import Path
from xml.sax.saxutils import escape
import json, re, textwrap
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, Preformatted, KeepTogether

ROOT = Path(__file__).resolve().parents[1]
if ROOT == Path('/private'):
    ROOT = Path('/Users/nurdaulet/DatabaseApp')
OUT = ROOT/'reports/Мұратов_Нұрдәулет_ЗС11.pdf'
OUT.parent.mkdir(exist_ok=True)
pdfmetrics.registerFont(TTFont('Clinic','/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
pdfmetrics.registerFont(TTFont('ClinicBold','/System/Library/Fonts/Supplemental/Arial Bold.ttf'))
pdfmetrics.registerFontFamily('Clinic',normal='Clinic',bold='ClinicBold',italic='Clinic',boldItalic='ClinicBold')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='ClinicBody',fontName='Clinic',fontSize=10.2,leading=15,spaceAfter=9,textColor=colors.HexColor('#263b47')))
styles.add(ParagraphStyle(name='ClinicTitle',fontName='ClinicBold',fontSize=25,leading=32,textColor=colors.HexColor('#0f766e'),spaceAfter=16))
styles.add(ParagraphStyle(name='ClinicHeading',fontName='ClinicBold',fontSize=15,leading=20,textColor=colors.HexColor('#0f766e'),spaceAfter=11))
styles.add(ParagraphStyle(name='ClinicSmall',fontName='Clinic',fontSize=8.5,leading=12,spaceAfter=7))
styles.add(ParagraphStyle(name='ClinicCode',fontName='Courier',fontSize=7.1,leading=10,spaceAfter=10,backColor=colors.HexColor('#f1f5f5'),borderPadding=7))
story=[]
def p(text,style='ClinicBody'): story.append(Paragraph(text,styles[style]))
def title(text): p(text,'ClinicHeading')
def code(text): story.append(Preformatted('\n'.join(textwrap.fill(line,105,replace_whitespace=False,drop_whitespace=False) if len(line)>105 else line for line in text.splitlines()),styles['ClinicCode']))
def table(rows,widths):
    prepared=[[Paragraph(escape(str(cell)),styles['ClinicSmall']) for cell in row] for row in rows]
    obj=Table(prepared,colWidths=widths,repeatRows=1,hAlign='LEFT')
    obj.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e1f3f1')),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#0f766e')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#e3e9ec'))]))
    story.extend([obj,Spacer(1,12)])
def image(name,width=475):
    path=ROOT/'evidence/screenshots'/name
    if path.exists():
        from PIL import Image as PILImage
        w,h=PILImage.open(path).size
        story.append(Image(str(path),width=width,height=width*h/w,hAlign='LEFT'))
        story.append(Spacer(1,8))
    else:p('Скриншот файлы: '+name,'ClinicSmall')
files=['02-profiled-baseline.json','03-optimized.json','04-indexed.json','05-cache-miss.json','05-cache-hit.json']
measurements=[json.loads((ROOT/'evidence'/f).read_text()) for f in files]
labels=['Бастапқы нұсқа','N+1 түзетілген','Индекс қосылған','Кэш: miss','Кэш: hit']
def footer(canvas,doc):
    canvas.setStrokeColor(colors.HexColor('#d8e4e2'));canvas.line(46,43,A4[0]-46,43)
    canvas.setFont('Clinic',8);canvas.setFillColor(colors.HexColor('#60747b'))
    canvas.drawString(46,29,'Емхана · 11-ЗС · Мұратов Нұрдәулет')
    canvas.drawRightString(A4[0]-46,29,str(doc.page))

p('11-зертханалық сабақ','ClinicSmall')
p('Django қосымшасының<br/>өнімділігін арттыру','ClinicTitle')
p('Жоба: емхана қабылдауларын басқару<br/>Студент: Мұратов Нұрдәулет<br/>Өлшеу күні: 12.11.2026')
title('Мақсат және жұмыс ортасы')
p('Мақсат - бір беттің деректеріне кететін SQL санын кемінде 10 есе азайту. Жұмыс бұрынғы /Users/nurdaulet/DatabaseApp жобасында және PostgreSQL clinic_db базасында жалғасты. Әр негізгі кезең жеке Git-коммитпен сақталды.')
p('Орта: macOS Apple Silicon, Python 3.14, Django 6.1.2, Django Debug Toolbar 8.0.0, PostgreSQL 17.11, LocMemCache. Барлық кезең бір компьютерде өлшенді.')
table([['Блог үлгісі','Емханадағы баламасы','Оқу деректері'],['Author','Doctor','200 дәрігерден тұратын пул'],['Tag','Diagnosis','50 оқу диагнозы'],['Post','Appointment','20 000 оқу қабылдауы'],['Comment','AppointmentNote','60 000 жазба'],['Қосымша байланыс','Patient','2 000 науқастан тұратын пул']],[100,170,225])
p('Оқу деректері is_training=True белгісімен бөлінді. Бұрынғы 100 қабылдау, 20 дәрігер, 32 науқас, 5 диагноз және олардың байланыстары резервтік SQL көшірмемен салыстырылды; бастапқы клиникалық жолдар сақталған. Тексеру: evidence/data-integrity.json.','ClinicSmall')
title('Нәтиже')
p('<b>201 → 2 SQL</b>: деректер сұраныстары 100,5 есе азайды. Жылы кэш деректерге 0 SQL орындайды. Толық HTTP сұранысында сеанс пен пайдаланушыны тексеруге 2 SQL қалады.')
story.append(PageBreak())

title('Өлшеу әдісі және нәтижелер')
p('Әр кезеңде бес қайталау жасалып, медиана есептелді. SQL уақыты connection.execute_wrapper және time.perf_counter арқылы өлшенді. Бет уақыты HTML құруды қамтиды; браузер желісі мен ресурстарды жүктеу уақытын қамтымайды. Toolbar өлшеу кезінде өшірілді, ал браузерлік скриншоттарда қосулы.')
p('1-кесте. Пайдаланушы алдын ала анықталған кездегі деректер мен HTML құру.','ClinicSmall')
rows=[['Кезең','SQL саны','SQL, мс','Бет, мс']]
for label,d in zip(labels,measurements):
 m=d['business']['median'];rows.append([label,int(m['sql_count']),f"{m['sql_ms']:.3f}",f"{m['page_ms']:.3f}"])
table(rows,[220,75,100,100])
p('2-кесте. Сеанс, авторизация және middleware бар толық HTTP өңдеу.','ClinicSmall')
rows=[['Кезең','SQL саны','SQL, мс','Бет, мс']]
for label,d in zip(labels,measurements):
 m=d['http']['median'];rows.append([label,int(m['sql_count']),f"{m['sql_ms']:.3f}",f"{m['page_ms']:.3f}"])
table(rows,[220,75,100,100])
p('Кэш miss кезінде үш қосымша SQL сайдбар статистикасын есептейді: сондықтан деректер саны 2-ден 5-ке өседі. Hit кезінде кесте мен статистика дайын жауаптан беріледі. CSRF cookie тұрақтануы үшін hit өлшемінен бұрын екі прогрев орындалды.')
p('Барлық кезеңдегі кесте HTML-ының SHA-256 мәні бірдей. Кэш нұсқасы кестеге қосымша статистика береді. Салыстырудағы толық бес үлгі мен нақты уақыттар evidence/*.json файлдарында сақталған.','ClinicSmall')
story.append(PageBreak())

title('N+1, индекс және EXPLAIN')
p('Медлендіктің себебі: 1 негізгі SELECT + 50 дәрігер + 50 науқас + 50 диагноз жиыны + 50 жазба саны = 201 SQL. select_related дәрігер мен науқасты JOIN арқылы жүктейді; prefetch_related диагноздарды бір қосымша SQL арқылы алады. annotate(Count("notes")) санауды SQL-де орындайды. Алдымен 50 ID таңдалып, содан кейін ғана олардың жазбалары саналады; defer("reason") ұзын мәтінді тізімге жүктемейді.')
code('models.Index(fields=["status", "-date"], name="appt_status_date_idx")')
p('Сүзгі: WHERE is_training AND status=planned ORDER BY date DESC LIMIT 50. Төменде PostgreSQL-дың нақты ANALYZE, BUFFERS шығыстары берілген.','ClinicSmall')
p('<b>Индекс қосылғанға дейін</b>')
code((ROOT/'evidence/04-explain-filter-before.txt').read_text())
p('<b>Индекс қосылғаннан кейін</b>')
code((ROOT/'evidence/04-explain-filter-after.txt').read_text())
p('Индекс SQL-командалар санын өзгертпейді, бірақ сүзу мен сұрыптаудың орындалуын жылдамдатады. Жоспар табиғи түрде Index Scan таңдады; планировщик параметрлері мәжбүрлі өзгертілмеді. Толық JOIN/COUNT жоспарлары да evidence/04-explain-optimized-*.txt ішінде сақталған.','ClinicSmall')
story.append(PageBreak())

title('Debug Toolbar: браузердегі тексеру')
p('Скриншоттар жергілікті нақты сайттан алынды. Toolbar 203 және 4 SQL көрсетеді: екеуінде де деректер SQL-ына сеанс пен пайдаланушының 2 сұранысы қосылады. Сеанс кілттері суреттерде жасырылған.','ClinicSmall')
p('Бастапқы нұсқа: қайталанатын сұраныстар.','ClinicSmall');image('02-slow-sql.png',420)
p('Оңтайландырылған нұсқа: JOIN/COUNT, диагноздар және 2 авторизация сұранысы.','ClinicSmall');image('03-optimized-sql.png',420)
story.append(PageBreak())

title('Кэш, жарамсыздау және тесттер')
p('LocMemCache: бет пен кестенің жүктелген деректері 60 секундқа, статистика 600 секундқа сақталады. Деректердің қосымша кэші Cookie өзгергенде де SQL-ды қайталамайды. Пайдаланушы мен manage_clinic рұқсаты кілтке кіреді; Vary: Cookie сеанстарды бөледі. Рұқсат серверлік кэшке дейін тексеріледі, сыртқы жауап Cache-Control: private алады.')
p('Appointment, AppointmentNote, Diagnosis, Doctor, Patient сақталғанда/өшірілгенде және диагноздардың M2M байланысы өзгергенде transaction.on_commit кэш нұсқасын жаңартады. Ескі кілттер енді қолданылмайды. Bulk операциялар сигнал шығармайды: олардан кейін invalidate() анық шақырылуы керек. LocMem бір процесс үшін жеткілікті; бірнеше процесс үшін ортақ backend қажет.','ClinicSmall')
image('05-cache-hit.png',455)
title('Тест нәтижесі')
text=(ROOT/'evidence/tests.txt').read_text();m=re.search(r'Ran \d+ tests.*?\n\nOK',text,re.S)
code(m.group(0) if m else text[-500:])
p('Тексерілгені: бірдей нәтиже және 2 SQL; ұзын өрісті кейін жүктеу; cache hit-та 0 деректер SQL; пациенттерді оқшаулау; рұқсатты кері қайтару; commit-тен кейін статистиканы және M2M кэшін жаңарту. Бұрынғы CRUD, API, рөлдер және Token/JWT тесттері де өтті.','ClinicSmall')
story.append(PageBreak())

title('Қайта көрсету және қорғау')
code('cd /Users/nurdaulet/DatabaseApp\nsource venv/bin/activate\npython manage.py runserver\n# Browser: http://127.0.0.1:8000/lab11/\n# Login: demo_admin; use the existing local credentials file\npython manage.py test --verbosity 2\ntail -f .local-backups/perf.log')
p('Үш бет: /lab11/slow/, /lab11/optimized/, /lab11/cached/. Қайта өлшеу командалары LAB11.md ішінде. Қазіргі базаға индекс орнатылған; бастапқы жоспарлар индекске дейін бөлек сақталды. Бастапқы perf.log және JSON уақыттары Toolbar скриншоттарындағы мәндерден өзгеше болуы мүмкін: браузерлік Toolbar қосымша шығын енгізеді.','ClinicSmall')
title('Қорытынды')
p('Ең үлкен SQL үнемін N+1 мәселесін түзету берді: сұраныстар саны 201-ден 2-ге түсті. select_related дәрігер мен науқасты JOIN арқылы алып, prefetch_related диагноздарды бір сұраныспен жүктеді. Жазбаларды annotate арқылы санау және алдымен 50 ID таңдау артық агрегаттауды азайтты. Құрама индекс сүзу мен сұрыптау жоспарын Seq Scan + Sort түрінен Index Scan түріне өзгертті. Кэш қайталанған есептеуді жойды, бірақ алғашқы miss кезінде қосымша статистика есептелді. Тиісті сигналдар мен commit-тен кейінгі нұсқа жаңартуы ескі нәтижені қолдануға жол бермейді. Индекс диск пен жазу шығынын, ал кэш жад пен жарамсыздау логикасын талап етеді; бұл шығындар өлшеумен негізделді.')
title('Бақылау сұрақтары')
p('<b>Неге select_related диагноздарға жарамайды?</b> Бұл M2M байланысы; бөлек prefetch сұранысы негізгі жолдарды көбейтпейді.<br/><b>Индекс SQL санын неге өзгертпеді?</b> Ол бар SELECT-тің орындалу тәсілін өзгертеді.<br/><b>(status, date) тек date үшін тиімді ме?</b> Кепіл жоқ; нақты жоспар EXPLAIN арқылы тексеріледі.<br/><b>Кэш қашан ескі болады?</b> TTL немесе invalidate орындалғанға дейін; bulk жаңарту анық invalidate талап етеді.<br/><b>DEBUG неге продакшнда өшірулі?</b> Диагностикалық ақпаратты жарияламау және қосымша шығынды болдырмау үшін.','ClinicSmall')
p('Дереккөздер: «11-апта · Django өнімділігі», 20-30-слайдтар; Django cache framework: docs.djangoproject.com/en/6.1/topics/cache/; Debug Toolbar: django-debug-toolbar.readthedocs.io/en/stable/installation.html.','ClinicSmall')
SimpleDocTemplate(str(OUT),pagesize=A4,leftMargin=46,rightMargin=46,topMargin=44,bottomMargin=54,title='11-ЗС · Емхана өнімділігі',author='Мұратов Нұрдәулет').build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT)
