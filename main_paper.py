from flask import Blueprint, request, render_template_string
import sqlite3, requests
from bs4 import BeautifulSoup
import json
import re

# 1. Blueprint Definition
main_bp = Blueprint('main_bp', __name__)

# 2. Database Helper
def init_db():
    conn = sqlite3.connect('ssc_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS results 
                      (roll_no TEXT PRIMARY KEY, name TEXT, score REAL, 
                       category TEXT, shift TEXT, exam_date TEXT, venue TEXT, comp_score REAL)''')
    conn.commit()
    conn.close()

# 3. HTML Templates
LEADERBOARD_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Global Leaderboard</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f4f7f6; padding: 40px; text-align: center; }
        .card { max-width: 800px; margin: auto; background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; border-bottom: 1px solid #eee; text-align: left; }
        th { background: #007bff; color: white; }
        .back-link { display: inline-block; margin-top: 20px; text-decoration: none; color: #007bff; font-weight: bold; }
    </style>
</head>
<body>
    <div class="card">
        <h1>🏆 Top 10 Scorers (Main)</h1>
        <table>
            <tr><th>Rank</th><th>Name</th><th>Score</th><th>Category</th><th>Shift</th></tr>
            {% for p in players %}
            <tr><td>{{ loop.index }}</td><td>{{ p[0] }}</td><td>{{ p[1] }}</td><td>{{ p[2] }}</td><td>{{ p[3] }}</td></tr>
            {% endfor %}
        </table>
        <a href="/main/" class="back-link">← Back to Checker</a>
    </div>
</body>
</html>
'''

HTML_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <title>SSC Pro Rank Checker</title>
    <style>
        @media print { form, .print-hide { display: none !important; } .container { box-shadow: none; border: none; } }
        body { font-family: 'Segoe UI', sans-serif; background: #f4f7f6; padding: 20px; }
        .container { max-width: 1000px; margin: auto; background: white; padding: 25px; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
        .rank-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin: 20px 0; }
        .rank-card { background: #fff; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #dee2e6; }
        .percentile { font-size: 12px; color: #28a745; font-weight: bold; }
        .total-box { background: #28a745; color: white; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px; }
        .print-btn { background: #6c757d; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #eee; padding: 12px; text-align: left; }
    </style>
</head>
<body>
    <div class="container">
        <div style="display: flex; justify-content: space-between;" class="print-hide">
            <h2>SSC Advanced Analytics</h2>
            <a href="/main/leaderboard" style="color: #007bff; text-decoration: none; font-weight: bold;">View Leaderboard →</a>
        </div>
        <form method="POST" class="print-hide">
            <input type="text" name="url" placeholder="Paste Answer Key Link" style="width:60%; padding:12px;" required>
            <select name="category" style="padding:12px;">
                <option value="UR">UR</option><option value="OBC">OBC</option>
                <option value="EWS">EWS</option><option value="SC">SC</option><option value="ST">ST</option>
            </select>
            <button type="submit" style="padding:12px 25px; background:#007bff; color:white; border:none; border-radius:5px; cursor:pointer;">Analyze</button>
        </form>

        {% if d %}
        <div style="margin-top:20px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3>Candidate: {{ d.name }}</h3>
                <button onclick="window.print()" class="print-btn print-hide">Download PDF</button>
            </div>
            
            <div class="total-box">
                <h3 style="margin:0;">Final Total Score (Subject 1-4)</h3>
                <h1 style="margin:5px 0;">{{ d.score }} / 390</h1>
            </div>

            <div class="rank-grid">
                <div class="rank-card"><h3>Overall Rank</h3><h2>{{ d.ranks.overall }} / {{ d.totals.overall }}</h2><div class="percentile">{{ d.perc.overall }}%ile</div></div>
                <div class="rank-card"><h3>Category Rank</h3><h2>{{ d.ranks.cat }} / {{ d.totals.cat }}</h2><div class="percentile">{{ d.perc.cat }}%ile</div></div>
                <div class="rank-card"><h3>Shift Rank</h3><h2>{{ d.ranks.shift }} / {{ d.totals.shift }}</h2><div class="percentile">{{ d.perc.shift }}%ile</div></div>
                <div class="rank-card"><h3>Comp Rank</h3><h2>{{ d.ranks.comp if d.is_comp else 'N/A' }}</h2></div>
                <div class="rank-card"><h3>CPT Rank</h3><h2>{{ d.ranks.cpt if d.is_cpt else 'N/A' }}</h2></div>
            </div>

            <table>
                <tr><th>Subject</th><th>Correct</th><th>Wrong</th><th>Left</th><th>Score</th></tr>
                {% for sub, v in d.subs.items() %}
                <tr><td>{{ sub }}</td><td>{{ v.c }}</td><td>{{ v.w }}</td><td>{{ v.l }}</td><td><b>{{ v.m }}</b></td></tr>
                {% endfor %}
            </table>
        </div>
        {% endif %}
    </div>
</body>
</html>
'''

# 4. Route Logic
@main_bp.route('/', methods=['GET', 'POST'])
def main_home():
    init_db()
    data = None
    if request.method == 'POST':
        url, cat = request.form.get('url'), request.form.get('category')
        comp_t = 18 if cat=="UR" else (15 if cat in ["OBC","EWS"] else 12)
        cpt_t = 27 if cat=="UR" else (24 if cat in ["OBC","EWS"] else 21)
        
        try:
            res = requests.get(url)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Extraction of Candidate Information
            info_tds = soup.find_all('td')
            info = {}
            for i in range(len(info_tds)-1):
                k = info_tds[i].text.strip()
                v = info_tds[i+1].text.strip()
                if k in ["Roll Number", "Candidate Name", "Exam Time", "Exam Date", "Test Center Name"]:
                    info[k] = v

            # Universal Scraping Logic
            # Use this for a deeper search
            # --- FIXED SCRAPING LOGIC ---
            # We try the most common tags first, then fall back to deep search
            qs = soup.find_all('div', class_=re.compile(r'question-pnl|section-it'))
            
            if not qs:
                # Fallback: Search for tables containing question data if divs aren't found
                qs = [t for t in soup.find_all('table') if "Question ID" in t.text]

            # REMOVE the old line below from your code:
            # qs = soup.find_all('div', class_='question-pnl') or soup.find_all('table', class_='question-pnl')
            
            print(f"DEBUG: Scraper found {len(qs)} questions") 
            # ----------------------------

            for i, q in enumerate(qs):
                sub = "Subject 1" if i<30 else ("Subject 2" if i<60 else ("Subject 3" if i<105 else ("Subject 4" if i<130 else "Computer")))
                
                # Robust search for correct answer
                ans_el = q.find(class_=re.compile('rightAns', re.I))
                if not ans_el: continue
                
                right = ans_el.text.strip()[0]
                tds = q.find_all('td')
                chosen = "--"
                
                for j, r in enumerate(tds):
                    txt = r.text.strip()
                    if "Chosen Option" in txt or "चयनित विकल्प" in txt:
                        chosen = tds[j+1].text.strip()
                
                pt = 3 if chosen == right else (-1 if (chosen != "--" and chosen != "None") else 0)
                
                subs[sub]['c' if pt==3 else ('w' if pt==-1 else 'l')] += 1
                subs[sub]['m'] += pt
                if sub != "Computer": merit += pt
                else: comp += pt

            # Google Sheets Backup
            gsheet_url = "https://script.google.com/macros/s/AKfycbxHAy5mclNXo98XISQIywbStTBybV3jucAu_Vd_SQp0QQsAaCbvsqk-RR0oWlHhD1tH/exec"
            payload = {"roll": info.get("Roll Number"), "name": info.get("Candidate Name"), "score": merit, "category": cat, "shift": info.get("Exam Time"), "paper_type": "Main"}
            try: requests.post(gsheet_url, data=json.dumps(payload), timeout=5)
            except: pass

            # SQLite Database Storage
            conn = sqlite3.connect('ssc_data.db')
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?)", 
                       (info.get("Roll Number", "N/A"), info.get("Candidate Name", "Unknown"), merit, cat, info.get("Exam Time", "N/A"), info.get("Exam Date", "N/A"), info.get("Test Center Name", "N/A"), comp))
            conn.commit()

            # Ranking Calculations
            def get_stats(query, params):
                cur.execute(query, params)
                r = cur.fetchone()[0] + 1
                base_q = query.replace("score > ?", "1").replace("comp_score >= ?", "1").split("WHERE")[0]
                if "category" in query: base_q += " WHERE category = ?"
                elif "shift" in query: base_q += " WHERE shift = ?"
                cur.execute(base_q, (params[1],) if len(params)>1 else ())
                t = cur.fetchone()[0]
                p = round(((t - r) / (t - 1) * 100), 2) if t > 1 else 100.0
                return r, t, p

            ranks, totals, perc = {}, {}, {}
            ranks['overall'], totals['overall'], perc['overall'] = get_stats("SELECT COUNT(*) FROM results WHERE score > ?", (merit,))
            ranks['cat'], totals['cat'], perc['cat'] = get_stats("SELECT COUNT(*) FROM results WHERE score > ? AND category = ?", (merit, cat))
            ranks['shift'], totals['shift'], perc['shift'] = get_stats("SELECT COUNT(*) FROM results WHERE score > ? AND shift = ?", (merit, info.get("Exam Time", "")))
            
            cur.execute("SELECT COUNT(*) FROM results WHERE score > ? AND comp_score >= ?", (merit, comp_t))
            ranks['comp'] = cur.fetchone()[0] + 1
            cur.execute("SELECT COUNT(*) FROM results WHERE score > ? AND comp_score >= ?", (merit, cpt_t))
            ranks['cpt'] = cur.fetchone()[0] + 1
            
            conn.close()
            data = {'name': info.get("Candidate Name"), 'shift': info.get("Exam Time"), 'subs': subs, 'score': merit, 'ranks': ranks, 'totals': totals, 'perc': perc, 'is_comp': comp >= comp_t, 'is_cpt': comp >= cpt_t}
        
        except Exception as e:
            print(f"Scraping Error: {e}")
            
    return render_template_string(HTML_PAGE, d=data)

@main_bp.route('/leaderboard')
def leaderboard():
    conn = sqlite3.connect('ssc_data.db')
    cur = conn.cursor()
    cur.execute("SELECT name, score, category, shift FROM results ORDER BY score DESC LIMIT 10")
    players = cur.fetchall()
    conn.close()
    return render_template_string(LEADERBOARD_PAGE, players=players)

