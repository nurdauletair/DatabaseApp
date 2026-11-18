"""Create the Kazakh report only from completed real measurements. No API calls."""
import json
from pathlib import Path
import re
import textwrap
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Preformatted

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/lab12"
OUT = ROOT / "reports/Мұратов_Нұрдәулет_ЗС12.pdf"
data = json.loads((EVIDENCE / "evaluation.json").read_text())
fixture = json.loads((EVIDENCE / "fixture-check.json").read_text())
verification = json.loads((EVIDENCE / "verification.json").read_text())
assert data["complete"] and data["llm_evaluated"] and data["api_calls_attempted"] == 20
assert len(data["cases"]) == 10 and len(fixture["cases"]) == 10

# Prefer fonts with the full Kazakh Cyrillic range; portable fallbacks are supported.
font_candidates = [
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
]
for regular, bold in font_candidates:
    if Path(regular).exists():
        normal_font = TTFont("Clinic12", regular)
        pdfmetrics.registerFont(normal_font)
        bold_font = TTFont("Clinic12Bold", bold) if Path(bold).exists() else TTFont("Clinic12Bold", regular)
        if not all(ord(c) in bold_font.face.charWidths for c in "ӘәҒғҚқҢңӨөҰұҮүҺһІі"):
            bold_font = TTFont("Clinic12Bold", regular)
        pdfmetrics.registerFont(bold_font)
        break
else:
    raise SystemExit("Install a TrueType font supporting Kazakh Cyrillic (Arial Unicode or DejaVu Sans).")
pdfmetrics.registerFontFamily("Clinic12", normal="Clinic12", bold="Clinic12Bold", italic="Clinic12", boldItalic="Clinic12Bold")
TEAL = colors.HexColor("#0f766e")
INK = colors.HexColor("#233640")
MUTED = colors.HexColor("#61747c")
WIDTH = A4[0] - 92
styles = {
    "body": ParagraphStyle("Body12", fontName="Clinic12", fontSize=9.6, leading=14.2, spaceAfter=9, textColor=INK),
    "title": ParagraphStyle("Title12", fontName="Clinic12Bold", fontSize=25, leading=32, spaceAfter=18, textColor=TEAL),
    "heading": ParagraphStyle("Heading12", fontName="Clinic12Bold", fontSize=15, leading=20, spaceAfter=12, textColor=TEAL),
    "small": ParagraphStyle("Small12", fontName="Clinic12", fontSize=8.1, leading=11.4, spaceAfter=7, textColor=MUTED),
    "cell": ParagraphStyle("Cell12", fontName="Clinic12", fontSize=8.1, leading=11.3, textColor=INK),
    "code": ParagraphStyle("Code12", fontName="Clinic12", fontSize=8.1, leading=11.5, spaceAfter=10, backColor=colors.HexColor("#f1f6f5"), borderPadding=7),
}
story = []


def p(text, style="body"):
    story.append(Paragraph(text, styles[style]))


def heading(text):
    p(text, "heading")


def code(text):
    lines = []
    for line in text.splitlines():
        lines.extend(textwrap.wrap(line, width=91, replace_whitespace=False, drop_whitespace=False) or [""])
    story.append(Preformatted("\n".join(lines), styles["code"]))


def table(rows, widths):
    prepared = [[Paragraph(escape(str(cell)).replace("\n", "<br/>"), styles["cell"]) for cell in row] for row in rows]
    obj = Table(prepared, colWidths=widths, repeatRows=1, hAlign="LEFT")
    obj.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e1f3f1")),
        ("LINEBELOW", (0, 0), (-1, 0), .7, TEAL),
        ("LINEBELOW", (0, 1), (-1, -1), .25, colors.HexColor("#dfe8e7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([obj, Spacer(1, 10)])


def page():
    story.append(PageBreak())


def footer(canvas, doc):
    canvas.setStrokeColor(colors.HexColor("#dbe6e4"))
    canvas.line(46, 42, A4[0] - 46, 42)
    canvas.setFillColor(MUTED)
    canvas.setFont("Clinic12", 8)
    canvas.drawString(46, 28, "Емхана · 12-ЗС · Мұратов Нұрдәулет")
    canvas.drawRightString(A4[0] - 46, 28, str(doc.page))


live = data["accuracy"]
control = fixture["accuracy"]
date = data["date_context"]
display_date = ".".join(reversed(date.split("-")))
p("ДЕРЕКҚОР ЖӘНЕ ЖАСАНДЫ ИНТЕЛЛЕКТ · 12-ЗС", "small")
p("Табиғи тілдегі сұрақтан<br/>қауіпсіз SQL есебіне", "title")
p(f"Жоба: емхана қабылдауларын басқару<br/>Студент: Мұратов Нұрдәулет<br/>Бағалау күні: {display_date}<br/>Модель: {escape(data['model'])}")
heading("Жұмыстың мақсаты")
p("Django қосымшасына табиғи тілдегі сұрақ бойынша есеп алу мүмкіндігін қосу: модель SQL құрады, сервер оны тексереді және тек оқуға арналған PostgreSQL қосылымында орындайды. Пайдаланушы SQL мен нәтиже кестесін көреді. Жұмыс бұрынғы DatabaseApp жобасында, main тармағында жалғастырылды.")
heading("Өлшенген нәтиже")
table([
    ["Сынақ", "1-нұсқа: схема", "2-нұсқа: ережелер + мысалдар"],
    ["Жобаның бар деректері", f"{live['baseline']['correct']}/10 ({live['baseline']['percent']:.0f}%)", f"{live['enhanced']['correct']}/10 ({live['enhanced']['percent']:.0f}%)"],
    ["Бос емес бақылау деректері", f"{control['baseline']['correct']}/10 ({control['baseline']['percent']:.0f}%)", f"{control['enhanced']['correct']}/10 ({control['enhanced']['percent']:.0f}%)"],
], [200, 120, WIDTH-320])
p("10 қазақша сұраққа екі промптпен 20 нақты API сұранысы орындалды. Бақылау сынағында сол сақталған SQL қайта тексерілді; жаңа API сұраныстары жіберілген жоқ. Қате немесе шектеуден өткен жоқ жауаптар дұрыс деп саналмады.")
p(f"{verification['tests']['passed']} тест өтті. Бастапқы клиникалық кестелердің жол саны өзгермеді. Құпия кілт, дерекқор парольдері және нәтиже жолдары есепке немесе GitHub-қа қосылған жоқ.", "small")
page()

heading("1. Жүйе және деректер")
p("Бет: /report/. Мәзірдегі атауы: «Есептер». Тізбек: сұрақ формасы -> OpenAI API -> SQL тексеру -> read-only PostgreSQL -> HTML кестесі. Кіру құқығы әкімші мен тіркеушідегі blog.manage_clinic рұқсатымен тексеріледі. Дәрігер мен науқасқа жалпы есептер жабық.")
table([
    ["Үлгідегі ұғым", "Емханадағы баламасы"],
    ["Клиент, тауар, тапсырыс", "Patient, Doctor, Appointment"],
    ["Баға және сатылым күйі", "price және status; түсімге тек done кіреді"],
    ["Жеке есеп беті", "/report/: сұрақ, SQL, кесте және QueryLog"],
], [180, WIDTH-180])
counts=verification["row_counts"]
p(f"Базада {counts['blog_doctor']} дәрігер, {counts['blog_patient']} науқас профилі және {counts['blog_appointment']} қабылдау бар. Оның 20 000-ы is_training=True белгісімен бөлінген. Есептер 100 негізгі қабылдаумен жұмыс істейді. Дәрігер және науқас профильдерінің жалпы санына оқу профильдері де кіреді.")
table([
    ["Рұқсат етілген көрініс", "Бағандар"],
    ["report_doctors", "id, full_name, specialty"],
    ["report_patients", "id"],
    ["report_appointments", "id, doctor_id, patient_id, date, price, duration, status"],
], [160, WIDTH-160])
heading("2. Қауіпсіздік қабаттары")
p("SQLGlot PostgreSQL сұранысын AST түрінде талдайды. Тек бір қарапайым SELECT және нақты рұқсат етілген түйіндер, кестелер, бағандар мен функциялар қабылданады. WITH, ішкі сұраныс, UNION, SELECT INTO, блоктау, түсініктемелер, еркін функция және бірнеше команда қабылданбайды. LIMIT ең көбі 100 жолға шектеледі.")
p("Орындалу бөлек clinic_report_ro рөлімен, READ ONLY транзакциясында жүреді. Рөлге тек clinic_reports көріністеріне SELECT берілген. Негізгі пайдаланушыға ауысып орындау жоқ. statement_timeout - 3 секунд, lock_timeout - 1 секунд. INSERT, UPDATE, DELETE және бастапқы құпия кестелерді оқу дерекқор деңгейінде де рұқсатсыз.")
p("API кілті тек жергілікті .env ішінде; файл Git-тен шығарылған. Модельге схема мен сұрақ жіберіледі, PostgreSQL нәтижесі жіберілмейді. Сұраққа жеке дерек енгізбеу қажет. Науқастың аты, туған күні, телефоны, диагнозы, жазбалары, пароль және токендер рұқсат етілген көріністерде жоқ.", "small")
page()

heading("3. Бағалау әдісі және 10 сұрақ")
p("3 қарапайым, 4 орташа және 3 күрделі сұрақ үшін эталон SQL алдын ала жазылды. Әр сұрақ екі промптқа бір рет жіберілді. 1-нұсқа тек схема мен ортақ қауіпсіздік шарттарын алады. 2-нұсқаға бизнес-ережелер мен үш мысал қосылады. Екі нұсқада модель, дата контексті және SQL қорғанысы бірдей.")
p("Дұрыстық SQL мәтінімен емес, Counter(actual) == Counter(expected) арқылы жолдардың мультимножествасы бойынша өлшенді. Баған атауы мен жол ретінің айырмасы бағалауға әсер етпейді; артық/жетіспейтін баған, мән немесе жол - қате. Формула: дұрыс жауап саны / 10 × 100%.")
rows=[["№", "Қазақша сұрақ", "База\n1", "База\n2", "Бақылау\n1", "Бақылау\n2"]]
for c,f in zip(data["cases"],fixture["cases"],strict=True):
    rows.append([c["id"],c["question"], *('+' if good else 'x' for good in (
        c['baseline']['correct'],c['enhanced']['correct'],f['baseline']['correct'],f['enhanced']['correct']))])
table(rows,[22,269,48,48,58,WIDTH-445])
p("Белгі: + = дұрыс, x = қате/қабылданбады. Екі негіздегі нәтиже бөлек көрсетілді; бақылау нәтижесі бастапқы өлшеуді алмастырмайды.", "small")
page()

heading("4. Қателерді талдау")
p("<b>Статусты ойдан шығару.</b> 1-нұсқа №6, №8, №9 және №10 сұрақтарда completed мәнін қолданды. Модельдегі нақты код - done. №10 сұрағында бұл бос нәтиже беріп, эталондағы бес дәрігерге сәйкес келмеді. 2-нұсқада status мәндері мен түсім ережесін нақты беру бұл семантикалық қатені жойды.")
p("№8 бойынша бастапқы промпттың нақты SQL-ы:", "small")
code(data["cases"][7]["baseline"]["sql"])
p("<b>Кездейсоқ дұрыс нәтиже.</b> Қазіргі айдың деректері бойынша №8 эталоны нөл береді, №9 эталоны бос. Қате completed сүзгісі де сол нөл/бос нәтижені бергендіктен негізгі базада дұрыс болып саналды. Осылайша 80% - модельдің нақты семантикалық сапасын асыра көрсететін өлшем.")
p("Сондықтан бөлек, бір реттік PostgreSQL базасында синтетикалық бақылау жасалды: 7 дәрігер, 7 науқас, төрт статус, осы/өткен/одан бұрынғы ай, бір қабылдаусыз дәрігер және бір оқу қабылдауы. Барлық 10 эталонның нәтижесі бос емес. Бірдей SQL жауаптары қайта тексерілгенде бастапқы нұсқа 60%, жақсартылған нұсқа 90% алды. Бұл кейін жасалған диагностикалық бақылау, жаңа тәуелсіз LLM сынағы емес.")
p("<b>№6: синтаксис шектеуі және екіұштылық.</b> Екі модель де LEFT JOIN ішіне ON теңдігімен бірге AND status сүзгісін қосты. Бұл деректі өзгертетін SQL емес, бірақ guard рұқсат ететін тек екі баған теңдігі түріндегі қарапайым JOIN шартынан шығады. Сұраныс орындалмады және қате ретінде саналды.")
p("2-нұсқаның қабылданбаған SQL-ы:", "small")
code(data["cases"][5]["enhanced"]["sql"])
p("Сондай-ақ «әр дәрігер» барлық профильді нөлдік түсіммен қамту ма, әлде тек аяқталған қабылдауы бар дәрігерлер ме деген екіұштылық бар. Эталон алдын ала екінші мағынаны таңдаған. Болашақта сұрақты нақтылап, JOIN синтаксисін промптта көрсету немесе қауіпсіз AST шартын жеке тесттермен кеңейту керек. Осы бағалауда ереже мен эталон нәтиже үшін өзгертілген жоқ.", "small")
page()

heading("5. Тесттер және бағалау талаптары")
code((EVIDENCE / "tests.txt").read_text().strip())
p("24 жаңа тест SQL guard, API адаптері, рөлдер, бос нәтиже, HTML escaping, CSRF, тұрақты сұраныс лимиті және read-only рөлді тексереді. 118 жалпы тестке бұрынғы CRUD, API, Token/JWT, рөлдер және өнімділік тесттері де кіреді. Интеграциялық сынақта READ ONLY әдейі өшіріліп, рөлдің өз құқықтары да бастапқы кестелерге жазуға/оқуға тыйым салатыны тексерілді.")
p("QueryLog сұрақ, SQL, мәртебе, қате, уақыт пен токен метадеректерін сақтайды. Журналды кәдімгі Django қосылымы жазады; модельдің read-only қосылымы жазбайды. Суперпайдаланушы журналды админкадан көре алады. API нәтижесін жасыру үшін қате мәтіндері провайдердің бастапқы жауабын шығармайды.")
table([
    ["Презентациядағы критерий", "Балл", "Орындалған дәлел"],
    ["Модельдер және деректер", "1", "Емхананың бұрынғы модельдері және деректері сақталды"],
    ["LLM қызметі, промпт, .env", "1,5", "llm.py, schema.py, prompts.py; 20 нақты API жауабы"],
    ["validate_sql + read-only", "2", "AST тізімі, PostgreSQL рөлі, интеграциялық тесттер"],
    ["/report/: форма, SQL, кесте, лог", "1,5", "Есептер беті және QueryLog"],
    ["Кемінде 3 бірлік тест", "1", "24 жаңа тест; барлығы 118 тест өтті"],
    ["10 сұрақ, екі нұсқа, дәлдік", "2", "3/4/3 сұрақ; 80% -> 90%, бақылауда 60% -> 90%"],
    ["Қате талдауы және қорытынды", "1", "Осы есеп, нақты SQL және бос нәтиже мәселесінің талдауы"],
], [220,35,WIDTH-255])
p("Бұл кесте орындалған жұмысты критерийлермен сәйкестендіреді. Қорытынды бағаны оқытушы қояды.", "small")
heading("Қорытынды")
p("Нақты схемаға бизнес-ережелер мен мысал қосу маңызды семантикалық қатені азайтты: done орнына completed қолдану тоқтады. Бірақ тек SQL орындалуы немесе бос нәтижемен сәйкестік дұрыстықты дәлелдемейді. Бос емес бақылау бастапқы промпттың екі жасырын қатесін көрсетті. Қорғаныс қабаттары сұраныстың әсерін оқумен шектейді; 90% дәлдік қалған жауаптарды тексеру қажеттігін жоймайды.")
page()

heading("6. Қайта көрсету және файлдар")
code("cd /Users/nurdaulet/DatabaseApp\nsource venv/bin/activate\npython manage.py runserver\n# http://127.0.0.1:8000/report/\n# Login: demo_admin or demo_registrar")
p("Қазақша мысал: «Әр күй бойынша қабылдаулар саны қанша?» Нәтиже кестесі астындағы SQL бөлігін ашу арқылы сүзгі мен есеп шартын тексеруге болады. Құпия кілт немесе пароль көрсетілмейді.")
table([
    ["Файл", "Мазмұны"],
    ["reporting/golden.json", "10 сұрақ және эталон SQL"],
    ["evidence/lab12/evaluation.json", "20 нақты жауап, екі промпт, тексерілген SQL, бастапқы дәлдік"],
    ["evidence/lab12/evaluation.csv / evaluation.md", "10 сұрақ нәтижелерінің кестесі және қысқаша талдау"],
    ["evidence/lab12/fixture-check.json", "Сол SQL-дың бос емес синтетикалық бақылауы"],
    ["evidence/lab12/tests.txt / verification.json", "Тест қорытындысы, деректердің сақталуы және тексеру"],
    ["LAB12.md", "Орнату, қауіпсіздік және қорғау нұсқаулығы"],
], [235,WIDTH-235])
p("Жаңа API сұранысынсыз сақталған SQL-ды бақылау базасында қайта тексеру:", "small")
code("python scripts/verify_lab12_fixture.py --evaluation evidence/lab12/evaluation.json\npython scripts/build_lab12_report.py")
p("Жаңа жауаптармен бағалауды қайталау қажет болса ғана:", "small")
code("python manage.py evaluate_reports --run-llm")
p("Соңғы команда тағы 20 ақылы API сұранысын жасайды. Әдепкі evaluate_reports командасы тек эталондарды тексереді. Модель жауаптары әр іске қосқанда өзгеруі мүмкін; бұл есеп бір іске қосудың нәтижесін көрсетеді.", "small")
heading("Дереккөздер")
p("1. «12-апта · Лекция РПБД», 19-29-слайдтар: Text-to-SQL зертханасы және бағалау критерийлері.<br/>2. Жобаның нақты өлшеулері: evidence/lab12/evaluation.json және fixture-check.json.<br/>3. OpenAI API: https://developers.openai.com/api/docs/quickstart<br/>4. PostgreSQL READ ONLY: https://www.postgresql.org/docs/current/sql-set-transaction.html<br/>5. Репозиторий: https://github.com/nurdauletair/DatabaseApp", "small")
OUT.parent.mkdir(parents=True, exist_ok=True)
SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=46, rightMargin=46, topMargin=44, bottomMargin=55,
                  title="12-ЗС: Емханадағы қауіпсіз LLM есептері", author="Мұратов Нұрдәулет").build(story, onFirstPage=footer, onLaterPages=footer)
print(OUT)
